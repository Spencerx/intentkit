// Package outage aggregates long-poll failures across the per-bot poll
// goroutines of a channel integration, so a shared outage produces a handful
// of alerts instead of one per bot per backoff cycle.
package outage

import (
	"sort"
	"sync"
	"time"
)

const (
	// FailureThreshold is the number of consecutive poll failures at or
	// above which a bot counts as part of an outage. A long-poll endpoint
	// routinely yields the odd transient EOF when the server (or an
	// intermediate proxy/LB) closes an idle keep-alive connection the
	// client then reuses — common in the first polls right after a restart.
	// Those self-heal on the next poll; only a sustained run (a real
	// outage, a bad token, or a network partition) feeds the tracker.
	FailureThreshold = 3
	// GatherWindow delays the first alert of an outage so bots whose poll
	// loops cross the failure threshold at staggered times coalesce into
	// one alert. It also means a short blip that heals within the window
	// never alerts at all.
	GatherWindow = 2 * time.Minute
	// RealertEvery is how often a still-ongoing outage re-alerts with an
	// updated summary.
	RealertEvery = 30 * time.Minute
)

// Summary is the payload for one aggregated alert (or recovery notice).
type Summary struct {
	Affected []string // sorted bot IDs affected so far in this outage
	Duration time.Duration
	LastErr  string // most recent failure, "" on recovery notices
}

// Tracker aggregates poll failures across bots. All methods are safe for
// concurrent use.
//
// Lifecycle: an outage opens when the first bot crosses FailureThreshold
// and closes when the last failing bot recovers (or is forgotten). State
// changes never alert by themselves; callers run Flush — after every failed
// poll and from the manager's sync ticker — so deadline checks need no
// timer goroutine yet fire within one tick of the gather window or re-alert
// interval elapsing. A recovery summary is returned only if the outage
// actually alerted.
type Tracker struct {
	mu  sync.Mutex
	now func() time.Time // injectable for tests

	failing   map[string]struct{} // bots currently past the failure threshold
	affected  map[string]struct{} // every bot that failed during this outage
	started   time.Time           // first threshold crossing of this outage
	pendingAt time.Time           // when the gathered first alert may fire; zero once fired
	lastAlert time.Time           // zero until the first alert of this outage fires
	lastErr   string              // most recent failure error text
}

func NewTracker() *Tracker {
	return &Tracker{
		now:      time.Now,
		failing:  make(map[string]struct{}),
		affected: make(map[string]struct{}),
	}
}

// NoteFailure records one failed poll. Below the threshold it only
// refreshes the error sample; at or past it the bot joins the outage.
func (t *Tracker) NoteFailure(botID string, consecutive int, errText string) {
	t.mu.Lock()
	defer t.mu.Unlock()

	t.lastErr = errText
	if consecutive < FailureThreshold {
		return
	}
	if len(t.failing) == 0 {
		t.started = t.now()
		t.pendingAt = t.started.Add(GatherWindow)
		t.lastAlert = time.Time{}
	}
	t.failing[botID] = struct{}{}
	t.affected[botID] = struct{}{}
}

// Flush returns a non-nil summary when an aggregated alert is due: the
// gathered first alert of the outage, or a periodic re-alert.
func (t *Tracker) Flush() *Summary {
	t.mu.Lock()
	defer t.mu.Unlock()

	if len(t.failing) == 0 {
		return nil
	}
	now := t.now()
	switch {
	case !t.pendingAt.IsZero() && !now.Before(t.pendingAt):
		t.pendingAt = time.Time{}
	case t.pendingAt.IsZero() && now.Sub(t.lastAlert) >= RealertEvery:
	default:
		return nil
	}
	t.lastAlert = now
	sum := t.summary(now)
	sum.LastErr = t.lastErr
	return sum
}

// NoteSuccess records a recovered bot. It returns a non-nil summary when
// this was the last failing bot of an outage that had alerted, meaning the
// caller should emit a recovery notice.
func (t *Tracker) NoteSuccess(botID string) *Summary {
	t.mu.Lock()
	defer t.mu.Unlock()

	if _, ok := t.failing[botID]; !ok {
		return nil
	}
	delete(t.failing, botID)
	if len(t.failing) > 0 {
		return nil
	}

	var sum *Summary
	if !t.lastAlert.IsZero() {
		sum = t.summary(t.now())
	}
	t.reset()
	return sum
}

// Forget drops a bot whose poll loop is going away (channel disabled,
// token-change restart, shutdown) so a failing bot cannot hold the outage
// open forever. Unlike NoteSuccess it closes a drained outage silently —
// the bot did not recover, its poller just stopped. A token-change restart
// may race the replacement poller and momentarily drop its failure state;
// the next failed poll re-registers it.
func (t *Tracker) Forget(botID string) {
	t.mu.Lock()
	defer t.mu.Unlock()

	if _, ok := t.failing[botID]; !ok {
		return
	}
	delete(t.failing, botID)
	if len(t.failing) == 0 {
		t.reset()
	}
}

// reset clears per-outage state. Callers must hold t.mu.
func (t *Tracker) reset() {
	t.affected = make(map[string]struct{})
	t.started = time.Time{}
	t.pendingAt = time.Time{}
	t.lastAlert = time.Time{}
}

func (t *Tracker) summary(now time.Time) *Summary {
	affected := make([]string, 0, len(t.affected))
	for id := range t.affected {
		affected = append(affected, id)
	}
	sort.Strings(affected)
	return &Summary{Affected: affected, Duration: now.Sub(t.started)}
}
