package bot

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"path"
	"strings"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/rs/xid"
	"gorm.io/gorm"

	"github.com/crestalnetwork/intentkit/integrations/shared"
	"github.com/crestalnetwork/intentkit/integrations/types"
	"github.com/crestalnetwork/intentkit/integrations/wechat/api"
	"github.com/crestalnetwork/intentkit/integrations/wechat/config"
	"github.com/crestalnetwork/intentkit/integrations/wechat/ilink"
	"github.com/crestalnetwork/intentkit/integrations/wechat/store"
)

type botEntry struct {
	client *ilink.Client
	// mu guards the mutable string fields below — they are read by the
	// poll-loop goroutine, by sync-tick refreshes, and by timer-fire
	// callbacks concurrently. The Manager-level lock is too coarse: it
	// already arbitrates the bots map, and holding it across DB writes
	// would serialize all per-team work.
	mu               sync.RWMutex
	typingTicket     string
	lastContextToken string // cached to skip DB writes when unchanged
	defaultChatID    string // teams.default_channel_chat_id when channel is wechat; "" otherwise
}

func (e *botEntry) getDefaultChatID() string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.defaultChatID
}

func (e *botEntry) setDefaultChatID(v string) {
	e.mu.Lock()
	e.defaultChatID = v
	e.mu.Unlock()
}

// updateContextTokenIfChanged returns true and updates the cache when the
// new token differs from what we last saw. False means caller can skip the
// follow-up DB write.
func (e *botEntry) updateContextTokenIfChanged(token string) bool {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.lastContextToken == token {
		return false
	}
	e.lastContextToken = token
	return true
}

func (e *botEntry) getTypingTicket() string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.typingTicket
}

func (e *botEntry) setTypingTicket(v string) {
	e.mu.Lock()
	e.typingTicket = v
	e.mu.Unlock()
}

// Manager manages WeChat bot lifecycles for team channels.
type Manager struct {
	db           *gorm.DB
	cfg          *config.Config
	apiClient    *api.Client
	storage      *shared.S3Storage
	sessionTimer *SessionTimerManager
	bots         map[string]*botEntry
	cancelFuncs  map[string]context.CancelFunc
	tokenHashes  map[string]string
	mu           sync.RWMutex
	stopCh       chan struct{}
}

func NewManager(db *gorm.DB, cfg *config.Config, apiClient *api.Client, storage *shared.S3Storage, redisClient *redis.Client) *Manager {
	m := &Manager{
		db:          db,
		cfg:         cfg,
		apiClient:   apiClient,
		storage:     storage,
		bots:        make(map[string]*botEntry),
		cancelFuncs: make(map[string]context.CancelFunc),
		tokenHashes: make(map[string]string),
		stopCh:      make(chan struct{}),
	}
	m.sessionTimer = NewSessionTimerManager(
		db, redisClient,
		cfg.WxSessionWindow, cfg.WxSessionWarnBefore,
		m.sendExpiringNotice,
	)
	return m
}

func (m *Manager) Start() {
	ticker := time.NewTicker(time.Duration(m.cfg.WxNewChannelPollInterval) * time.Second)
	defer ticker.Stop()

	// Restore must happen after syncBots so the botEntry map is populated.
	m.syncBots()
	m.restoreSessionTimers()

	for {
		select {
		case <-ticker.C:
			m.syncBots()
		case <-m.stopCh:
			return
		}
	}
}

// botKey is the map key under which an entry for a team's bot lives in
// m.bots / m.cancelFuncs / m.tokenHashes.
func botKey(teamID string) string { return "team:" + teamID }

// getEntry fetches the live botEntry for a team. ok is false when the bot
// is not currently running (e.g. channel disabled, or syncBots tore it
// down). Holds the read lock for the duration of the call only.
func (m *Manager) getEntry(teamID string) (*botEntry, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	entry, ok := m.bots[botKey(teamID)]
	return entry, ok
}

