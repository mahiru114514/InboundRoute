"""缓存与调用预算（C4）。"""
from __future__ import annotations

import threading
import time


class TTLCache:
    """内存 TTL 缓存。key -> (expires, value)。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._store = {}
        self._hits = 0
        self._misses = 0

    def get(self, key):
        with self._lock:
            item = self._store.get(key)
            if item is None:
                self._misses += 1
                return None, False
            expires, value = item
            if time.time() > expires:
                self._store.pop(key, None)
                self._misses += 1
                return None, False
            self._hits += 1
            return value, True

    def set(self, key, value, ttl_seconds):
        with self._lock:
            self._store[key] = (time.time() + ttl_seconds, value)

    def stats(self):
        with self._lock:
            return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}


class CallBudget:
    """一次拖拽/重算的三方调用预算（cache_keys.call_budget）。"""

    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self._count = 0
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """返回是否允许再发起一次三方调用。"""
        with self._lock:
            if self._count >= self.max_calls:
                return False
            self._count += 1
            return True

    @property
    def used(self) -> int:
        with self._lock:
            return self._count