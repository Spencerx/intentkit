package bot

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"strconv"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"gorm.io/datatypes"
	"gorm.io/gorm"

	"github.com/crestalnetwork/intentkit/integrations/wechat/store"
)

// SessionTriggerExpiring is the value of the `system_trigger` field on the
// /core/lead/stream payload that asks the lead agent to generate a pre-expiry
// notice (window-about-to-close + status summary) for a wechat user.
const SessionTriggerExpiring = "wechat_session_expiring"

const (
	sessionLastKeyFmt   = "wechat:session:last:%s"
	sessionWarnedKeyFmt = "wechat:session:warned:%s"

	// sessionDataField is the sub-key inside team_channel_data.data used by
	// the DB fallback. Keep aligned with the WechatChannelData pydantic
	// model on the Python side if we ever expose it there.
	sessionDataField = "wechat_session"
)

// sessionState is the persisted per-team state for the wechat reply window.
// LastUserMessageAt is unix-ms of the last qualifying inbound user message.
// WarnedFor, when non-zero, is the LastUserMessageAt value the pre-expiry
// notice was sent for — used to skip duplicate notices within one window.
type sessionState struct {
	LastUserMessageAt int64 `json:"last_user_message_at"`
	WarnedFor         int64 `json:"warned_for,omitempty"`
}

// FireFunc is invoked when a team's pre-expiry timer fires and the
// SessionTimerManager has confirmed (a) the window is still open and (b) no
// notice has been sent for the current window. The chat ID is resolved by
// the implementation at call time so it always reflects the current
// default_channel_chat_id rather than whatever was cached at schedule time.
// Returning an error is logged but does not cause a retry — the warned flag
// is already set.
type FireFunc func(ctx context.Context, teamID string) error

// SessionTimerManager schedules per-team pre-expiry notices for the wechat
// reply window. Persists state to Redis when available, with a JSONB
// fallback inside team_channel_data.data so timers survive a Go restart.
type SessionTimerManager struct {
	db         *gorm.DB
	redis      *redis.Client
	fire       FireFunc
	window     time.Duration
	warnBefore time.Duration
	// fireTimeout caps a single fire-callback execution; tests override it
	// to keep shutdown snappy. Defaults to 10 minutes.
	fireTimeout time.Duration

	// mgrCtx is the parent context for every fire callback. Cancelled on
	// Stop so any in-flight agent run is aborted instead of dangling past
	// process shutdown.
	mgrCtx    context.Context
	mgrCancel context.CancelFunc

	mu     sync.Mutex
	timers map[string]*time.Timer
	closed bool
}

// NewSessionTimerManager wires the timer manager. redisClient may be nil, in
// which case the DB fallback is used unconditionally. fire is the callback
// invoked when a team's notice is due (after lock acquisition).
func NewSessionTimerManager(
	db *gorm.DB,
	redisClient *redis.Client,
	window, warnBefore time.Duration,
	fire FireFunc,
) *SessionTimerManager {
	ctx, cancel := context.WithCancel(context.Background())
	return &SessionTimerManager{
		db:          db,
		redis:       redisClient,
		fire:        fire,
		window:      window,
		warnBefore:  warnBefore,
		fireTimeout: 10 * time.Minute,
		mgrCtx:      ctx,
		mgrCancel:   cancel,
		timers:      make(map[string]*time.Timer),
	}
}

// OnQualifyingUserMessage records that the team's default-push user just
// sent us a message: persists the new "last seen" timestamp, clears any
// warned marker for the current window, and (re)arms the pre-expiry timer.
func (s *SessionTimerManager) OnQualifyingUserMessage(ctx context.Context, teamID string) {
	now := time.Now()
	if err := s.writeRefresh(ctx, teamID, now); err != nil {
		slog.Error("wechat session: failed to persist last-user-message",
			"team_id", teamID, "error", err)
		// fall through: still schedule the in-process timer so the warning
		// fires for the current bot lifetime even without persistence.
	}
	s.scheduleTimer(teamID, s.window-s.warnBefore, now.UnixMilli())
}

