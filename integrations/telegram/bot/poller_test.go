package bot

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/mymmrac/telego"

	"github.com/crestalnetwork/intentkit/integrations/shared/outage"
)

// fakeFetcher scripts GetUpdates responses; calls beyond the script block
// until the context is cancelled, like a quiet long poll.
type fakeFetcher struct {
	mu     sync.Mutex
	calls  []telego.GetUpdatesParams
	script []func() ([]telego.Update, error)
}

func (f *fakeFetcher) GetUpdates(ctx context.Context, params *telego.GetUpdatesParams) ([]telego.Update, error) {
	f.mu.Lock()
	i := len(f.calls)
	f.calls = append(f.calls, *params)
	f.mu.Unlock()
	if i < len(f.script) {
		return f.script[i]()
	}
	<-ctx.Done()
	return nil, ctx.Err()
}

func (f *fakeFetcher) callParams(i int) telego.GetUpdatesParams {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.calls[i]
}

func newTestManager() *Manager {
	return &Manager{outage: outage.NewTracker()}
}

func TestPollUpdatesDispatchesAndAdvancesOffset(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	upd := func(id int) telego.Update { return telego.Update{UpdateID: id} }
	fetcher := &fakeFetcher{script: []func() ([]telego.Update, error){
		func() ([]telego.Update, error) { return []telego.Update{upd(1), upd(2)}, nil },
		// A stale duplicate (ID 2 again) must be skipped, ID 3 dispatched.
		func() ([]telego.Update, error) { return []telego.Update{upd(2), upd(3)}, nil },
		func() ([]telego.Update, error) { cancel(); return nil, context.Canceled },
	}}

	var handled []int
	done := make(chan struct{})
	go func() {
		defer close(done)
		newTestManager().pollUpdates(ctx, fetcher, "bot1", func(u telego.Update) {
			handled = append(handled, u.UpdateID)
		})
	}()

	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("pollUpdates did not exit after context cancel")
	}

	want := []int{1, 2, 3}
	if len(handled) != len(want) {
		t.Fatalf("handled = %v, want %v", handled, want)
	}
	for i := range want {
		if handled[i] != want[i] {
			t.Fatalf("handled = %v, want %v", handled, want)
		}
	}
	if got := fetcher.callParams(1).Offset; got != 3 {
		t.Fatalf("second call offset = %d, want 3 (after IDs 1,2)", got)
	}
	if got := fetcher.callParams(2).Offset; got != 4 {
		t.Fatalf("third call offset = %d, want 4 (after ID 3)", got)
	}
}

func TestPollUpdatesExitsDuringErrorBackoff(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())

	fetcher := &fakeFetcher{script: []func() ([]telego.Update, error){
		func() ([]telego.Update, error) {
			// Cancel while pollUpdates is about to enter its backoff wait.
			go cancel()
			return nil, errors.New("telegram: bad gateway")
		},
	}}

	done := make(chan struct{})
	go func() {
		defer close(done)
		newTestManager().pollUpdates(ctx, fetcher, "bot1", func(telego.Update) {
			t.Error("no updates expected")
		})
	}()

	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("pollUpdates did not exit promptly when cancelled during backoff")
	}
}
