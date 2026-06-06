package bot

import (
	"log/slog"
	"testing"
)

// TestGetUpdatesErrLogLevel pins the graduated log-level behaviour: the first
// few transient failures stay at Warn (a long-poll EOF self-heals on the next
// poll), and only a sustained run escalates to Error.
func TestGetUpdatesErrLogLevel(t *testing.T) {
	tests := []struct {
		consecutiveErrors int
		want              slog.Level
	}{
		{1, slog.LevelWarn},
		{getUpdatesErrLogThreshold - 1, slog.LevelWarn},
		{getUpdatesErrLogThreshold, slog.LevelError},
		{getUpdatesErrLogThreshold + 1, slog.LevelError},
		{100, slog.LevelError},
	}
	for _, tt := range tests {
		if got := getUpdatesErrLogLevel(tt.consecutiveErrors); got != tt.want {
			t.Errorf("getUpdatesErrLogLevel(%d) = %v, want %v",
				tt.consecutiveErrors, got, tt.want)
		}
	}
}