// restoreSessionTimers schedules pre-expiry timers for every active wechat
// team whose persisted state shows a still-open reply window.
func (m *Manager) restoreSessionTimers() {
	m.mu.RLock()
	teamIDs := make([]string, 0, len(m.bots))
	for key := range m.bots {
		teamIDs = append(teamIDs, strings.TrimPrefix(key, "team:"))
	}
	m.mu.RUnlock()
	if len(teamIDs) == 0 {
		return
	}
	m.sessionTimer.Restore(context.Background(), teamIDs)
}

const heartbeatFile = "/tmp/healthy"

func writeHeartbeat() {
	if err := os.WriteFile(heartbeatFile, []byte("ok"), 0644); err != nil {
		slog.Error("Failed to write heartbeat file", "error", err)
	}
}

func (m *Manager) Stop() {
	close(m.stopCh)
	m.sessionTimer.Stop()
	m.mu.Lock()
	defer m.mu.Unlock()

	for id, cancel := range m.cancelFuncs {
		cancel()
		slog.Info("Stopped wechat bot", "id", id)
	}
}

// syncBots queries team_channels for enabled WeChat channels and manages their bots.
// Only queries team_channels — WeChat does NOT support individual agents.
func (m *Manager) syncBots() {
	var teamChannels []store.TeamChannel
	if err := m.db.Where("channel_type = ? AND enabled = ?", "wechat", true).Find(&teamChannels).Error; err != nil {
		slog.Error("Failed to fetch wechat team channels", "error", err)
		return
	}

	activeIDs := make(map[string]bool)

	for _, tc := range teamChannels {
		key := botKey(tc.TeamID)
		activeIDs[key] = true
		m.ensureTeamBotRunning(&tc)
	}
	// Pick up out-of-band changes to teams.default_channel_chat_id (e.g. via
	// the Python push-channel API) on each sync tick. Ensure-time only sets
	// it once; a wrong cached value would route notices to the wrong user.
	m.refreshDefaultChatIDs()

	// Stop bots for disabled/removed channels
	m.mu.Lock()
	stoppedTeams := make([]string, 0)
	for id, cancel := range m.cancelFuncs {
		if !activeIDs[id] {
			cancel()
			delete(m.bots, id)
			delete(m.cancelFuncs, id)
			delete(m.tokenHashes, id)
			stoppedTeams = append(stoppedTeams, strings.TrimPrefix(id, "team:"))
			slog.Info("Stopped and removed wechat bot", "id", id)
		}
	}
	m.mu.Unlock()
	for _, teamID := range stoppedTeams {
		m.sessionTimer.Remove(teamID)
	}
}

// refreshDefaultChatIDs re-reads teams.default_channel_chat_id for every
// active wechat bot and updates the cached value on each entry. Cheap PK
// lookups; runs once per sync tick.
func (m *Manager) refreshDefaultChatIDs() {
	m.mu.RLock()
	teamIDs := make([]string, 0, len(m.bots))
	for key := range m.bots {
		teamIDs = append(teamIDs, strings.TrimPrefix(key, "team:"))
	}
	m.mu.RUnlock()
	for _, teamID := range teamIDs {
		chatID := m.fetchDefaultChatID(context.Background(), teamID)
		if entry, ok := m.getEntry(teamID); ok {
			entry.setDefaultChatID(chatID)
		}
	}

	writeHeartbeat()
}

