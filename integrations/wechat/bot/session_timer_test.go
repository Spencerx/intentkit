package bot

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

// newTestRedis spins up an in-memory miniredis and returns a connected
// go-redis client plus a cleanup function the test should defer.
func newTestRedis(t *testing.T) (*redis.Client, func()) {
	t.Helper()
	srv, err := miniredis.Run()
	if err != nil {
		t.Fatalf("start miniredis: %v", err)
	}
	client := redis.NewClient(&redis.Options{Addr: srv.Addr()})
	return client, func() {
		_ = client.Close()
		srv.Close()
	}
}

// fireRecorder is a thread-safe FireFunc that records every teamID it is
// invoked with so tests can assert on what fired and when.
type fireRecorder struct {
	mu    sync.Mutex
	calls []string
	wg    sync.WaitGroup
	err   error
}

func (f *fireRecorder) expect(n int) { f.wg.Add(n) }
func (f *fireRecorder) waitDone(d time.Duration) error {
	done := make(chan struct{})
	go func() { f.wg.Wait(); close(done) }()
	select {
	case <-done:
		return nil
	case <-time.After(d):
		return errors.New("timed out waiting for fire")
	}
}
func (f *fireRecorder) fn(_ context.Context, teamID string) error {
	f.mu.Lock()
	f.calls = append(f.calls, teamID)
	f.mu.Unlock()
	f.wg.Done()
	return f.err
}
func (f *fireRecorder) snapshot() []string {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := make([]string, len(f.calls))
	copy(out, f.calls)
	return out
}

func TestSessionTimer_FiresAfterWarnDelay(t *testing.T) {
	client, cleanup := newTestRedis(t)
	defer cleanup()

	rec := &fireRecorder{}
	rec.expect(1)
	mgr := NewSessionTimerManager(nil, client, 600*time.Millisecond, 400*time.Millisecond, rec.fn)
	defer mgr.Stop()

	mgr.OnQualifyingUserMessage(context.Background(), "team-a")

	// warn delay = window - warnBefore = 200ms; allow generous slack for CI.
	if err := rec.waitDone(3 * time.Second); err != nil {
		t.Fatalf("expected fire to run: %v", err)
	}
	got := rec.snapshot()
	if len(got) != 1 || got[0] != "team-a" {
		t.Fatalf("unexpected calls: %v", got)
	}
}

func TestSessionTimer_RefreshCancelsPriorTimer(t *testing.T) {
	client, cleanup := newTestRedis(t)
	defer cleanup()

	var fireCount atomic.Int32
	mgr := NewSessionTimerManager(
		nil, client, 400*time.Millisecond, 300*time.Millisecond,
		func(_ context.Context, _ string) error {
			fireCount.Add(1)
			return nil
		},
	)
	defer mgr.Stop()

	mgr.OnQualifyingUserMessage(context.Background(), "team-b")
	// Refresh well before the first 100ms timer would fire — second
	// message resets the window, so the original schedule must be
	// cancelled. 30ms of slack is comfortably below the 100ms delay even
	// on a slow CI runner.
	time.Sleep(30 * time.Millisecond)
	mgr.OnQualifyingUserMessage(context.Background(), "team-b")

	// Wait long enough that BOTH the original and refreshed delays elapse.
	time.Sleep(250 * time.Millisecond)
	if got := fireCount.Load(); got != 1 {
		t.Fatalf("expected fire to run exactly once after refresh, got %d", got)
	}
}

func TestSessionTimer_SetNXLockPreventsDuplicateFire(t *testing.T) {
	client, cleanup := newTestRedis(t)
	defer cleanup()

	mgr := NewSessionTimerManager(nil, client, 200*time.Millisecond, 150*time.Millisecond, nil)
	defer mgr.Stop()

	now := time.Now()
	if err := mgr.writeRefresh(context.Background(), "team-c", now); err != nil {
		t.Fatalf("writeRefresh: %v", err)
	}
	state, err := mgr.readState(context.Background(), "team-c")
	if err != nil {
		t.Fatalf("readState: %v", err)
	}
	if state == nil || state.LastUserMessageAt != now.UnixMilli() {
		t.Fatalf("unexpected state: %+v", state)
	}

	first, err := mgr.acquireWarnedLock(context.Background(), "team-c", state.LastUserMessageAt)
	if err != nil || !first {
		t.Fatalf("expected first lock acquire to succeed, got ok=%v err=%v", first, err)
	}
	second, err := mgr.acquireWarnedLock(context.Background(), "team-c", state.LastUserMessageAt)
	if err != nil {
		t.Fatalf("second acquire err: %v", err)
	}
	if second {
		t.Fatalf("expected second acquire to fail (already warned)")
	}
}

func TestSessionTimer_RestoreSchedulesRemainingDelay(t *testing.T) {
	client, cleanup := newTestRedis(t)
	defer cleanup()

	rec := &fireRecorder{}
	rec.expect(1)
	mgr := NewSessionTimerManager(nil, client, 600*time.Millisecond, 400*time.Millisecond, rec.fn)
	defer mgr.Stop()

	// Seed state as if the user messaged ~100ms ago. Planned trigger is at
	// window-warnBefore = 200ms after the message; restore should fire
	// after ~100ms — comfortably more than typical CI scheduler jitter so
	// we exercise the "scheduled" path rather than the immediate-fire one.
	past := time.Now().Add(-100 * time.Millisecond)
	if err := mgr.writeRefresh(context.Background(), "team-d", past); err != nil {
		t.Fatalf("seed: %v", err)
	}
	mgr.Restore(context.Background(), []string{"team-d"})

	if err := rec.waitDone(2 * time.Second); err != nil {
		t.Fatalf("expected restored timer to fire: %v", err)
	}
}

