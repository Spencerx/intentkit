package outage

import (
	"reflect"
	"testing"
	"time"
)

type fakeClock struct{ t time.Time }

func (c *fakeClock) now() time.Time          { return c.t }
func (c *fakeClock) advance(d time.Duration) { c.t = c.t.Add(d) }

func newTestTracker() (*Tracker, *fakeClock) {
	clk := &fakeClock{t: time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)}
	tr := NewTracker()
	tr.now = clk.now
	return tr, clk
}

func TestSubThresholdNeverOpens(t *testing.T) {
	tr, clk := newTestTracker()
	for i := 1; i < FailureThreshold; i++ {
		tr.NoteFailure("a", i, "dial timeout")
	}
	clk.advance(GatherWindow * 2)
	if sum := tr.Flush(); sum != nil {
		t.Fatalf("sub-threshold failures should never alert, got %+v", sum)
	}
	if sum := tr.NoteSuccess("a"); sum != nil {
		t.Fatalf("recovery of a never-failing bot should be silent, got %+v", sum)
	}
}

func TestFirstAlertWaitsForGatherWindow(t *testing.T) {
	tr, clk := newTestTracker()

	tr.NoteFailure("a", FailureThreshold, "dial timeout")
	if sum := tr.Flush(); sum != nil {
		t.Fatalf("alert fired before gather window elapsed: %+v", sum)
	}
	clk.advance(GatherWindow / 2)
	if sum := tr.Flush(); sum != nil {
		t.Fatalf("alert fired before gather window elapsed: %+v", sum)
	}
	clk.advance(GatherWindow / 2)
	sum := tr.Flush()
	if sum == nil {
		t.Fatal("expected first alert once gather window elapsed")
	}
	if !reflect.DeepEqual(sum.Affected, []string{"a"}) {
		t.Fatalf("affected = %v, want [a]", sum.Affected)
	}
	if sum.Duration != GatherWindow {
		t.Fatalf("duration = %v, want %v", sum.Duration, GatherWindow)
	}
	if sum.LastErr != "dial timeout" {
		t.Fatalf("lastErr = %q, want sample error", sum.LastErr)
	}
	if again := tr.Flush(); again != nil {
		t.Fatalf("flush right after alerting must be silent, got %+v", again)
	}
}

func TestCoalescesStaggeredBots(t *testing.T) {
	tr, clk := newTestTracker()

	tr.NoteFailure("b", FailureThreshold, "dial timeout")
	clk.advance(30 * time.Second)
	tr.NoteFailure("a", FailureThreshold, "dial timeout")
	clk.advance(GatherWindow) // past b's pending deadline

	sum := tr.Flush()
	if sum == nil {
		t.Fatal("expected gathered alert")
	}
	if !reflect.DeepEqual(sum.Affected, []string{"a", "b"}) {
		t.Fatalf("affected = %v, want [a b] (sorted, both bots)", sum.Affected)
	}
}

func TestBlipNeverAlerts(t *testing.T) {
	tr, clk := newTestTracker()

	tr.NoteFailure("a", FailureThreshold, "dial timeout")
	clk.advance(30 * time.Second)
	if sum := tr.NoteSuccess("a"); sum != nil {
		t.Fatalf("unalerted blip should produce no recovery notice, got %+v", sum)
	}
	clk.advance(GatherWindow)
	if sum := tr.Flush(); sum != nil {
		t.Fatalf("closed blip must not alert later, got %+v", sum)
	}

	// The next outage starts a fresh gather window rather than inheriting
	// the cancelled one.
	tr.NoteFailure("b", FailureThreshold, "dial timeout")
	if sum := tr.Flush(); sum != nil {
		t.Fatalf("fresh outage alerted immediately: %+v", sum)
	}
	clk.advance(GatherWindow)
	if sum := tr.Flush(); sum == nil {
		t.Fatal("fresh outage should alert after its own gather window")
	}
}

