"""Thread-safe global request pacing for one HCX generator instance."""
import threading
import time


class GlobalMinIntervalLimiter:
    def __init__(self, minimum_interval_seconds, *, clock=time.monotonic, sleeper=time.sleep):
        self.minimum_interval_seconds = minimum_interval_seconds
        self._clock = clock
        self._sleeper = sleeper
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0

    def acquire(self):
        """Reserve the next global request slot and return the applied wait."""
        with self._lock:
            now = self._clock()
            wait_seconds = max(0.0, self._next_allowed_at - now)
            self._next_allowed_at = max(now, self._next_allowed_at) + self.minimum_interval_seconds
        if wait_seconds:
            self._sleeper(wait_seconds)
        return wait_seconds