func (m *Manager) ensureTeamBotRunning(tc *store.TeamChannel) {
	token := getStringFromConfig(tc.Config, "bot_token")
	baseURL := getStringFromConfig(tc.Config, "baseurl")
	botID := getStringFromConfig(tc.Config, "ilink_bot_id")
	if token == "" || baseURL == "" {
		slog.Warn("WeChat team channel missing bot_token or baseurl", "team_id", tc.TeamID)
		return
	}

	key := "team:" + tc.TeamID

	m.mu.RLock()
	_, exists := m.bots[key]
	oldToken := m.tokenHashes[key]
	m.mu.RUnlock()

	if exists && oldToken == token {
		return
	}

	if exists && oldToken != token {
		slog.Info("WeChat bot token changed, restarting", "team_id", tc.TeamID)
		m.mu.Lock()
		if cancel, ok := m.cancelFuncs[key]; ok {
			cancel()
		}
		delete(m.bots, key)
		delete(m.cancelFuncs, key)
		delete(m.tokenHashes, key)
		m.mu.Unlock()
	}

	client := ilink.NewClient(baseURL, token, botID)

	// GetConfig requires a user_id and context_token from a real message,
	// which we don't have at startup. typing_ticket will be fetched on first message.
	typingTicket := ""

	// Save runtime data
	m.updateTeamChannelData(tc.TeamID, typingTicket)

	// Start long-poll loop
	ctx, cancel := context.WithCancel(context.Background())

	entry := &botEntry{
		client:        client,
		typingTicket:  typingTicket,
		defaultChatID: m.fetchDefaultChatID(ctx, tc.TeamID),
	}

	go m.pollLoop(ctx, entry, tc.TeamID)

	m.mu.Lock()
	m.bots[key] = entry
	m.cancelFuncs[key] = cancel
	m.tokenHashes[key] = token
	m.mu.Unlock()

	slog.Info("Started wechat bot for team channel", "team_id", tc.TeamID)
}

func (m *Manager) pollLoop(ctx context.Context, entry *botEntry, teamID string) {
	backoff := 2 * time.Second
	const maxBackoff = 60 * time.Second
	consecutiveErrors := 0

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		msgs, err := entry.client.GetUpdates(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return // context cancelled
			}
			consecutiveErrors++
			slog.Error("GetUpdates failed",
				"team_id", teamID,
				"error", err,
				"consecutive_errors", consecutiveErrors,
				"next_backoff", backoff.String(),
			)
			time.Sleep(backoff)
			backoff = min(backoff*2, maxBackoff)
			continue
		}

		if consecutiveErrors > 0 {
			slog.Info("GetUpdates recovered after errors",
				"team_id", teamID,
				"previous_consecutive_errors", consecutiveErrors,
			)
		}
		// Reset backoff on success
		consecutiveErrors = 0
		backoff = 2 * time.Second

		if len(msgs) > 0 {
			slog.Debug("GetUpdates received messages", "team_id", teamID, "msg_count", len(msgs))
		}

		for _, msg := range msgs {
			m.handleTeamMessage(entry, msg, teamID)
		}
	}
}

func (m *Manager) updateTeamChannelData(teamID, typingTicket string) {
	if typingTicket == "" {
		return
	}
	if err := store.MergeTeamChannelDataField(
		context.Background(), m.db, teamID, "wechat", "typing_ticket", typingTicket,
	); err != nil {
		slog.Error("Failed to update typing_ticket", "team_id", teamID, "error", err)
	}
}

func (m *Manager) updateContextToken(teamID, contextToken string) {
	if contextToken == "" {
		return
	}
	if err := store.MergeTeamChannelDataField(
		context.Background(), m.db, teamID, "wechat", "context_token", contextToken,
	); err != nil {
		slog.Error("Failed to update context_token", "team_id", teamID, "error", err)
	}
}

// fetchDefaultChatID returns teams.default_channel_chat_id when the team's
// default_channel is "wechat", or "" otherwise. Errors are logged and treated
// as "no default" — the timer simply won't arm until /default is run.
func (m *Manager) fetchDefaultChatID(ctx context.Context, teamID string) string {
	var chatID string
	err := m.db.WithContext(ctx).Raw(
		`SELECT default_channel_chat_id FROM teams
		 WHERE id = ? AND default_channel = ? AND default_channel_chat_id IS NOT NULL`,
		teamID, "wechat",
	).Row().Scan(&chatID)
	if err != nil {
		// gorm returns sql.ErrNoRows when the team has no wechat default; that
		// is the common case at startup, not worth logging.
		if !errors.Is(err, gorm.ErrRecordNotFound) && err.Error() != "sql: no rows in result set" {
			slog.Warn("wechat: failed to read default_channel_chat_id",
				"team_id", teamID, "error", err)
		}
		return ""
	}
	return chatID
}

