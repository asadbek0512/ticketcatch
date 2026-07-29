"""Per-user cooldown for expensive actions.

A live search drives four sites and a browser. Left unguarded, one person holding down 🔍 can
occupy every browser slot and make the bot look dead to everyone else, without meaning any harm.
The cooldown is in memory on purpose: it guards this process's capacity, so it should reset when
the process does."""

import time

PRUNE_AT = 5_000  # entries; the map only exists to answer "how long ago", so old keys are junk


class Cooldown:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self._last: dict[str, float] = {}

    def remaining(self, key: str) -> int:
        """Seconds the caller still has to wait; 0 means go ahead."""
        if self.seconds <= 0:
            return 0
        left = self.seconds - (time.monotonic() - self._last.get(key, -self.seconds))
        return max(0, round(left))

    def hit(self, key: str) -> None:
        """Record a use. Call it when the action starts, so a slow action can't be double-fired."""
        if len(self._last) >= PRUNE_AT:
            cutoff = time.monotonic() - self.seconds
            self._last = {k: t for k, t in self._last.items() if t > cutoff}
        self._last[key] = time.monotonic()

    def clear(self, key: str) -> None:
        self._last.pop(key, None)
