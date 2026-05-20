"""Tests for systems/animator.py — driven by an injected clock so they
don't need real time (or real pygame)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from systems.animator import Animator, _EASINGS


class FakeClock:
    """Settable monotonic clock for animation tests."""
    def __init__(self, t: int = 0):
        self.t = t

    def __call__(self) -> int:
        return self.t


class TestAnimatorBasics:
    def test_start_records_entry(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        assert "x" in a.entries

    def test_eased_zero_at_start(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        assert a.eased("x") == pytest.approx(0.0, abs=1e-6)

    def test_eased_one_at_end(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        c.t = 100
        assert a.eased("x") == pytest.approx(1.0)

    def test_eased_clamps_past_end(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        c.t = 500
        assert a.eased("x") == pytest.approx(1.0)

    def test_eased_unknown_id_returns_one(self):
        """Render code asks for animations that may not exist — must not
        crash, must return 1.0 (i.e. 'finished, no effect')."""
        a = Animator(clock=FakeClock(0))
        assert a.eased("nope") == 1.0

    def test_progress_linear_independent_of_easing(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100, easing="out_cubic")
        c.t = 50
        assert a.progress("x") == pytest.approx(0.5)
        # eased value is past 0.5 because out_cubic is concave.
        assert a.eased("x") > 0.5


class TestIdempotentStart:
    def test_start_is_no_op_when_active(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        c.t = 50
        # Second start at mid-animation must NOT reset the start time.
        a.start("x", 100)
        assert a.eased("x") > 0  # was at ~0.5 before; second start would zero it

    def test_restart_overwrites_active(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        c.t = 50
        a.restart("x", 100)
        assert a.eased("x") == pytest.approx(0.0, abs=1e-6)

    def test_start_after_finish_creates_fresh_entry(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        c.t = 200  # past end
        a.start("x", 100)  # animation is finished; this should start a new one
        assert a.eased("x") == pytest.approx(0.0, abs=1e-6)


class TestFinish:
    def test_finish_snaps_to_end(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 1000)
        c.t = 100
        a.finish("x")
        assert a.eased("x") == pytest.approx(1.0)
        assert a.is_active("x") is False

    def test_finish_unknown_id_does_not_crash(self):
        a = Animator(clock=FakeClock(0))
        a.finish("nope")  # should be a no-op


class TestIsActive:
    def test_active_inside_duration(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        c.t = 50
        assert a.is_active("x") is True

    def test_inactive_after_duration(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        c.t = 101
        assert a.is_active("x") is False

    def test_inactive_when_unknown(self):
        a = Animator(clock=FakeClock(0))
        assert a.is_active("nope") is False


class TestGC:
    def test_gc_drops_finished(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        a.start("y", 1000)
        c.t = 200
        a.gc()
        assert "x" not in a.entries
        assert "y" in a.entries

    def test_gc_keeps_running(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        c.t = 50
        a.gc()
        assert "x" in a.entries


class TestEnabledFlag:
    def test_disabled_returns_full_progress(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        a.enabled = False
        assert a.eased("x") == 1.0
        assert a.is_active("x") is False

    def test_re_enabling_resumes_progress(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        a.enabled = False
        a.enabled = True
        c.t = 25
        assert 0.0 < a.eased("x") < 1.0


class TestEasings:
    @pytest.mark.parametrize("name", list(_EASINGS.keys()))
    def test_endpoints(self, name):
        fn = _EASINGS[name]
        assert fn(0.0) == pytest.approx(0.0)
        assert fn(1.0) == pytest.approx(1.0)

    def test_out_cubic_is_concave(self):
        """out_cubic should be above the identity for 0 < t < 1."""
        fn = _EASINGS["out_cubic"]
        for t in (0.1, 0.25, 0.5, 0.75, 0.9):
            assert fn(t) > t

    def test_in_out_cubic_is_symmetric(self):
        fn = _EASINGS["in_out_cubic"]
        # in_out_cubic should pass through 0.5 at t=0.5.
        assert fn(0.5) == pytest.approx(0.5)


class TestMultipleAnimations:
    def test_independent_progress(self):
        c = FakeClock(0)
        a = Animator(clock=c)
        a.start("x", 100)
        c.t = 50
        a.start("y", 100)
        c.t = 100
        # x is finished, y is half-done.
        assert a.eased("x") == pytest.approx(1.0)
        assert 0.0 < a.eased("y") < 1.0
