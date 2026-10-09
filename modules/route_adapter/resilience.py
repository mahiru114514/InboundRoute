"""重试 / 熔断 / 幂等（C5 + errors.json）。纯标准库。"""
from __future__ import annotations

import threading
import time


class RetryPolicy:
    """connect 1s / read 2s；重试 <=2 次（300ms、800ms 退避）；429 不重试。"""

    def __init__(self, max_retries=2, backoff_ms=(300, 800), connect_timeout=1.0, read_timeout=2.0):
        self.max_retries = max_retries
        self.backoff_ms = list(backoff_ms)
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout


class CircuitBreaker:
    """错误率 >50%（30s 窗口）熔断 5s；熔断结束进入半开探测。"""

    def __init__(self, error_rate_threshold=0.5, window_seconds=30.0, open_seconds=5.0):
        self.threshold = error_rate_threshold
        self.window_seconds = window_seconds
        self.open_seconds = open_seconds
        self._lock = threading.Lock()
        self._events = []  # [(timestamp, is_error)]
        self._opened_at = None

    def _prune(self, now):
        cutoff = now - self.window_seconds
        self._events = [e for e in self._events if e[0] >= cutoff]

    def record(self, is_error: bool):
        now = time.monotonic()
        with self._lock:
            self._events.append((now, bool(is_error)))
            self._prune(now)
            if self._opened_at is None:
                total = len(self._events)
                errors = sum(1 for _, err in self._events if err)
                if total >= 2 and errors / total > self.threshold:
                    self._opened_at = now

    def allow(self) -> bool:
        """True=允许调用；False=熔断打开（跳过真实三方调用）。"""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            if self._opened_at is None:
                return True
            if now - self._opened_at >= self.open_seconds:
                # 半开：允许一次探测
                self._opened_at = None
                return True
            return False

    @property
    def state(self) -> str:
        with self._lock:
            if self._opened_at is None:
                return "closed"
            return "open"


class IdempotencyStore:
    """Idempotency-Key 24h 窗口：重放返回首次结果，不重复调用三方。"""

    def __init__(self, window_hours=24):
        self.window_seconds = window_hours * 3600
        self._lock = threading.Lock()
        self._store = {}

    def get(self, key):
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires, value = item
            if time.time() > expires:
                self._store.pop(key, None)
                return None
            return value

    def put(self, key, value):
        with self._lock:
            self._store[key] = (time.time() + self.window_seconds, value)

    def __len__(self):
        with self._lock:
            return len(self._store)