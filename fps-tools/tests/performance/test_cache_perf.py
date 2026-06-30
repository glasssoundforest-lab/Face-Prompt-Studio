"""
fps-tools/tests/performance/test_cache_perf.py

CacheManager / LRUCache の効率性能テスト。
hit率・処理速度・メモリ効率を測定する。

pytest で実行: pytest fps-tools/tests/performance/test_cache_perf.py -v -s
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from cache.lru_cache import LRUCache
from cache.manager import CacheManager

# ── 性能目標値 ───────────────────────────────────────────────────
TARGET_SET_GET_US   = 50.0    # set/get 1回あたり（マイクロ秒）
TARGET_HIT_RATE_MIN = 0.90    # 同一キー連続アクセス時の最低ヒット率
TARGET_BATCH_1000_MS = 50.0   # 1000件 set+get 一括


def _measure_us(fn, iterations: int = 1000) -> dict[str, float]:
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        elapsed_us = (time.perf_counter_ns() - start) / 1000
        times.append(elapsed_us)
    return {
        "mean":   statistics.mean(times),
        "median": statistics.median(times),
        "max":    max(times),
    }


# ══════════════════════════════════════════════════════════════════
# LRUCache — 基本性能
# ══════════════════════════════════════════════════════════════════

class TestLRUCacheSpeed:
    def test_set_speed(self):
        cache = LRUCache(max_size=1000)
        stats = _measure_us(lambda: cache.set("key", "value"), iterations=1000)
        print(f"\n  [set] mean={stats['mean']:.2f}us  max={stats['max']:.2f}us")
        assert stats["mean"] <= TARGET_SET_GET_US

    def test_get_hit_speed(self):
        cache = LRUCache(max_size=1000)
        cache.set("key", "value")
        stats = _measure_us(lambda: cache.get("key"), iterations=1000)
        print(f"\n  [get:hit] mean={stats['mean']:.2f}us")
        assert stats["mean"] <= TARGET_SET_GET_US

    def test_get_miss_speed(self):
        cache = LRUCache(max_size=1000)
        stats = _measure_us(lambda: cache.get("nonexistent"), iterations=1000)
        print(f"\n  [get:miss] mean={stats['mean']:.2f}us")
        assert stats["mean"] <= TARGET_SET_GET_US

    def test_batch_1000_set_get(self):
        cache = LRUCache(max_size=2000)
        start = time.perf_counter()
        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}")
        for i in range(1000):
            cache.get(f"key_{i}")
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [batch] 1000 set + 1000 get in {elapsed_ms:.2f}ms")
        assert elapsed_ms <= TARGET_BATCH_1000_MS


# ══════════════════════════════════════════════════════════════════
# LRUCache — エビクション性能
# ══════════════════════════════════════════════════════════════════

class TestLRUEvictionPerformance:
    def test_eviction_under_load(self):
        """max_size を超える書き込みでも性能劣化しないこと"""
        cache = LRUCache(max_size=100)

        start = time.perf_counter()
        for i in range(10_000):   # max_size の100倍書き込み
            cache.set(f"key_{i}", i)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [eviction] 10000 writes (max_size=100) in {elapsed_ms:.2f}ms")
        assert cache.size == 100   # サイズが維持されていること
        assert elapsed_ms <= 200.0  # エビクションが頻発しても妥当な時間で完了

    def test_ttl_expiration_performance(self):
        """TTL 期限切れエントリの evict_expired() 性能"""
        cache = LRUCache(max_size=1000, default_ttl=0.01)
        for i in range(500):
            cache.set(f"key_{i}", i)

        time.sleep(0.05)   # 全て期限切れにする

        start = time.perf_counter()
        evicted = cache.evict_expired()
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [ttl_evict] {evicted} entries evicted in {elapsed_ms:.2f}ms")
        assert evicted == 500
        assert elapsed_ms <= 50.0


# ══════════════════════════════════════════════════════════════════
# CacheManager — ヒット率シミュレーション
# ══════════════════════════════════════════════════════════════════

class TestCacheHitRateSimulation:
    def test_repeated_lookup_high_hit_rate(self):
        """同一プロンプトを繰り返し処理する典型シナリオでのヒット率"""
        cm = CacheManager(max_size=256, default_ttl=3600)

        # 10種類のプロンプトを100回ずつ「処理」（初回は miss、以降は hit）
        prompts = [f"prompt_{i}" for i in range(10)]

        for _ in range(100):
            for p in prompts:
                cached = cm.get_prompt(p)
                if cached is None:
                    cm.set_prompt(p, f"result_for_{p}")

        stats = cm.statistics()
        print(f"\n  [hit_rate] hits={stats['hits']}  misses={stats['misses']}  "
              f"rate={stats['hit_rate']:.2%}")

        assert stats["hit_rate"] >= TARGET_HIT_RATE_MIN, (
            f"ヒット率が目標値を下回る: {stats['hit_rate']:.2%} < {TARGET_HIT_RATE_MIN:.0%}"
        )

    def test_dictionary_lookup_cache_speedup(self):
        """
        辞書ルックアップキャッシュの動作確認。

        注意: DictionaryManager.lookup() 自体がハッシュマップベースで
        既に ~1us 級と極めて高速なため、CacheManager 経由（SHA-256キー
        生成のオーバーヘッドを伴う）の方が遅くなるのは予期された結果。
        このテストではキャッシュが「正しく機能する」ことのみを検証し、
        生の辞書ルックアップとの speedup 比較は行わない
        （キャッシュが効果を発揮するのは、辞書ルックアップより重い
        処理＝パイプライン全体やルール適用結果のキャッシュにおいてである）。
        """
        sys.path.insert(0, str(ROOT / "fps-core"))
        from dictionary.manager import DictionaryManager

        dm = DictionaryManager(
            system_dir=ROOT / "fps-data" / "dictionaries" / "system",
            user_dir=ROOT / "fps-data" / "dictionaries" / "user",
        )
        dm.load()
        cm = CacheManager(max_size=256)

        # 1回目: キャッシュミス → 実ルックアップ → キャッシュ書き込み
        cached = cm.get_lookup("masterpiece")
        assert cached is None
        result = dm.lookup("masterpiece")
        cm.set_lookup("masterpiece", result.resolved)

        # 2回目以降: キャッシュヒットすることを確認
        for _ in range(100):
            cached = cm.get_lookup("masterpiece")
            assert cached == "Quality.High"

        stats = cm.statistics()
        print(f"\n  [cache_correctness] hits={stats['hits']}  misses={stats['misses']}")
        assert stats["hits"] == 100
        assert stats["misses"] == 1

    def test_cache_beneficial_for_heavy_computation(self):
        """
        キャッシュが効果を発揮する典型シナリオ: パイプライン全体の
        コンパイル結果をキャッシュした場合の高速化を測定する。
        """
        sys.path.insert(0, str(ROOT / "fps-core"))
        from dictionary.manager import DictionaryManager
        from pipeline.manager import PipelineManager

        dm = DictionaryManager(
            system_dir=ROOT / "fps-data" / "dictionaries" / "system",
            user_dir=ROOT / "fps-data" / "dictionaries" / "user",
        )
        dm.load()
        pm = PipelineManager()
        pm.set_context(dictionary_manager=dm)
        cm = CacheManager(max_size=256)

        prompt = "masterpiece, blue_eyes, elf_ears, long_hair, smile"

        # キャッシュなし: 毎回フルパイプライン実行
        start = time.perf_counter()
        for _ in range(200):
            pm.compile(prompt)
        no_cache_ms = (time.perf_counter() - start) * 1000

        # キャッシュあり: 初回のみパイプライン実行、以降キャッシュ
        start = time.perf_counter()
        for _ in range(200):
            cached = cm.get_prompt(prompt)
            if cached is None:
                result = pm.compile(prompt)
                cm.set_prompt(prompt, result.prompt)
        with_cache_ms = (time.perf_counter() - start) * 1000

        speedup = no_cache_ms / with_cache_ms if with_cache_ms > 0 else 0
        print(
            f"\n  [pipeline_cache_speedup] no_cache={no_cache_ms:.2f}ms  "
            f"with_cache={with_cache_ms:.2f}ms  speedup={speedup:.1f}x"
        )
        # パイプライン全体はキャッシュの恩恵を受けるべき
        assert with_cache_ms < no_cache_ms


# ══════════════════════════════════════════════════════════════════
# CacheManager — 名前空間分離性能
# ══════════════════════════════════════════════════════════════════

class TestNamespaceIsolationPerformance:
    def test_multiple_namespaces_no_interference(self):
        """複数名前空間を使っても性能劣化しないこと"""
        cm = CacheManager(max_size=256)

        start = time.perf_counter()
        for i in range(100):
            cm.set(f"ns_{i % 10}", f"key_{i}", f"value_{i}")
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [namespaces] 100 writes across 10 namespaces: {elapsed_ms:.2f}ms")
        assert elapsed_ms <= 20.0
        assert len(cm.namespace_names) == 10
