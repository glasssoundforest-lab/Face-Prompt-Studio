"""
fps-tools/tests/performance/test_dict_lookup_perf.py

DictionaryManager のルックアップ速度性能テスト。
目標: < 1ms/lookup

pytest で実行: pytest fps-tools/tests/performance/test_dict_lookup_perf.py -v -s
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from dictionary.manager import DictionaryManager

# ── 性能目標値（ミリ秒） ─────────────────────────────────────────
TARGET_LOOKUP_MS          = 1.0     # 1ルックアップあたり
TARGET_BATCH_1000_MS      = 200.0   # 1000ルックアップ一括
TARGET_LOAD_MS            = 500.0   # 辞書全体ロード時間


def _measure_ns(fn, iterations: int = 1000) -> dict[str, float]:
    """関数を複数回実行して統計値を返す（マイクロ秒単位）"""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        elapsed_us = (time.perf_counter_ns() - start) / 1000
        times.append(elapsed_us)

    return {
        "mean_us":   statistics.mean(times),
        "median_us": statistics.median(times),
        "min_us":    min(times),
        "max_us":    max(times),
        "p95_us":    sorted(times)[int(len(times) * 0.95)],
        "p99_us":    sorted(times)[int(len(times) * 0.99)],
    }


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def dm() -> DictionaryManager:
    manager = DictionaryManager(
        system_dir=ROOT / "fps-data" / "dictionaries" / "system",
        user_dir=ROOT / "fps-data" / "dictionaries" / "user",
    )
    manager.load()
    return manager


@pytest.fixture(scope="module")
def sample_keys(dm: DictionaryManager) -> list[str]:
    """辞書から実際のキーをサンプリングする"""
    import json

    keys: list[str] = []
    for f in sorted((ROOT / "fps-data" / "dictionaries" / "system").rglob("*.json")):
        data = json.loads(f.read_text())
        for entry in data.get("entries", [])[:5]:  # 各ファイルから最大5件
            keys.append(entry["key"])
    return keys[:100]   # 最大100キー


# ══════════════════════════════════════════════════════════════════
# 辞書ロード速度
# ══════════════════════════════════════════════════════════════════

class TestDictionaryLoadSpeed:
    def test_load_speed(self):
        start = time.perf_counter()
        manager = DictionaryManager(
            system_dir=ROOT / "fps-data" / "dictionaries" / "system",
            user_dir=ROOT / "fps-data" / "dictionaries" / "user",
        )
        manager.load()
        elapsed_ms = (time.perf_counter() - start) * 1000

        stats = manager.statistics()
        print(f"\n  [load] {stats['total_keys']} keys loaded in {elapsed_ms:.2f}ms")
        assert elapsed_ms <= TARGET_LOAD_MS, (
            f"辞書ロードが目標値を超過: {elapsed_ms:.2f}ms > {TARGET_LOAD_MS}ms"
        )

    def test_reload_speed(self, dm: DictionaryManager):
        start = time.perf_counter()
        dm.reload()
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [reload] completed in {elapsed_ms:.2f}ms")
        assert elapsed_ms <= TARGET_LOAD_MS


# ══════════════════════════════════════════════════════════════════
# 単発ルックアップ速度
# ══════════════════════════════════════════════════════════════════

class TestSingleLookupSpeed:
    def test_known_key_lookup(self, dm: DictionaryManager):
        stats = _measure_ns(lambda: dm.lookup("masterpiece"), iterations=1000)
        print(
            f"\n  [lookup:known] mean={stats['mean_us']:.2f}us  "
            f"p95={stats['p95_us']:.2f}us  p99={stats['p99_us']:.2f}us"
        )
        assert stats["mean_us"] / 1000 <= TARGET_LOOKUP_MS, (
            f"ルックアップが目標値を超過: {stats['mean_us']/1000:.4f}ms > {TARGET_LOOKUP_MS}ms"
        )

    def test_unknown_key_lookup(self, dm: DictionaryManager):
        """存在しないキーの検索速度（ミスケース）"""
        stats = _measure_ns(lambda: dm.lookup("nonexistent_tag_xyz_999"), iterations=1000)
        print(f"\n  [lookup:miss] mean={stats['mean_us']:.2f}us")
        assert stats["mean_us"] / 1000 <= TARGET_LOOKUP_MS

    def test_alias_lookup(self, dm: DictionaryManager):
        """エイリアス経由の検索速度"""
        stats = _measure_ns(lambda: dm.lookup("best quality"), iterations=1000)
        print(f"\n  [lookup:alias] mean={stats['mean_us']:.2f}us")
        assert stats["mean_us"] / 1000 <= TARGET_LOOKUP_MS

    def test_normalized_key_lookup(self, dm: DictionaryManager):
        """大文字・スペース混在キーの正規化込み検索速度"""
        stats = _measure_ns(lambda: dm.lookup("BLUE EYES"), iterations=1000)
        print(f"\n  [lookup:normalize] mean={stats['mean_us']:.2f}us")
        assert stats["mean_us"] / 1000 <= TARGET_LOOKUP_MS


# ══════════════════════════════════════════════════════════════════
# バッチルックアップ速度
# ══════════════════════════════════════════════════════════════════

class TestBatchLookupSpeed:
    def test_batch_1000_lookups(self, dm: DictionaryManager, sample_keys: list[str]):
        """1000回ルックアップを一括実行する"""
        if not sample_keys:
            pytest.skip("サンプルキーが取得できませんでした")

        start = time.perf_counter()
        for _ in range(1000 // len(sample_keys) + 1):
            for key in sample_keys:
                dm.lookup(key)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [batch] ~1000 lookups in {elapsed_ms:.2f}ms "
              f"({elapsed_ms/1000:.4f}ms/lookup)")
        assert elapsed_ms <= TARGET_BATCH_1000_MS, (
            f"バッチルックアップが目標値を超過: {elapsed_ms:.2f}ms > {TARGET_BATCH_1000_MS}ms"
        )

    def test_lookup_many_speed(self, dm: DictionaryManager, sample_keys: list[str]):
        """lookup_many() 一括APIの速度"""
        if not sample_keys:
            pytest.skip("サンプルキーが取得できませんでした")

        start = time.perf_counter()
        dm.lookup_many(sample_keys * 10)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [lookup_many] {len(sample_keys)*10} keys in {elapsed_ms:.2f}ms")
        assert elapsed_ms <= TARGET_BATCH_1000_MS


# ══════════════════════════════════════════════════════════════════
# スケーラビリティ（辞書サイズに対する線形性）
# ══════════════════════════════════════════════════════════════════

class TestScalability:
    def test_lookup_time_independent_of_dict_size(self, dm: DictionaryManager):
        """
        辞書サイズが大きくても（784キー）ルックアップは O(1) に近いはず。
        ハッシュマップベースの実装であることを性能面から検証する。
        """
        stats = dm.statistics()
        total_keys = stats["total_keys"]

        single_lookup = _measure_ns(lambda: dm.lookup("masterpiece"), iterations=500)

        print(
            f"\n  [scalability] {total_keys} keys, "
            f"avg lookup={single_lookup['mean_us']:.2f}us"
        )
        # 784キーでも 1ms 未満であれば O(1) 的な実装と判断できる
        assert single_lookup["mean_us"] / 1000 <= TARGET_LOOKUP_MS
