"""
fps-core/cache/manager.py — CacheManager

名前空間別の LRU キャッシュを管理するファサード。
パイプラインや辞書ルックアップの高速化に使用する。

Public API:
  - get(namespace, key)          → value | None
  - set(namespace, key, value)
  - has(namespace, key)          → bool
  - delete(namespace, key)       → bool
  - clear(namespace=None)
  - get_lookup / set_lookup      辞書ルックアップ用ショートカット
  - get_prompt / set_prompt      プロンプトキャッシュ用ショートカット
  - statistics()                 → dict
  - evict_expired()              → int
  - from_config(config)          → CacheManager
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from .key_builder import build_lookup_key, build_prompt_key
from .lru_cache import LRUCache
from .models import CacheStats

if TYPE_CHECKING:
    pass


class CacheManager:
    """
    名前空間別 LRU キャッシュ管理クラス。

    使い方:
        cm = CacheManager(max_size=256, default_ttl=3600)
        cm.set("lookup", "blue_eyes", {"resolved": "Eyes.Blue"})
        result = cm.get("lookup", "blue_eyes")
    """

    def __init__(
        self,
        max_size: int = 256,
        default_ttl: float = 0.0,
        enabled: bool = True,
    ) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._enabled = enabled
        self._namespaces: dict[str, LRUCache] = {}
        self._lock = threading.RLock()

    # ── 名前空間管理 ──────────────────────────────────────────────

    def _get_ns(self, namespace: str) -> LRUCache:
        with self._lock:
            if namespace not in self._namespaces:
                self._namespaces[namespace] = LRUCache(
                    max_size=self._max_size,
                    default_ttl=self._default_ttl,
                )
            return self._namespaces[namespace]

    # ── 基本操作 ──────────────────────────────────────────────────

    def get(self, namespace: str, key: str) -> Any | None:
        if not self._enabled:
            return None
        return self._get_ns(namespace).get(key)

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: float | None = None,
    ) -> None:
        if not self._enabled:
            return
        self._get_ns(namespace).set(key, value, ttl=ttl)

    def has(self, namespace: str, key: str) -> bool:
        if not self._enabled:
            return False
        with self._lock:
            if namespace not in self._namespaces:
                return False
        return self._get_ns(namespace).has(key)

    def delete(self, namespace: str, key: str) -> bool:
        with self._lock:
            if namespace not in self._namespaces:
                return False
        return self._namespaces[namespace].delete(key)

    def clear(self, namespace: str | None = None) -> None:
        with self._lock:
            if namespace is None:
                for ns in self._namespaces.values():
                    ns.clear()
            elif namespace in self._namespaces:
                self._namespaces[namespace].clear()

    # ── ショートカット（辞書ルックアップ） ───────────────────────

    def get_lookup(self, tag: str) -> Any | None:
        return self.get("lookup", build_lookup_key(tag))

    def set_lookup(self, tag: str, value: Any, ttl: float | None = None) -> None:
        self.set("lookup", build_lookup_key(tag), value, ttl=ttl)

    # ── ショートカット（プロンプトキャッシュ） ──────────────────

    def get_prompt(self, prompt: str) -> Any | None:
        return self.get("prompt", build_prompt_key(prompt))

    def set_prompt(self, prompt: str, value: Any, ttl: float | None = None) -> None:
        self.set("prompt", build_prompt_key(prompt), value, ttl=ttl)

    # ── 統計 / 有効化 ─────────────────────────────────────────────

    def evict_expired(self) -> int:
        total = 0
        with self._lock:
            namespaces = list(self._namespaces.values())
        for ns in namespaces:
            total += ns.evict_expired()
        return total

    def statistics(self) -> dict[str, Any]:
        total = CacheStats()
        ns_stats: dict[str, dict] = {}
        with self._lock:
            items = list(self._namespaces.items())
        for name, ns in items:
            s = ns.statistics()
            total.hits += s.hits
            total.misses += s.misses
            total.evictions += s.evictions
            total.size += s.size
            ns_stats[name] = s.to_dict()
        total.max_size = self._max_size
        result = total.to_dict()
        result["namespaces"] = ns_stats
        result["enabled"] = self._enabled
        return result

    def reset_stats(self) -> None:
        with self._lock:
            for ns in self._namespaces.values():
                ns.reset_stats()

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def namespace_names(self) -> list[str]:
        with self._lock:
            return list(self._namespaces.keys())

    # ── コンストラクタ ────────────────────────────────────────────

    @classmethod
    def from_config(cls, config: Any) -> CacheManager:
        """ConfigManager からインスタンスを生成する。"""
        max_size = int(config.get("cache.max_size", 256))
        ttl = float(config.get("cache.ttl", 0.0))
        enabled = bool(config.get("cache.enabled", True))
        return cls(max_size=max_size, default_ttl=ttl, enabled=enabled)

    def __repr__(self) -> str:
        return (
            f"CacheManager(max_size={self._max_size}, "
            f"enabled={self._enabled}, "
            f"namespaces={list(self._namespaces.keys())})"
        )
