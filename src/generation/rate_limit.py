"""Thread-safe, actual-start-time global request pacing for one HCX generator instance."""
import threading
import time


class GlobalMinIntervalLimiter:
    def __init__(
        self,
        minimum_interval_seconds,
        *,
        guard_seconds=0.0,
        clock=time.monotonic,
        sleeper=time.sleep,
    ):
        self.minimum_interval_seconds = minimum_interval_seconds
        self.guard_seconds = guard_seconds
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0

    def acquire(self):
        """Wait until an actual request start is safe, even after an early wake-up.

        The lock intentionally covers the wait. This serializes all callers at the
        moment a request may start; merely reserving a future slot before sleeping
        does not guarantee a real request-start interval on every OS scheduler.
        """
        with self._lock:
            started_at = self._clock()
            while True:
                now = self._clock()
                remaining = self._next_allowed_at - now
                if remaining <= 0:
                    actual_start = self._clock()
                    self._next_allowed_at = actual_start + self.minimum_interval_seconds + self.guard_seconds
                    return actual_start - started_at
                self._sleeper(remaining)