func TestSessionTimer_RestoreFiresImmediatelyWhenAlreadyOverdue(t *testing.T) {
	client, cleanup := newTestRedis(t)
	defer cleanup()

	rec := &fireRecorder{}
	rec.expect(1)
	mgr := NewSessionTimerManager(nil, client, 500*time.Millisecond, 200*time.Millisecond, rec.fn)
	defer mgr.Stop()

	// Seed state with the user message at -400ms — already past the
	// planned 300ms trigger but still inside the 500ms window.
	past := time.Now().Add(-400 * time.Millisecond)
	if err := mgr.writeRefresh(context.Background(), "team-e", past); err != nil {
		t.Fatalf("seed: %v", err)
	}
	mgr.Restore(context.Background(), []string{"team-e"})

	if err := rec.waitDone(500 * time.Millisecond); err != nil {
		t.Fatalf("expected immediate fire: %v", err)
	}
}

func TestSessionTimer_RestoreSkipsClosedWindow(t *testing.T) {
	client, cleanup := newTestRedis(t)
	defer cleanup()

	var fireCount atomic.Int32
	mgr := NewSessionTimerManager(
		nil, client, 100*time.Millisecond, 50*time.Millisecond,
		func(_ context.Context, _ string) error {
			fireCount.Add(1)
			return nil
		},
	)
	defer mgr.Stop()

	// Seed state already older than the window — should be skipped.
	long := time.Now().Add(-1 * time.Second)
	if err := mgr.writeRefresh(context.Background(), "team-f", long); err != nil {
		t.Fatalf("seed: %v", err)
	}
	mgr.Restore(context.Background(), []string{"team-f"})

	time.Sleep(150 * time.Millisecond)
	if got := fireCount.Load(); got != 0 {
		t.Fatalf("expected no fire for closed window, got %d", got)
	}
}

func TestSessionTimer_StaleCallbackIsIgnored(t *testing.T) {
	// Simulates the race where the old timer's AfterFunc goroutine begins
	// executing just as a refresh persists a new LastUserMessageAt. The
	// stale callback must NOT acquire the warned lock for the new window.
	client, cleanup := newTestRedis(t)
	defer cleanup()

	var fireCount atomic.Int32
	mgr := NewSessionTimerManager(
		nil, client, time.Hour, 30*time.Minute,
		func(_ context.Context, _ string) error {
			fireCount.Add(1)
			return nil
		},
	)
	defer mgr.Stop()

	// Seed window 1, then refresh to window 2. The "stale" callback then
	// runs with window 1's scheduledForLast — it must be a no-op.
	old := time.Now().Add(-1 * time.Minute)
	if err := mgr.writeRefresh(context.Background(), "team-h", old); err != nil {
		t.Fatalf("seed: %v", err)
	}
	staleScheduledFor := old.UnixMilli()
	mgr.OnQualifyingUserMessage(context.Background(), "team-h") // window 2

	mgr.onTimerFire("team-h", staleScheduledFor)

	if got := fireCount.Load(); got != 0 {
		t.Fatalf("stale callback fired the notice: count=%d", got)
	}
	// And the warned key must NOT have been claimed for window 2 — the
	// real, refreshed timer should still be able to fire when its time
	// comes.
	state, err := mgr.readState(context.Background(), "team-h")
	if err != nil || state == nil {
		t.Fatalf("readState err=%v state=%+v", err, state)
	}
	if state.WarnedFor == state.LastUserMessageAt {
		t.Fatalf("stale callback wrongly marked window 2 as warned")
	}
}

func TestSessionTimer_RestoreSkipsAlreadyWarned(t *testing.T) {
	client, cleanup := newTestRedis(t)
	defer cleanup()

	var fireCount atomic.Int32
	mgr := NewSessionTimerManager(
		nil, client, 300*time.Millisecond, 250*time.Millisecond,
		func(_ context.Context, _ string) error {
			fireCount.Add(1)
			return nil
		},
	)
	defer mgr.Stop()

	now := time.Now()
	if err := mgr.writeRefresh(context.Background(), "team-g", now); err != nil {
		t.Fatalf("seed: %v", err)
	}
	state, err := mgr.readState(context.Background(), "team-g")
	if err != nil || state == nil {
		t.Fatalf("readState err=%v state=%+v", err, state)
	}
	ok, err := mgr.acquireWarnedLock(context.Background(), "team-g", state.LastUserMessageAt)
	if err != nil || !ok {
		t.Fatalf("seed warned lock failed: ok=%v err=%v", ok, err)
	}

	// Restore should see the warned key and skip scheduling.
	mgr.Restore(context.Background(), []string{"team-g"})

	time.Sleep(120 * time.Millisecond)
	if got := fireCount.Load(); got != 0 {
		t.Fatalf("expected no fire for already-warned team, got %d", got)
	}
}