// sendExpiringNotice is the FireFunc passed to the SessionTimerManager. It
// resolves the team's current push target and context_token at call time —
// so a mid-window default-chat change is honored AND a freshly-restarted
// process (whose in-memory cache hasn't been hydrated yet) can still send.
// Then runs the lead agent with the wechat_session_expiring system trigger
// and streams the response through the team's WechatSender, so the notice
// reaches the user inside the still-open reply window.
func (m *Manager) sendExpiringNotice(ctx context.Context, teamID string) error {
	entry, ok := m.getEntry(teamID)
	if !ok {
		return fmt.Errorf("no active wechat bot for team %s", teamID)
	}
	chatID := entry.getDefaultChatID()
	if chatID == "" {
		return errors.New("no default_channel_chat_id — nothing to notify")
	}
	contextToken, err := m.fetchContextToken(ctx, teamID)
	if err != nil {
		return fmt.Errorf("read context_token: %w", err)
	}
	if contextToken == "" {
		// No persisted context_token means no real inbound message has ever
		// been seen — iLink would reject the send. The timer guards against
		// this (state only exists after OnQualifyingUserMessage), but check
		// anyway.
		return errors.New("no persisted context_token — cannot push notice")
	}

	sender := NewWechatSender(entry.client, chatID, contextToken)
	payload := map[string]interface{}{
		"team_id":         teamID,
		"channel_type":    "wechat",
		"channel_user_id": chatID,
		"chat_id":         chatID,
		"message":         "",
		"system_trigger":  SessionTriggerExpiring,
	}
	return m.apiClient.StreamTeamLead(ctx, payload, func(chatMsg types.ChatMessage) error {
		shared.DispatchMessage(ctx, chatMsg, sender)
		return nil
	})
}

// fetchContextToken reads the current context_token from team_channel_data
// for the team's wechat channel. Mirrors push.py's lookup so both proactive
// paths use the same source of truth and survive a Go restart without any
// in-memory hydration.
func (m *Manager) fetchContextToken(ctx context.Context, teamID string) (string, error) {
	var token string
	err := m.db.WithContext(ctx).Raw(
		`SELECT data->>'context_token' FROM team_channel_data
		 WHERE team_id = ? AND channel_type = ?`,
		teamID, "wechat",
	).Row().Scan(&token)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) || err.Error() == "sql: no rows in result set" {
			return "", nil
		}
		return "", err
	}
	return token, nil
}

func getStringFromConfig(config map[string]interface{}, key string) string {
	if val, ok := config[key]; ok {
		if s, ok := val.(string); ok {
			return s
		}
	}
	return ""
}

