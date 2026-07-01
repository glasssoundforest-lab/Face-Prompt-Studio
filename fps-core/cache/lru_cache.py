"""
fps-core/cache/lru_cache.py — LRU キャッシュ実装

スレッドセーフな LRU（Least Recently Used）キャッシュ。
TTL（Time To Live）もサポートする。
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any

from .models import CacheEntry, CacheStats


class LRUCache:
    """
    スレッドセーフ LRU キャッシュ。

    使い方:
        c = LRUCache(max_size=256, default_ttl=3600)
        c.set("key", value)
        val = c.get("key")    # None なら miss
    """

    def __init__(self, max_size: int = 256, default_ttl: float = 0.0) -> None:
        if max_size <= 0:
            raise ValueError(f"max_size must be > 0, got {max_size}")
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # ── 基本操作 ──────────────────────────────────────────────────

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None
            entry = self._store[key]
            if entry.is_expired:
                del self._store[key]
                self._misses += 1
                return None
            entry.touch()
            self._store.move_to_end(key)   # LRU 更新
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            effective_ttl = ttl if ttl is not None else self._default_ttl
            entry = CacheEntry(key=key, value=value, ttl=effective_ttl)
            if key in self._store:
                del self._store[key]
            self._store[key] = entry
            self._store.move_to_end(key)
            # 容量超過なら最古エントリを削除
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)
                self._evictions += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def has(self, key: str) -> bool:
        with self._lock:
            if key not in self._store:
                return False
            if self._store[key].is_expired:
                del self._store[key]
                return False
            return True

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    # ── 統計 / ユーティリティ ─────────────────────────────────────

    def evict_expired(self) -> int:
        with self._lock:
            expired = [k for k, e in self._store.items() if e.is_expired]
            for k in expired:
                del self._store[k]
            return len(expired)

    def statistics(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                size=len(self._store),
                max_size=self._max_size,
            )

    def reset_stats(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    @property
    def keys(self) -> list[str]:
        with self._lock:
            return list(self._store.keys())

    def __len__(self) -> int:
        return self.size

    def __repr__(self) -> str:
        return (
            f"LRUCache(max_size={self._max_size}, "
            f"size={self.size}, default_ttl={self._default_ttl})"
        )
