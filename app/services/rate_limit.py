"""Simple in-memory rate limiter for demo usage."""

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int) -> None:
        self.max_calls = int(max_calls)
        self.window_seconds = int(window_seconds)
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        queue = self._calls[key]
        while queue and now - queue[0] > self.window_seconds:
            queue.popleft()
        if len(queue) >= self.max_calls:
            return False
        queue.append(now)
        return True