func (m *Manager) handleTeamMessage(entry *botEntry, msg ilink.WeixinMessage, teamID string) {
	text := ""
	attachments := make([]types.ChatMessageAttach, 0)
	// Voice attachments ride on types.AttachFile (no dedicated audio type),
	// so we track their lead texts separately to preserve the "this is a
	// voice message" hint. The core engine drops attachment.lead_text when
	// forwarding to the LLM, so we inline voiceNotes into the user text.
	var voiceNotes []string
	voiceCount := 0
	for _, item := range msg.ItemList {
		switch {
		case item.Type == ilink.ItemTypeText && item.TextItem != nil:
			text = item.TextItem.Text
		case item.Type == ilink.ItemTypeImage && item.ImageItem != nil:
			if att, ok := m.handleInboundImage(teamID, msg.FromUserID, *item.ImageItem); ok {
				attachments = append(attachments, att)
			}
		case item.Type == ilink.ItemTypeVoice && item.VoiceItem != nil:
			if att, ok := m.handleInboundVoice(teamID, msg.FromUserID, *item.VoiceItem); ok {
				attachments = append(attachments, att)
				voiceCount++
				if att.LeadText != nil {
					voiceNotes = append(voiceNotes, *att.LeadText)
				}
			}
		case item.Type == ilink.ItemTypeVideo && item.VideoItem != nil:
			if att, ok := m.handleInboundVideo(teamID, msg.FromUserID, *item.VideoItem); ok {
				attachments = append(attachments, att)
			}
		case item.Type == ilink.ItemTypeFile && item.FileItem != nil:
			if att, ok := m.handleInboundFile(teamID, msg.FromUserID, *item.FileItem); ok {
				attachments = append(attachments, att)
			}
		}
	}

	if msg.FromUserID == "" || (text == "" && len(attachments) == 0) {
		return
	}

	rawText := text
	if len(attachments) > 0 && rawText == "" {
		text = summarizeAttachments(attachments, voiceCount)
	} else if len(voiceNotes) > 0 {
		text = strings.TrimSpace(text + "\n\n" + strings.Join(voiceNotes, " "))
	}

	slog.Info("Received wechat message", "team_id", teamID, "from", msg.FromUserID)

	// Store latest context_token for proactive messaging (skip DB write if unchanged)
	if entry.updateContextTokenIfChanged(msg.ContextToken) {
		m.updateContextToken(teamID, msg.ContextToken)
	}

	// Intercept /default command — set this chat as the push channel
	if rawText == "/default" {
		if err := m.apiClient.SetPushChannel(context.Background(), teamID, "wechat", msg.FromUserID, false); err != nil {
			slog.Error("Failed to set push channel", "team_id", teamID, "error", err)
			_ = entry.client.SendMessage(context.Background(), msg.FromUserID, msg.ContextToken, "Failed to set push channel.")
		} else {
			_ = entry.client.SendMessage(context.Background(), msg.FromUserID, msg.ContextToken, "This chat is now the default push channel.")
			entry.setDefaultChatID(msg.FromUserID)
			m.sessionTimer.OnQualifyingUserMessage(context.Background(), teamID)
		}
		return
	}

	// Other users chatting with the bot do not refresh the timer —
	// proactive pushes only target the default chat.
	if cur := entry.getDefaultChatID(); cur != "" && msg.FromUserID == cur {
		m.sessionTimer.OnQualifyingUserMessage(context.Background(), teamID)
	}

	// Lazy-fetch typing_ticket on first message (requires user_id + context_token)
	typingTicket := entry.getTypingTicket()
	if typingTicket == "" {
		cfgResp, err := entry.client.GetConfig(context.Background(), msg.FromUserID, msg.ContextToken)
		if err != nil {
			slog.Warn("Failed to get typing_ticket", "team_id", teamID, "error", err)
		} else {
			typingTicket = cfgResp.TypingTicket
			entry.setTypingTicket(typingTicket)
			m.updateTeamChannelData(teamID, typingTicket)
		}
	}

	// Start periodic typing indicator while waiting for API response
	typingCtx, typingCancel := context.WithCancel(context.Background())
	if typingTicket != "" {
		_ = entry.client.SendTyping(typingCtx, msg.FromUserID, typingTicket)
		go func() {
			ticker := time.NewTicker(10 * time.Second)
			defer ticker.Stop()
			for {
				select {
				case <-typingCtx.Done():
					return
				case <-ticker.C:
					_ = entry.client.SendTyping(typingCtx, msg.FromUserID, typingTicket)
				}
			}
		}()
	}

	// Call Core API via SSE streaming
	payload := map[string]interface{}{
		"team_id":         teamID,
		"channel_type":    "wechat",
		"channel_user_id": msg.FromUserID,
		"chat_id":         msg.FromUserID,
		"message":         text,
	}
	if len(attachments) > 0 {
		payload["attachments"] = attachments
	}

	sender := NewWechatSender(entry.client, msg.FromUserID, msg.ContextToken)
	err := m.apiClient.StreamTeamLead(context.Background(), payload, func(chatMsg types.ChatMessage) error {
		shared.DispatchMessage(context.Background(), chatMsg, sender)
		return nil
	})
	typingCancel() // stop typing indicator

	if err != nil {
		slog.Error("Failed to stream wechat team lead", "error", err)
		if sendErr := entry.client.SendMessage(context.Background(), msg.FromUserID, msg.ContextToken, "Sorry, I encountered an error processing your request."); sendErr != nil {
			slog.Error("Failed to send error reply", "team_id", teamID, "error", sendErr)
		}
		return
	}
}

