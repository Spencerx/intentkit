package bot

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/mymmrac/telego"

	"github.com/crestalnetwork/intentkit/integrations/shared/alert"
)

// longPollTimeoutSeconds matches telego's default long-poll timeout that the
// previous UpdatesViaLongPolling(ctx, nil) call applied.
const longPollTimeoutSeconds = 8

// updatesFetcher is the slice of *telego.Bot that pollUpdates needs,
// extracted so tests can fake the Telegram API.
type updatesFetcher interface {
	GetUpdates(ctx context.Context, params *telego.GetUpdatesParams) ([]telego.Update, error)
}

// pollUpdates is our replacement for telego's UpdatesViaLongPolling. Owning
// the loop gives failures exponential backoff (telego retries on a fixed 8s
// forever) and feeds them into the shared outage tracker so a platform-wide
// outage alerts once instead of two telego error lines per bot per retry.
// Updates are dispatched inline in arrival order, matching the serial
// consumer goroutine it replaces.
func (m *Manager) pollUpdates(ctx context.Context, fetcher updatesFetcher, botID string, handle func(telego.Update)) {
	params := &telego.GetUpdatesParams{Timeout: longPollTimeoutSeconds}
	backoff := 2 * time.Second
	const maxBackoff = 4 * time.Minute
	consecutiveErrors := 0

	// A failing bot must not hold the outage open after its poller goes
	// away (bot disabled, token-change restart, shutdown).
	defer m.outage.Forget(botID)

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		updates, err := fetcher.GetUpdates(ctx, params)
		if err != nil {
			if ctx.Err() != nil {
				return // context cancelled
			}
			consecutiveErrors++
			// Per-bot lines stay at Warn so they never reach the alert
			// channel; the aggregated outage alert is the only GetUpdates
			// failure that pages.
			slog.Warn("GetUpdates failed",
				"bot_id", botID,
				"error", err,
				"consecutive_errors", consecutiveErrors,
				"next_backoff", backoff.String(),
			)
			m.outage.NoteFailure(botID, consecutiveErrors, err.Error())
			m.emitOutageAlertIfDue()
			select {
			case <-ctx.Done():
				return
			case <-time.After(backoff):
			}
			backoff = min(backoff*2, maxBackoff)
			continue
		}

		if consecutiveErrors > 0 {
			slog.Info("GetUpdates recovered after errors",
				"bot_id", botID,
				"previous_consecutive_errors", consecutiveErrors,
			)
			if sum := m.outage.NoteSuccess(botID); sum != nil {
				slog.Info("Telegram GetUpdates outage recovered",
					"affected_bots", strings.Join(sum.Affected, ","),
					"duration", sum.Duration.Round(time.Second).String(),
					alert.NotifyKey, true,
				)
			}
		}
		consecutiveErrors = 0
		backoff = 2 * time.Second

		for _, update := range updates {
			if update.UpdateID >= params.Offset {
				params.Offset = update.UpdateID + 1
				handle(update)
			}
		}
	}
}

// emitOutageAlertIfDue sends the aggregated GetUpdates outage alert when one
// is due. This Error log is the only GetUpdates failure that reaches the
// alert channel; per-bot failures log at Warn.
func (m *Manager) emitOutageAlertIfDue() {
	if sum := m.outage.Flush(); sum != nil {
		slog.Error("Telegram GetUpdates outage",
			"affected_bots", strings.Join(sum.Affected, ","),
			"bot_count", len(sum.Affected),
			"duration", sum.Duration.Round(time.Second).String(),
			"sample_error", sum.LastErr,
		)
	}
}

// slogTelegoLogger routes telego's internal log lines into slog. Errors map
// to Warn: telego-internal failures (API call errors it would retry anyway)
// must not page by themselves — pollUpdates decides what becomes an alert.
type slogTelegoLogger struct {
	botID string
}

func (l slogTelegoLogger) Debugf(format string, args ...any) {
	slog.Debug("telego: "+fmt.Sprintf(format, args...), "bot_id", l.botID)
}

func (l slogTelegoLogger) Errorf(format string, args ...any) {
	slog.Warn("telego: "+fmt.Sprintf(format, args...), "bot_id", l.botID)
}
