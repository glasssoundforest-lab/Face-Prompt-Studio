"""
fps-core/cache/models.py — キャッシュデータモデル
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """キャッシュエントリ 1 件"""

    key: str
    value: Any
    ttl: float = 0.0          # 0.0 = 無期限
    hit_count: int = 0
    _created_at: float = field(default_factory=time.monotonic, repr=False)

    @property
    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return time.monotonic() - self._created_at >= self.ttl

    def touch(self) -> None:
        self.hit_count += 1


@dataclass
class CacheStats:
    """キャッシュ統計情報"""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "miss_rate": round(self.miss_rate, 4),
            "evictions": self.evictions,
            "size": self.size,
            "max_size": self.max_size,
        }