// Media kind labels used in log fields and S3 key paths.
const (
	mediaKindImage = "image"
	mediaKindVoice = "voice"
	mediaKindVideo = "video"
	mediaKindFile  = "file"
)

// mediaSpec describes how to turn one decrypted inbound media payload into a
// ChatMessageAttach: which attachment type, what lead text, what extension/
// content-type to use when the sniffed MIME is unknown, and an optional
// validator for acceptance rules not expressible as a MIME predicate.
type mediaSpec struct {
	kind        string
	attachType  string
	defaultExt  string
	defaultMime string
	leadText    string
	// validate runs after download+decrypt succeeds. Returning a non-empty
	// reason drops the attachment with a warning log. Used by the image path
	// to reject MIMEs that survive isRecognizedImageMime but have no mapping
	// in shared.ExtensionForContentType.
	validate func(ext, contentType string) (reason string)
	// overrideExt, when non-empty, wins over the sniffed extension. Used for
	// files where the user-provided filename extension is more reliable.
	overrideExt string
}

// handleInboundImage downloads, decrypts, and uploads an inbound image to
// S3, returning an attachment ready to forward to the LLM. Returns ok=false
// on any failure; errors are logged and the item is dropped rather than
// aborting the whole message.
func (m *Manager) handleInboundImage(teamID, fromUserID string, img ilink.ImageItem) (types.ChatMessageAttach, bool) {
	slog.Info("wechat image: received",
		"team_id", teamID,
		"from", fromUserID,
		"media_url", img.Media.URL,
		"encrypt_query_param_len", len(img.Media.EncryptQueryParam),
		"has_media_aes_key", img.Media.AESKey != "",
		"media_aes_key_len", len(img.Media.AESKey),
		"encrypt_type", img.Media.EncryptType,
		"has_image_item_aeskey", img.AESKeyHex != "",
		"image_item_aeskey_len", len(img.AESKeyHex),
		"image_item_url", img.URL,
		"mid_size", img.MidSize,
	)
	spec := mediaSpec{
		kind:       mediaKindImage,
		attachType: types.AttachImage,
		leadText:   "User sent an image.",
		// Downstream forwards type=image attachments to Gemini vision, which
		// only accepts a small set of formats. ilink's strict image MIME
		// policy already ensures contentType starts with "image/"; this
		// rejects exotic image subtypes (HEIC, etc.) with no extension map.
		validate: func(ext, _ string) string {
			if ext == "" {
				return "no extension for content type"
			}
			return ""
		},
	}
	return m.finalizeInboundMedia(teamID, fromUserID, spec, func() ([]byte, string, error) {
		return ilink.DownloadAndDecryptImage(context.Background(), img)
	})
}

