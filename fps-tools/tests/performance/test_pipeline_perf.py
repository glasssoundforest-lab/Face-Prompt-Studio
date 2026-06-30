"""
fps-tools/tests/performance/test_pipeline_perf.py

パイプライン処理速度の性能テスト。
目標値を下回った場合に失敗する回帰検出テスト。

pytest で実行: pytest fps-tools/tests/performance/test_pipeline_perf.py -v -s
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from dictionary.manager import DictionaryManager
from pipeline.category_weights import CategoryWeightTable
from pipeline.manager import PipelineManager
from rules.manager import RuleManager

# ── 性能目標値（ミリ秒） ─────────────────────────────────────────
# 環境差を考慮し緩めに設定。CI 環境での揺れを許容する。
TARGET_SIMPLE_PROMPT_MS   = 5.0    # 単純プロンプト1回のコンパイル
TARGET_COMPLEX_PROMPT_MS  = 15.0   # 顔15カテゴリ全部入りプロンプト
TARGET_BATCH_100_MS       = 500.0  # 100プロンプト一括処理
TARGET_THROUGHPUT_PER_SEC = 50     # 1秒あたりの処理可能プロンプト数（最低値）


def _measure(fn, iterations: int = 20) -> dict[str, float]:
    """関数を複数回実行して統計値を返す（ミリ秒単位）"""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)

    return {
        "mean":   statistics.mean(times),
        "median": statistics.median(times),
        "min":    min(times),
        "max":    max(times),
        "stdev":  statistics.stdev(times) if len(times) > 1 else 0.0,
    }


def _print_stats(label: str, stats: dict[str, float], target_ms: float) -> None:
    status = "✓" if stats["mean"] <= target_ms else "✗"
    print(
        f"\n  [{status}] {label}\n"
        f"      mean={stats['mean']:.3f}ms  median={stats['median']:.3f}ms  "
        f"min={stats['min']:.3f}ms  max={stats['max']:.3f}ms  "
        f"target={target_ms}ms"
    )


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def dictionary_manager() -> DictionaryManager:
    dm = DictionaryManager(
        system_dir=ROOT / "fps-data" / "dictionaries" / "system",
        user_dir=ROOT / "fps-data" / "dictionaries" / "user",
    )
    dm.load()
    return dm


@pytest.fixture(scope="module")
def rule_manager() -> RuleManager:
    rm = RuleManager(rule_dir=ROOT / "fps-data" / "rules")
    rm.load()
    return rm


@pytest.fixture(scope="module")
def weight_table() -> CategoryWeightTable:
    return CategoryWeightTable.load(ROOT / "fps-data" / "rules" / "category_weights.json")


@pytest.fixture
def pipeline(
    dictionary_manager: DictionaryManager,
    rule_manager: RuleManager,
    weight_table: CategoryWeightTable,
) -> PipelineManager:
    pm = PipelineManager()
    pm.set_context(
        dictionary_manager=dictionary_manager,
        rule_manager=rule_manager,
        category_weight_table=weight_table,
    )
    return pm


SIMPLE_PROMPT = "masterpiece, blue_eyes"

COMPLEX_PROMPT = (
    "masterpiece, blue_eyes, thick_eyebrows, long_eyelashes, "
    "oval_face, small_nose, full_lips, white_teeth, "
    "freckles, smile, hair_ribbon, glasses, "
    "ear_piercing, lipstick, elf_ears, long_hair, anime, "
    "[bad hands, low_quality, blurry]"
)


# ══════════════════════════════════════════════════════════════════
# パイプライン単体処理速度
# ══════════════════════════════════════════════════════════════════

class TestPipelineSpeed:
    def test_simple_prompt_speed(self, pipeline: PipelineManager):
        stats = _measure(lambda: pipeline.compile(SIMPLE_PROMPT), iterations=30)
        _print_stats("Simple Prompt", stats, TARGET_SIMPLE_PROMPT_MS)
        assert stats["mean"] <= TARGET_SIMPLE_PROMPT_MS, (
            f"単純プロンプト処理が目標値を超過: {stats['mean']:.3f}ms > {TARGET_SIMPLE_PROMPT_MS}ms"
        )

    def test_complex_prompt_speed(self, pipeline: PipelineManager):
        stats = _measure(lambda: pipeline.compile(COMPLEX_PROMPT), iterations=30)
        _print_stats("Complex Prompt (15 categories)", stats, TARGET_COMPLEX_PROMPT_MS)
        assert stats["mean"] <= TARGET_COMPLEX_PROMPT_MS, (
            f"複雑プロンプト処理が目標値を超過: {stats['mean']:.3f}ms > {TARGET_COMPLEX_PROMPT_MS}ms"
        )

    def test_empty_prompt_fast(self, pipeline: PipelineManager):
        stats = _measure(lambda: pipeline.compile(""), iterations=30)
        _print_stats("Empty Prompt", stats, TARGET_SIMPLE_PROMPT_MS)
        assert stats["mean"] <= TARGET_SIMPLE_PROMPT_MS


# ══════════════════════════════════════════════════════════════════
# バッチ処理速度
# ══════════════════════════════════════════════════════════════════

class TestBatchThroughput:
    def test_batch_100_simple_prompts(self, pipeline: PipelineManager):
        prompts = [SIMPLE_PROMPT] * 100

        start = time.perf_counter()
        for p in prompts:
            pipeline.compile(p)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [batch] 100 simple prompts: {elapsed_ms:.2f}ms total "
              f"({elapsed_ms/100:.3f}ms/prompt)")
        assert elapsed_ms <= TARGET_BATCH_100_MS, (
            f"100件バッチ処理が目標値を超過: {elapsed_ms:.2f}ms > {TARGET_BATCH_100_MS}ms"
        )

    def test_throughput_per_second(self, pipeline: PipelineManager):
        """1秒間に処理できるプロンプト数を測定する"""
        start = time.perf_counter()
        count = 0
        while time.perf_counter() - start < 1.0:
            pipeline.compile(SIMPLE_PROMPT)
            count += 1

        print(f"\n  [throughput] {count} prompts/sec "
              f"(target: >= {TARGET_THROUGHPUT_PER_SEC})")
        assert count >= TARGET_THROUGHPUT_PER_SEC, (
            f"スループットが目標値を下回る: {count} < {TARGET_THROUGHPUT_PER_SEC} prompts/sec"
        )


# ══════════════════════════════════════════════════════════════════
# ステージ別処理時間内訳
# ══════════════════════════════════════════════════════════════════

class TestStageBreakdown:
    def test_stage_timing_breakdown(self, pipeline: PipelineManager):
        """各ステージの相対的な処理時間を可視化する（情報提供目的）"""
        import cProfile
        import io
        import pstats

        profiler = cProfile.Profile()
        profiler.enable()
        for _ in range(50):
            pipeline.compile(COMPLEX_PROMPT)
        profiler.disable()

        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
        stats.print_stats(10)

        print("\n  [profile] Top 10 cumulative time functions:")
        print(stream.getvalue()[:2000])

        # このテストは情報提供のみ（失敗条件なし）
        assert True


# ══════════════════════════════════════════════════════════════════
# 大量タグ処理（極端なケース）
# ══════════════════════════════════════════════════════════════════

class TestExtremeLoad:
    def test_many_duplicate_tags(self, pipeline: PipelineManager):
        """同一タグを大量に含むプロンプト（重複除去の負荷テスト）"""
        prompt = ", ".join(["masterpiece"] * 100)
        start = time.perf_counter()
        result = pipeline.compile(prompt)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [extreme] 100x duplicate tags: {elapsed_ms:.3f}ms")
        assert result.success is True
        assert elapsed_ms <= 50.0  # 重複除去後は1タグになるはず

    def test_many_unique_tags(self, pipeline: PipelineManager):
        """大量のユニークタグを含むプロンプト"""
        import json

        dict_path = ROOT / "fps-data" / "dictionaries" / "system" / "eyes.json"
        data = json.loads(dict_path.read_text())
        keys = [e["key"] for e in data["entries"]] * 5  # 75タグ

        prompt = ", ".join(keys)
        start = time.perf_counter()
        result = pipeline.compile(prompt)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  [extreme] {len(keys)} tags (many unique): {elapsed_ms:.3f}ms")
        assert result.success is True
        assert elapsed_ms <= 100.0
