"""Login throttle: bounded, thread-safe, in-process.

Two limits per sliding window: failures per (username, client address) and failures per client
address across all usernames (stops one address from spraying many usernames). A different address
is never affected, so nobody can lock a user out from elsewhere. Memory is capped (oldest entries
are dropped first). State lives in this process only: it resets on restart and is not shared
between workers.
"""
import math
import threading
import time
from collections import OrderedDict


class LoginThrottle:
    def __init__(self, max_failures=5, max_ip_failures=20, window=300, max_entries=10000, clock=time.time):
        self.max_failures, self.max_ip_failures = max_failures, max_ip_failures
        self.window, self.max_entries, self.clock = window, max_entries, clock
        self._data, self._lock = OrderedDict(), threading.Lock()

    def _recent(self, key, now):
        return [t for t in self._data.get(key, ()) if now - t < self.window]

    def retry_after(self, name, ip):
        """Seconds the caller must wait (0 = allowed)."""
        now, wait = self.clock(), 0
        with self._lock:
            for key, limit in ((("u", name, ip), self.max_failures), (("i", ip), self.max_ip_failures)):
                recent = self._recent(key, now)
                if len(recent) >= limit:
                    wait = max(wait, math.ceil(recent[-limit] + self.window - now))
        return max(wait, 0)

    def record_failure(self, name, ip):
        now = self.clock()
        with self._lock:
            for key in (("u", name, ip), ("i", ip)):
                self._data[key] = self._recent(key, now) + [now]
                self._data.move_to_end(key)
            while self._data and (len(self._data) > self.max_entries
                                  or now - next(iter(self._data.values()))[-1] >= self.window):
                self._data.popitem(last=False)      # oldest-updated first: expired, then over the cap

    def clear(self, name, ip):
        """Successful sign-in forgets that user's failures (the address-wide count is kept)."""
        with self._lock:
            self._data.pop(("u", name, ip), None)