// handleInboundVoice downloads, decrypts, and uploads an inbound voice
// message. No AttachVoice type exists, so it's forwarded as a file
// attachment. WeChat sends SILK-v3 which no LLM accepts directly; we
// transcode to MP3 (Gemini-compatible) before upload. If transcoding
// fails, fall back to uploading the original SILK so the message at
// least lands in storage for diagnostics.
func (m *Manager) handleInboundVoice(teamID, fromUserID string, vi ilink.VoiceItem) (types.ChatMessageAttach, bool) {
	slog.Info("wechat voice: received",
		"team_id", teamID,
		"from", fromUserID,
		"media_url", vi.Media.URL,
		"has_voice_item_aeskey", vi.AESKeyHex != "",
		"duration", vi.Duration,
	)
	leadText := "User sent a voice message."
	if vi.Duration > 0 {
		leadText = fmt.Sprintf("User sent a voice message (%d seconds).", vi.Duration)
	}

	silkData, _, err := ilink.DownloadAndDecryptVoice(context.Background(), vi)
	if err != nil {
		slog.Error("Failed to download/decrypt wechat voice",
			"team_id", teamID, "from", fromUserID, "error", err)
		return types.ChatMessageAttach{}, false
	}

	// On transcode success, the upload becomes an audio/mpeg attachment that
	// the engine routes through the model's audio-input capability check.
	// On failure, fall back to uploading the raw SILK as a generic file so
	// at least storage gets the bytes for diagnostics.
	data, mime, ext := silkData, "audio/silk", "silk"
	attachType := types.AttachFile
	if mp3Data, transErr := transcodeSilkToMP3(context.Background(), silkData); transErr == nil {
		data, mime, ext = mp3Data, "audio/mpeg", "mp3"
		attachType = types.AttachAudio
	} else {
		slog.Warn("wechat voice: silk→mp3 transcode failed, falling back to silk file upload",
			"team_id", teamID, "from", fromUserID, "error", transErr)
	}

	spec := mediaSpec{
		kind:        mediaKindVoice,
		attachType:  attachType,
		defaultExt:  ext,
		defaultMime: mime,
		leadText:    leadText,
	}
	return m.finalizeInboundMedia(teamID, fromUserID, spec, func() ([]byte, string, error) {
		return data, mime, nil
	})
}

// handleInboundVideo downloads, decrypts, and uploads an inbound video.
func (m *Manager) handleInboundVideo(teamID, fromUserID string, vi ilink.VideoItem) (types.ChatMessageAttach, bool) {
	slog.Info("wechat video: received",
		"team_id", teamID,
		"from", fromUserID,
		"media_url", vi.Media.URL,
		"has_video_item_aeskey", vi.AESKeyHex != "",
		"duration", vi.Duration,
	)
	leadText := "User sent a video."
	if vi.Duration > 0 {
		leadText = fmt.Sprintf("User sent a video (%d seconds).", vi.Duration)
	}
	spec := mediaSpec{
		kind:        mediaKindVideo,
		attachType:  types.AttachVideo,
		defaultExt:  "mp4",
		defaultMime: "video/mp4",
		leadText:    leadText,
	}
	return m.finalizeInboundMedia(teamID, fromUserID, spec, func() ([]byte, string, error) {
		return ilink.DownloadAndDecryptVideo(context.Background(), vi)
	})
}

// handleInboundFile downloads, decrypts, and uploads an inbound file. The
// user-provided filename extension is preferred over sniffed MIME because
// it survives round-trips through tools that rewrite Content-Type.
func (m *Manager) handleInboundFile(teamID, fromUserID string, fi ilink.FileItem) (types.ChatMessageAttach, bool) {
	slog.Info("wechat file: received",
		"team_id", teamID,
		"from", fromUserID,
		"media_url", fi.Media.URL,
		"has_file_item_aeskey", fi.AESKeyHex != "",
		"file_name", fi.FileName,
		"file_size", fi.FileSize,
	)
	leadText := "User sent a file."
	if fi.FileName != "" {
		leadText = fmt.Sprintf("User sent a file: %s", fi.FileName)
	}
	spec := mediaSpec{
		kind:        mediaKindFile,
		attachType:  types.AttachFile,
		defaultExt:  "bin",
		defaultMime: "application/octet-stream",
		leadText:    leadText,
		overrideExt: extensionFromFilename(fi.FileName),
	}
	return m.finalizeInboundMedia(teamID, fromUserID, spec, func() ([]byte, string, error) {
		return ilink.DownloadAndDecryptFile(context.Background(), fi)
	})
}