// Restore is called once on startup with the active wechat team IDs. For
// each, it reads persisted state and schedules a timer if a notice is still
// due inside the current window. If we are already past the planned trigger
// time but the window is still open, it fires immediately.
func (s *SessionTimerManager) Restore(ctx context.Context, teamIDs []string) {
	for _, teamID := range teamIDs {
		state, err := s.readState(ctx, teamID)
		if err != nil {
			slog.Warn("wechat session: failed to read state on restore",
				"team_id", teamID, "error", err)
			continue
		}
		if state == nil || state.LastUserMessageAt == 0 {
			continue
		}
		last := time.UnixMilli(state.LastUserMessageAt)
		elapsed := time.Since(last)
		if elapsed >= s.window {
			continue // window already closed
		}
		if state.WarnedFor == state.LastUserMessageAt {
			continue // already warned for this window
		}
		delay := s.window - s.warnBefore - elapsed
		if delay < 0 {
			delay = 0
		}
		s.scheduleTimer(teamID, delay, state.LastUserMessageAt)
		slog.Info("wechat session: restored timer",
			"team_id", teamID, "delay", delay.String())
	}
}

// Remove cancels and forgets the timer for a team, e.g. when the channel is
// disabled. Persisted state is left to expire naturally.
func (s *SessionTimerManager) Remove(teamID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if t, ok := s.timers[teamID]; ok {
		t.Stop()
		delete(s.timers, teamID)
	}
}

// Stop cancels all timers, aborts any in-flight fire callback, and rejects
// new schedules.
func (s *SessionTimerManager) Stop() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.closed = true
	for _, t := range s.timers {
		t.Stop()
	}
	s.timers = make(map[string]*time.Timer)
	s.mgrCancel()
}

func (s *SessionTimerManager) scheduleTimer(teamID string, delay time.Duration, scheduledForLast int64) {
	if delay < 0 {
		delay = 0
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return
	}
	if existing, ok := s.timers[teamID]; ok {
		existing.Stop()
	}
	s.timers[teamID] = time.AfterFunc(delay, func() {
		s.onTimerFire(teamID, scheduledForLast)
	})
}

func (s *SessionTimerManager) onTimerFire(teamID string, scheduledForLast int64) {
	// Inherit from the manager-level context so Stop() aborts in-flight
	// fire callbacks instead of leaving them dangling past shutdown.
	ctx, cancel := context.WithTimeout(s.mgrCtx, s.fireTimeout)
	defer cancel()

	state, err := s.readState(ctx, teamID)
	if err != nil {
		slog.Error("wechat session: failed to read state on fire",
			"team_id", teamID, "error", err)
		return
	}
	if state == nil || state.LastUserMessageAt == 0 {
		return
	}
	if state.LastUserMessageAt != scheduledForLast {
		// A user message arrived between schedule time and fire — the new
		// timer (set by Refresh) owns this window. Without this guard a
		// stale callback would acquire the warned lock for the new window
		// and silently suppress the legitimate notice.
		return
	}
	last := time.UnixMilli(state.LastUserMessageAt)
	if time.Since(last) >= s.window {
		// window already closed — pushing now would just hit ret=-2.
		slog.Info("wechat session: window already closed at fire time",
			"team_id", teamID, "last_user_message_at", last)
		return
	}
	if state.WarnedFor == state.LastUserMessageAt {
		return // already warned for this window
	}

	acquired, err := s.acquireWarnedLock(ctx, teamID, state.LastUserMessageAt)
	if err != nil {
		slog.Error("wechat session: failed to acquire warned lock",
			"team_id", teamID, "error", err)
		return
	}
	if !acquired {
		slog.Debug("wechat session: warned lock not acquired (already sent)",
			"team_id", teamID)
		return
	}

	if err := s.fire(ctx, teamID); err != nil {
		slog.Error("wechat session: pre-expiry notice failed",
			"team_id", teamID, "error", err)
	}
}

// writeRefresh persists last_user_message_at = now and clears warned_for.
// In Redis, sets the last key (TTL = window + 1h) and deletes the warned
// key in a single pipeline. In the DB fallback, replaces the wechat_session
// sub-object atomically via jsonb_set.
func (s *SessionTimerManager) writeRefresh(ctx context.Context, teamID string, now time.Time) error {
	ms := now.UnixMilli()
	if s.redis != nil {
		ttl := s.window + time.Hour
		pipe := s.redis.Pipeline()
		pipe.Set(ctx, fmt.Sprintf(sessionLastKeyFmt, teamID), strconv.FormatInt(ms, 10), ttl)
		pipe.Del(ctx, fmt.Sprintf(sessionWarnedKeyFmt, teamID))
		if _, err := pipe.Exec(ctx); err == nil {
			return nil
		} else {
			slog.Warn("wechat session: redis write failed, falling back to DB",
				"team_id", teamID, "error", err)
		}
	}
	return s.writeStateToDB(ctx, teamID, sessionState{LastUserMessageAt: ms})
}