func TestRealertsPeriodically(t *testing.T) {
	tr, clk := newTestTracker()

	tr.NoteFailure("a", FailureThreshold, "dial timeout")
	clk.advance(GatherWindow)
	if tr.Flush() == nil {
		t.Fatal("expected first alert")
	}

	clk.advance(RealertEvery - time.Minute)
	if sum := tr.Flush(); sum != nil {
		t.Fatalf("re-alerted before interval elapsed: %+v", sum)
	}
	clk.advance(time.Minute)
	sum := tr.Flush()
	if sum == nil {
		t.Fatal("expected periodic re-alert")
	}
	if sum.Duration != GatherWindow+RealertEvery {
		t.Fatalf("duration = %v, want %v", sum.Duration, GatherWindow+RealertEvery)
	}
}

func TestRecoveryNoticeAndReset(t *testing.T) {
	tr, clk := newTestTracker()

	tr.NoteFailure("a", FailureThreshold, "dial timeout")
	tr.NoteFailure("b", FailureThreshold, "dial timeout")
	clk.advance(GatherWindow)
	if tr.Flush() == nil {
		t.Fatal("expected first alert")
	}

	clk.advance(10 * time.Minute)
	if sum := tr.NoteSuccess("a"); sum != nil {
		t.Fatalf("recovery notice fired while b still failing: %+v", sum)
	}
	sum := tr.NoteSuccess("b")
	if sum == nil {
		t.Fatal("expected recovery notice when last bot recovers")
	}
	if !reflect.DeepEqual(sum.Affected, []string{"a", "b"}) {
		t.Fatalf("affected = %v, want [a b]", sum.Affected)
	}
	if sum.Duration != GatherWindow+10*time.Minute {
		t.Fatalf("duration = %v, want %v", sum.Duration, GatherWindow+10*time.Minute)
	}

	// Tracker is fully reset for the next outage.
	tr.NoteFailure("a", FailureThreshold, "dial timeout")
	if sum := tr.Flush(); sum != nil {
		t.Fatalf("next outage should gather again, got immediate alert %+v", sum)
	}
	clk.advance(GatherWindow)
	sum = tr.Flush()
	if sum == nil {
		t.Fatal("expected next outage to alert after gather window")
	}
	if !reflect.DeepEqual(sum.Affected, []string{"a"}) {
		t.Fatalf("affected = %v, want [a] (b from prior outage must not leak)", sum.Affected)
	}
}

func TestForgetReleasesStuckBot(t *testing.T) {
	tr, clk := newTestTracker()

	tr.NoteFailure("a", FailureThreshold, "dial timeout")
	tr.NoteFailure("b", FailureThreshold, "dial timeout")
	clk.advance(GatherWindow)
	if tr.Flush() == nil {
		t.Fatal("expected first alert")
	}

	// Bot a's poller is torn down (channel disabled) while still failing;
	// b's later recovery must still close the outage.
	tr.Forget("a")
	sum := tr.NoteSuccess("b")
	if sum == nil {
		t.Fatal("expected recovery notice after forgotten bot released the outage")
	}
	if !reflect.DeepEqual(sum.Affected, []string{"a", "b"}) {
		t.Fatalf("affected = %v, want [a b] (forgotten bot stays in affected)", sum.Affected)
	}
}

func TestForgetLastBotClosesSilently(t *testing.T) {
	tr, clk := newTestTracker()

	tr.NoteFailure("a", FailureThreshold, "dial timeout")
	clk.advance(GatherWindow)
	if tr.Flush() == nil {
		t.Fatal("expected first alert")
	}

	tr.Forget("a")
	clk.advance(RealertEvery)
	if sum := tr.Flush(); sum != nil {
		t.Fatalf("forgotten outage must not re-alert, got %+v", sum)
	}

	// Forgetting an unknown bot is a no-op.
	tr.Forget("ghost")
	if sum := tr.Flush(); sum != nil {
		t.Fatalf("no-op forget must not alert, got %+v", sum)
	}
}