// finalizeInboundMedia drives the shared "download → resolve ext → validate
// → upload → build attach" flow; per-kind specifics come in via spec and
// the download closure.
func (m *Manager) finalizeInboundMedia(
	teamID, fromUserID string,
	spec mediaSpec,
	download func() ([]byte, string, error),
) (types.ChatMessageAttach, bool) {
	data, contentType, err := download()
	if err != nil {
		slog.Error("Failed to download/decrypt wechat media",
			"team_id", teamID, "from", fromUserID, "kind", spec.kind, "error", err)
		return types.ChatMessageAttach{}, false
	}

	ext := spec.overrideExt
	if ext == "" {
		ext = shared.ExtensionForContentType(contentType)
	}
	if ext == "" && spec.defaultExt != "" {
		ext = spec.defaultExt
		contentType = spec.defaultMime
	}

	if spec.validate != nil {
		if reason := spec.validate(ext, contentType); reason != "" {
			slog.Warn("wechat media: dropping attachment",
				"team_id", teamID, "from", fromUserID,
				"kind", spec.kind, "mime", contentType, "reason", reason)
			return types.ChatMessageAttach{}, false
		}
	}

	url, err := m.uploadMedia(teamID, spec.kind, ext, data, contentType)
	if err != nil {
		slog.Error("Failed to upload wechat media to S3",
			"team_id", teamID, "from", fromUserID, "kind", spec.kind, "error", err)
		return types.ChatMessageAttach{}, false
	}

	leadText := spec.leadText
	return types.ChatMessageAttach{
		Type:     spec.attachType,
		LeadText: &leadText,
		URL:      &url,
	}, true
}

// uploadMedia builds an S3 key scoped by team and media kind and uploads
// the bytes, returning the public URL.
func (m *Manager) uploadMedia(teamID, kind, ext string, data []byte, contentType string) (string, error) {
	key := fmt.Sprintf("wechat/%s/%s/%d_%s.%s", teamID, kind, time.Now().UnixMilli(), xid.New().String(), ext)
	url, err := m.storage.StoreMedia(context.Background(), data, key, contentType)
	if err != nil {
		return "", err
	}
	slog.Info("Uploaded wechat media to S3", "team_id", teamID, "kind", kind, "url", url)
	return url, nil
}

// extensionFromFilename returns the lowercased extension (without the dot)
// from a filename, or "" if none is present. Uses path.Ext (always
// forward-slash) rather than filepath.Ext (OS-specific separator).
func extensionFromFilename(name string) string {
	ext := path.Ext(name)
	if len(ext) <= 1 {
		return ""
	}
	return strings.ToLower(ext[1:])
}

// summarizeAttachments builds a short placeholder message when the user
// sent only media (no caption text). voiceCount is the total number of
// inbound voice items (regardless of whether they transcoded to MP3 or
// fell back to raw SILK) — successful transcodes ride on AttachAudio,
// silk fallbacks on AttachFile, but both are reported as "voice message".
func summarizeAttachments(attachments []types.ChatMessageAttach, voiceCount int) string {
	var images, audios, videos, files int
	for _, att := range attachments {
		switch att.Type {
		case types.AttachImage:
			images++
		case types.AttachAudio:
			audios++
		case types.AttachVideo:
			videos++
		case types.AttachFile:
			files++
		}
	}
	// Silk-fallback voice items ride on AttachFile and would otherwise be
	// reported as generic "file"; subtract them so they're counted as
	// voice. Successful transcodes are already in `audios`, not `files`.
	silkFallbacks := voiceCount - audios
	if silkFallbacks < 0 {
		silkFallbacks = 0
	}
	files -= silkFallbacks
	if files < 0 {
		files = 0
	}

	parts := []string{}
	parts = appendNounPhrase(parts, images, "an image", "images")
	parts = appendNounPhrase(parts, voiceCount, "a voice message", "voice messages")
	parts = appendNounPhrase(parts, videos, "a video", "videos")
	parts = appendNounPhrase(parts, files, "a file", "files")
	if len(parts) == 0 {
		return "User sent an attachment."
	}
	return "User sent " + strings.Join(parts, ", ") + "."
}

// appendNounPhrase adds a count-aware phrase ("a video" / "3 videos") to
// parts when count > 0.
func appendNounPhrase(parts []string, count int, singular, plural string) []string {
	if count == 1 {
		return append(parts, singular)
	}
	if count > 1 {
		return append(parts, fmt.Sprintf("%d %s", count, plural))
	}
	return parts
}