// readState returns the persisted state for a team, or (nil, nil) when no
// state exists in either store. Tries Redis first; if Redis errors OR
// returns nil (which can mean either "no state" or "state was DB-only
// because Redis was down for that earlier write"), falls through to DB.
func (s *SessionTimerManager) readState(ctx context.Context, teamID string) (*sessionState, error) {
	if s.redis != nil {
		state, err := s.readStateFromRedis(ctx, teamID)
		if err == nil && state != nil {
			return state, nil
		}
		if err != nil {
			slog.Warn("wechat session: redis read failed, falling back to DB",
				"team_id", teamID, "error", err)
		}
	}
	return s.readStateFromDB(ctx, teamID)
}

func (s *SessionTimerManager) readStateFromRedis(ctx context.Context, teamID string) (*sessionState, error) {
	lastKey := fmt.Sprintf(sessionLastKeyFmt, teamID)
	warnedKey := fmt.Sprintf(sessionWarnedKeyFmt, teamID)
	pipe := s.redis.Pipeline()
	lastCmd := pipe.Get(ctx, lastKey)
	warnedCmd := pipe.Get(ctx, warnedKey)
	if _, err := pipe.Exec(ctx); err != nil && !errors.Is(err, redis.Nil) {
		return nil, err
	}
	lastStr, err := lastCmd.Result()
	if errors.Is(err, redis.Nil) {
		return nil, nil
	} else if err != nil {
		return nil, err
	}
	last, err := strconv.ParseInt(lastStr, 10, 64)
	if err != nil {
		return nil, fmt.Errorf("parse last: %w", err)
	}
	state := &sessionState{LastUserMessageAt: last}
	if warnedStr, err := warnedCmd.Result(); err == nil {
		if w, perr := strconv.ParseInt(warnedStr, 10, 64); perr == nil {
			state.WarnedFor = w
		}
	}
	return state, nil
}

func (s *SessionTimerManager) readStateFromDB(ctx context.Context, teamID string) (*sessionState, error) {
	var data datatypes.JSONMap
	err := s.db.WithContext(ctx).
		Model(&store.TeamChannelData{}).
		Select("data").
		Where("team_id = ? AND channel_type = ?", teamID, "wechat").
		Limit(1).
		Pluck("data", &data).Error
	if err != nil {
		return nil, err
	}
	raw, ok := data[sessionDataField]
	if !ok || raw == nil {
		return nil, nil
	}
	// JSONMap unmarshals nested objects as map[string]interface{}; round-trip
	// through json so we can use the typed sessionState directly.
	buf, err := json.Marshal(raw)
	if err != nil {
		return nil, err
	}
	var state sessionState
	if err := json.Unmarshal(buf, &state); err != nil {
		return nil, err
	}
	if state.LastUserMessageAt == 0 {
		return nil, nil
	}
	return &state, nil
}

func (s *SessionTimerManager) writeStateToDB(ctx context.Context, teamID string, state sessionState) error {
	return store.MergeTeamChannelDataField(ctx, s.db, teamID, "wechat", sessionDataField, state)
}

// acquireWarnedLock atomically marks "warning sent for this window" and
// returns whether this caller won the race. In Redis, uses SET NX with a
// TTL aligned to the window so it expires automatically. In the DB
// fallback, performs a guarded UPDATE.
func (s *SessionTimerManager) acquireWarnedLock(ctx context.Context, teamID string, lastMs int64) (bool, error) {
	if s.redis != nil {
		ttl := s.window + time.Hour
		ok, err := s.redis.SetNX(
			ctx,
			fmt.Sprintf(sessionWarnedKeyFmt, teamID),
			strconv.FormatInt(lastMs, 10),
			ttl,
		).Result()
		if err == nil {
			return ok, nil
		}
		slog.Warn("wechat session: redis SETNX failed, falling back to DB",
			"team_id", teamID, "error", err)
	}
	// DB fallback: guarded UPDATE — only set warned_for when (a) the
	// persisted last_user_message_at still matches this window and (b) we
	// have not already marked this same window as warned.
	dataField := sessionDataField
	res := s.db.WithContext(ctx).Exec(
		`UPDATE team_channel_data
		   SET data = jsonb_set(
		         COALESCE(data, '{}'::jsonb),
		         ARRAY[?, ?]::text[],
		         to_jsonb(?::bigint)
		       )
		 WHERE team_id = ? AND channel_type = ?
		   AND (data->?->>'last_user_message_at')::bigint = ?
		   AND COALESCE((data->?->>'warned_for')::bigint, 0) <> ?`,
		dataField, "warned_for", lastMs,
		teamID, "wechat",
		dataField, lastMs,
		dataField, lastMs,
	)
	if res.Error != nil {
		return false, res.Error
	}
	return res.RowsAffected == 1, nil
}
