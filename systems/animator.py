"""Time-based animation envelopes for the render layer.

The animator stores one entry per active animation, keyed by string id.
Each entry is `(start_ms, duration_ms, ease_fn)`. The renderer queries
`eased(id)` on read; nothing internal ticks per frame. Polling means
restarts are trivial — overwrite the entry — and animations are a pure
function of wall clock minus start time.

Clock is injectable so tests can drive it without touching `pygame.time`
(the test harness stubs all of `pygame`)."""

from typing import Callable


_EASINGS: dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "out_cubic": lambda t: 1 - (1 - t) ** 3,
    "out_quart": lambda t: 1 - (1 - t) ** 4,
    "in_out_cubic": lambda t: 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2,
}


class Animator:
    def __init__(self, clock: Callable[[], int] | None = None):
        if clock is None:
            import pygame
            clock = pygame.time.get_ticks
        self.clock = clock
        self.entries: dict[str, tuple[int, int, Callable[[float], float]]] = {}
        self.enabled: bool = True

    def start(self, anim_id: str, duration_ms: int, easing: str = "out_cubic") -> None:
        """No-op if `anim_id` is already running. Use `restart` to override.
        Idempotency lets render code call `start` freely without worrying
        about double-fires."""
        if anim_id in self.entries:
            start, dur, _ = self.entries[anim_id]
            if self.clock() - start < dur:
                return
        self.entries[anim_id] = (self.clock(), duration_ms, _EASINGS[easing])

    def restart(self, anim_id: str, duration_ms: int, easing: str = "out_cubic") -> None:
        """Force-reset an animation, even if it's currently running."""
        self.entries[anim_id] = (self.clock(), duration_ms, _EASINGS[easing])

    def finish(self, anim_id: str) -> None:
        """Snap an animation to its final frame (used to skip score staging
        when the player clicks during the reveal)."""
        entry = self.entries.get(anim_id)
        if entry is None:
            return
        _, dur, ease = entry
        self.entries[anim_id] = (self.clock() - dur, dur, ease)

    def eased(self, anim_id: str) -> float:
        """Eased 0..1 progress. Returns 1.0 when the animation is not
        registered, has finished, or animations are globally disabled."""
        if not self.enabled:
            return 1.0
        entry = self.entries.get(anim_id)
        if entry is None:
            return 1.0
        start, dur, ease = entry
        if dur <= 0:
            return 1.0
        t = min(1.0, (self.clock() - start) / dur)
        return ease(t)

    def progress(self, anim_id: str) -> float:
        """Linear 0..1 progress without easing."""
        if not self.enabled:
            return 1.0
        entry = self.entries.get(anim_id)
        if entry is None:
            return 1.0
        start, dur, _ = entry
        if dur <= 0:
            return 1.0
        return min(1.0, (self.clock() - start) / dur)

    def is_active(self, anim_id: str) -> bool:
        if not self.enabled:
            return False
        entry = self.entries.get(anim_id)
        if entry is None:
            return False
        start, dur, _ = entry
        return self.clock() - start < dur

    def gc(self) -> None:
        """Drop finished animations. Call once per frame at the top of
        `draw()`. O(N) over the active set — usually <20 entries."""
        now = self.clock()
        self.entries = {
            k: v for k, v in self.entries.items() if now - v[0] < v[1]
        }
