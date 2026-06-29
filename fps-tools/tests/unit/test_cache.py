"""
fps-tools/tests/unit/test_cache.py

Cache のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_cache.py -v
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))

from cache.key_builder import build_key, build_lookup_key, build_prompt_key
from cache.lru_cache import LRUCache
from cache.manager import CacheManager
from cache.models import CacheEntry, CacheStats


# ══════════════════════════════════════════════════════════════════
# CacheEntry / CacheStats
# ══════════════════════════════════════════════════════════════════

class TestCacheEntry:
    def test_not_expired_when_ttl_zero(self):
        e = CacheEntry(key="k", value="v", ttl=0.0)
        assert e.is_expired is False

    def test_not_expired_within_ttl(self):
        e = CacheEntry(key="k", value="v", ttl=60.0)
        assert e.is_expired is False

    def test_expired_after_ttl(self):
        e = CacheEntry(key="k", value="v", ttl=0.01)
        time.sleep(0.05)
        assert e.is_expired is True

    def test_touch_increments_hit_count(self):
        e = CacheEntry(key="k", value="v")
        e.touch()
        e.touch()
        assert e.hit_count == 2


class TestCacheStats:
    def test_hit_rate_zero_when_no_requests(self):
        s = CacheStats()
        assert s.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        s = CacheStats(hits=3, misses=1)
        assert s.hit_rate == pytest.approx(0.75)

    def test_miss_rate_calculation(self):
        s = CacheStats(hits=3, misses=1)
        assert s.miss_rate == pytest.approx(0.25)

    def test_to_dict_keys(self):
        s = CacheStats(hits=10, misses=5)
        d = s.to_dict()
        for k in ("hits", "misses", "hit_rate", "miss_rate", "size", "max_size"):
            assert k in d


# ══════════════════════════════════════════════════════════════════
# LRUCache
# ══════════════════════════════════════════════════════════════════

class TestLRUCache:
    def test_set_and_get(self):
        c = LRUCache(max_size=10)
        c.set("k", "v")
        assert c.get("k") == "v"

    def test_get_miss_returns_none(self):
        c = LRUCache(max_size=10)
        assert c.get("missing") is None

    def test_max_size_evicts_oldest(self):
        c = LRUCache(max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.set("d", 4)   # "a" が追い出される
        assert c.get("a") is None
        assert c.get("b") == 2
        assert c.get("d") == 4

    def test_lru_access_updates_order(self):
        c = LRUCache(max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.get("a")       # "a" をアクセスして最新に
        c.set("d", 4)    # "b" が最古になって追い出される
        assert c.get("a") == 1
        assert c.get("b") is None

    def test_delete_existing(self):
        c = LRUCache(max_size=10)
        c.set("k", "v")
        assert c.delete("k") is True
        assert c.get("k") is None

    def test_delete_nonexistent(self):
        c = LRUCache(max_size=10)
        assert c.delete("ghost") is False

    def test_has_existing(self):
        c = LRUCache(max_size=10)
        c.set("k", "v")
        assert c.has("k") is True

    def test_has_missing(self):
        c = LRUCache(max_size=10)
        assert c.has("ghost") is False

    def test_clear(self):
        c = LRUCache(max_size=10)
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.size == 0

    def test_update_existing_key(self):
        c = LRUCache(max_size=10)
        c.set("k", "old")
        c.set("k", "new")
        assert c.get("k") == "new"
        assert c.size == 1

    def test_ttl_expiration(self):
        c = LRUCache(max_size=10, default_ttl=0.05)
        c.set("k", "v")
        assert c.get("k") == "v"
        time.sleep(0.1)
        assert c.get("k") is None

    def test_ttl_per_entry(self):
        c = LRUCache(max_size=10, default_ttl=0.0)
        c.set("short", "v", ttl=0.05)
        c.set("long",  "v", ttl=60.0)
        time.sleep(0.1)
        assert c.get("short") is None
        assert c.get("long")  == "v"

    def test_evict_expired(self):
        c = LRUCache(max_size=10, default_ttl=0.05)
        c.set("a", 1)
        c.set("b", 2)
        time.sleep(0.1)
        count = c.evict_expired()
        assert count == 2
        assert c.size == 0

    def test_statistics_hit_rate(self):
        c = LRUCache(max_size=10)
        c.set("k", "v")
        c.get("k")       # hit
        c.get("ghost")   # miss
        s = c.statistics()
        assert s.hits   == 1
        assert s.misses == 1
        assert s.hit_rate == pytest.approx(0.5)

    def test_statistics_evictions(self):
        c = LRUCache(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)    # 1 eviction
        s = c.statistics()
        assert s.evictions == 1

    def test_invalid_max_size_raises(self):
        with pytest.raises(ValueError):
            LRUCache(max_size=0)

    def test_len(self):
        c = LRUCache(max_size=10)
        c.set("a", 1)
        c.set("b", 2)
        assert len(c) == 2

    def test_keys(self):
        c = LRUCache(max_size=10)
        c.set("a", 1)
        c.set("b", 2)
        assert set(c.keys) == {"a", "b"}

    def test_repr(self):
        c = LRUCache(max_size=10)
        assert "LRUCache" in repr(c)

    def test_reset_stats(self):
        c = LRUCache(max_size=10)
        c.set("k", "v")
        c.get("k")
        c.reset_stats()
        s = c.statistics()
        assert s.hits == 0


# ══════════════════════════════════════════════════════════════════
# key_builder
# ══════════════════════════════════════════════════════════════════

class TestKeyBuilder:
    def test_build_key_format(self):
        k = build_key("lookup", "masterpiece")
        assert k.startswith("lookup:")
        assert len(k) > 8

    def test_build_key_deterministic(self):
        k1 = build_key("lookup", "masterpiece")
        k2 = build_key("lookup", "masterpiece")
        assert k1 == k2

    def test_build_key_different_args(self):
        k1 = build_key("ns", "a")
        k2 = build_key("ns", "b")
        assert k1 != k2

    def test_build_key_different_namespaces(self):
        k1 = build_key("ns1", "x")
        k2 = build_key("ns2", "x")
        assert k1 != k2

    def test_build_prompt_key_normalizes_whitespace(self):
        k1 = build_prompt_key("hello   world")
        k2 = build_prompt_key("hello world")
        assert k1 == k2

    def test_build_lookup_key_lowercase(self):
        k1 = build_lookup_key("MASTERPIECE")
        k2 = build_lookup_key("masterpiece")
        assert k1 == k2

    def test_build_key_with_kwargs(self):
        k1 = build_key("ns", x=1, y=2)
        k2 = build_key("ns", x=1, y=2)
        k3 = build_key("ns", x=1, y=9)
        assert k1 == k2
        assert k1 != k3


# ══════════════════════════════════════════════════════════════════
# CacheManager
# ══════════════════════════════════════════════════════════════════

class TestCacheManager:
    def test_set_and_get(self):
        cm = CacheManager(max_size=10)
        cm.set("ns", "k", "v")
        assert cm.get("ns", "k") == "v"

    def test_get_miss(self):
        cm = CacheManager(max_size=10)
        assert cm.get("ns", "ghost") is None

    def test_has(self):
        cm = CacheManager(max_size=10)
        cm.set("ns", "k", "v")
        assert cm.has("ns", "k") is True
        assert cm.has("ns", "x") is False

    def test_delete(self):
        cm = CacheManager(max_size=10)
        cm.set("ns", "k", "v")
        assert cm.delete("ns", "k") is True
        assert cm.get("ns", "k") is None

    def test_delete_nonexistent_namespace(self):
        cm = CacheManager(max_size=10)
        assert cm.delete("ghost_ns", "k") is False

    def test_clear_namespace(self):
        cm = CacheManager(max_size=10)
        cm.set("ns1", "k", "v")
        cm.set("ns2", "k", "v")
        cm.clear("ns1")
        assert cm.get("ns1", "k") is None
        assert cm.get("ns2", "k") == "v"

    def test_clear_all(self):
        cm = CacheManager(max_size=10)
        cm.set("ns1", "k", "v")
        cm.set("ns2", "k", "v")
        cm.clear()
        assert cm.get("ns1", "k") is None
        assert cm.get("ns2", "k") is None

    def test_disabled_returns_none(self):
        cm = CacheManager(max_size=10, enabled=False)
        cm.set("ns", "k", "v")
        assert cm.get("ns", "k") is None

    def test_enable_disable(self):
        cm = CacheManager(max_size=10, enabled=False)
        cm.enable()
        cm.set("ns", "k", "v")
        assert cm.get("ns", "k") == "v"
        cm.disable()
        assert cm.get("ns", "k") is None

    def test_multiple_namespaces(self):
        cm = CacheManager(max_size=10)
        cm.set("lookup", "k", "lookup_val")
        cm.set("prompt", "k", "prompt_val")
        assert cm.get("lookup", "k") == "lookup_val"
        assert cm.get("prompt", "k") == "prompt_val"

    def test_lookup_shortcuts(self):
        cm = CacheManager(max_size=10)
        cm.set_lookup("masterpiece", {"resolved": "Quality.High"})
        result = cm.get_lookup("masterpiece")
        assert result == {"resolved": "Quality.High"}

    def test_prompt_shortcuts(self):
        cm = CacheManager(max_size=10)
        cm.set_prompt("(masterpiece)", {"output": "Quality.High"})
        result = cm.get_prompt("(masterpiece)")
        assert result == {"output": "Quality.High"}

    def test_prompt_whitespace_normalized(self):
        cm = CacheManager(max_size=10)
        cm.set_prompt("hello  world", "v")
        assert cm.get_prompt("hello world") == "v"

    def test_evict_expired(self):
        cm = CacheManager(max_size=10, default_ttl=0.05)
        cm.set("ns", "k", "v")
        time.sleep(0.1)
        count = cm.evict_expired()
        assert count >= 1

    def test_statistics_structure(self):
        cm = CacheManager(max_size=10)
        cm.set("ns", "k", "v")
        cm.get("ns", "k")    # hit
        cm.get("ns", "x")    # miss
        stats = cm.statistics()
        assert stats["hits"]   == 1
        assert stats["misses"] == 1
        assert "namespaces"    in stats

    def test_from_config(self):
        sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))
        from config.manager import ConfigManager
        cfg = ConfigManager()
        cfg.set("cache.max_size", 128)
        cfg.set("cache.ttl",      1800)
        cfg.set("cache.enabled",  True)
        cm = CacheManager.from_config(cfg)
        assert cm._max_size    == 128
        assert cm._default_ttl == 1800.0
        assert cm.is_enabled   is True

    def test_namespace_names(self):
        cm = CacheManager(max_size=10)
        cm.set("alpha", "k", "v")
        cm.set("beta",  "k", "v")
        assert "alpha" in cm.namespace_names
        assert "beta"  in cm.namespace_names

    def test_repr(self):
        cm = CacheManager(max_size=10)
        assert "CacheManager" in repr(cm)

    def test_reset_stats(self):
        cm = CacheManager(max_size=10)
        cm.set("ns", "k", "v")
        cm.get("ns", "k")
        cm.reset_stats()
        stats = cm.statistics()
        assert stats["hits"] == 0
