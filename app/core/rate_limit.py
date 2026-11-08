from collections import deque
from threading import Lock
from time import monotonic

class RateLimiter:
    """Single-user, single-process sliding window; no per-IP unbounded storage."""
    def __init__(self, capacity, clock=monotonic):
        self.capacity, self.clock = capacity, clock
        self.events = deque()
        self.lock = Lock()

    def allow(self):
        with self.lock:
            now = self.clock()
            while self.events and self.events[0] <= now - 60:
                self.events.popleft()
            if len(self.events) >= self.capacity:
                return False
            self.events.append(now)
            return True
