"""
fps-tools/tests/unit/test_pipeline_cache.py

PipelineManager のキャッシュ統合（Gap 1 対応）のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_pipeline_cache.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from cache.manager import CacheManager
from dictionary.manager import DictionaryManager
from pipeline.manager import PipelineManager


@pytest.fixture
def cache_manager() -> CacheManager:
    return CacheManager(max_size=256, default_ttl=3600)


@pytest.fixture
def dictionary_manager(tmp_path: Path) -> DictionaryManager:
    system_dir = tmp_path / "system"
    system_dir.mkdir()
    (system_dir / "quality.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "category": "quality",
                "entries": [{"key": "masterpiece", "resolved": "Quality.High"}],
            }
        ),
        encoding="utf-8",
    )
    dm = DictionaryManager(system_dir=system_dir, user_dir=tmp_path / "user")
    dm.load()
    return dm


# ══════════════════════════════════════════════════════════════════
# 基本キャッシュ動作
# ══════════════════════════════════════════════════════════════════

class TestCacheBasic:
    def test_no_cache_manager_works_normally(self):
        pm = PipelineManager()
        result = pm.compile("masterpiece")
        assert result.success is True

    def test_cache_hit_returns_equivalent_result(self, cache_manager: CacheManager):
        pm = PipelineManager(cache_manager=cache_manager)
        r1 = pm.compile("masterpiece")
        r2 = pm.compile("masterpiece")
        assert r1.prompt == r2.prompt
        assert r1.tag_count == r2.tag_count

    def test_cache_hit_returns_different_object(self, cache_manager: CacheManager):
        """キャッシュヒット時はディープコピーを返す（参照共有しない）"""
        pm = PipelineManager(cache_manager=cache_manager)
        r1 = pm.compile("masterpiece")
        r2 = pm.compile("masterpiece")
        assert r1 is not r2
        if r1.tags and r2.tags:
            assert r1.tags[0] is not r2.tags[0]

    def test_mutation_does_not_affect_cache(self, cache_manager: CacheManager):
        """キャッシュ結果を呼び出し側がミューテートしてもキャッシュ本体は汚染されない"""
        pm = PipelineManager(cache_manager=cache_manager)
        pm.compile("masterpiece, blue_eyes")
        r2 = pm.compile("masterpiece, blue_eyes")

        if r2.tags:
            r2.tags[0].tag = "MUTATED"

        r3 = pm.compile("masterpiece, blue_eyes")
        if r3.tags:
            assert r3.tags[0].tag != "MUTATED"

    def test_different_prompts_different_cache_entries(self, cache_manager: CacheManager):
        pm = PipelineManager(cache_manager=cache_manager)
        pm.compile("masterpiece")
        pm.compile("blue_eyes")
        stats = pm.cache_statistics()
        assert stats["misses"] == 2
        assert stats["hits"] == 0


# ══════════════════════════════════════════════════════════════════
# キャッシュ統計
# ══════════════════════════════════════════════════════════════════

class TestCacheStatistics:
    def test_statistics_disabled_without_cache(self):
        pm = PipelineManager()
        stats = pm.cache_statistics()
        assert stats["enabled"] is False

    def test_statistics_enabled_with_cache(self, cache_manager: CacheManager):
        pm = PipelineManager(cache_manager=cache_manager)
        stats = pm.cache_statistics()
        assert stats["enabled"] is True

    def test_hit_rate_calculation(self, cache_manager: CacheManager):
        pm = PipelineManager(cache_manager=cache_manager)
        pm.compile("masterpiece")  # miss
        pm.compile("masterpiece")  # hit
        pm.compile("masterpiece")  # hit
        stats = pm.cache_statistics()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(2 / 3, abs=0.01)


# ══════════════════════════════════════════════════════════════════
# 後付け設定
# ══════════════════════════════════════════════════════════════════

class TestSetCacheManager:
    def test_set_cache_manager_after_init(self, cache_manager: CacheManager):
        pm = PipelineManager()
        pm.set_cache_manager(cache_manager)
        pm.compile("masterpiece")
        pm.compile("masterpiece")
        stats = pm.cache_statistics()
        assert stats["hits"] == 1

    def test_set_cache_manager_returns_self(self, cache_manager: CacheManager):
        pm = PipelineManager()
        result = pm.set_cache_manager(cache_manager)
        assert result is pm


# ══════════════════════════════════════════════════════════════════
# 辞書/ルール変更時の自動キャッシュ無効化
# ══════════════════════════════════════════════════════════════════

class TestCacheInvalidationOnContextChange:
    def test_dictionary_key_count_change_invalidates_cache(
        self, cache_manager: CacheManager, dictionary_manager: DictionaryManager, tmp_path: Path
    ):
        """辞書のキー数が変わるとキャッシュキーが変わり、再コンパイルされる"""
        pm = PipelineManager(cache_manager=cache_manager)
        pm.set_context(dictionary_manager=dictionary_manager)

        pm.compile("masterpiece")
        stats_before = pm.cache_statistics()
        assert stats_before["misses"] == 1

        # 辞書に新エントリを追加（total_keys が変わる）
        extra_file = tmp_path / "extra.json"
        extra_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "category": "extra",
                    "entries": [{"key": "new_entry_xyz", "resolved": "Extra.New"}],
                }
            ),
            encoding="utf-8",
        )
        from dictionary.models import DictSource

        dictionary_manager.load_file(extra_file, DictSource.SYSTEM)

        pm.compile("masterpiece")
        stats_after = pm.cache_statistics()
        # 辞書が変わったので再度ミスになるはず（同じキーでヒットしない）
        assert stats_after["misses"] == 2

    def test_blacklist_change_invalidates_cache(self, cache_manager: CacheManager):
        pm = PipelineManager(cache_manager=cache_manager)
        pm.compile("masterpiece")
        pm.set_context(blacklist={"masterpiece"})
        pm.compile("masterpiece")
        stats = pm.cache_statistics()
        assert stats["misses"] == 2  # blacklist 変更でキャッシュキーが変わる

    def test_weight_preset_change_invalidates_cache(self, cache_manager: CacheManager):
        pm = PipelineManager(cache_manager=cache_manager)
        pm.compile("masterpiece")
        pm.set_context(weight_preset="quality_focused")
        pm.compile("masterpiece")
        stats = pm.cache_statistics()
        assert stats["misses"] == 2

    def test_same_context_same_cache_key(self, cache_manager: CacheManager):
        """コンテキストが変わらなければ同じキャッシュキーでヒットする"""
        pm = PipelineManager(cache_manager=cache_manager)
        pm.set_context(max_weight=2.5)
        pm.compile("masterpiece")
        pm.compile("masterpiece")
        stats = pm.cache_statistics()
        assert stats["hits"] == 1


# ══════════════════════════════════════════════════════════════════
# イベント連携
# ══════════════════════════════════════════════════════════════════

class TestCacheEventIntegration:
    def test_cache_hit_emits_event(self, cache_manager: CacheManager):
        from events.event_bus import EventBus

        bus = EventBus()
        received = []
        bus.on("pipeline.cache_hit", lambda e: received.append(e))

        pm = PipelineManager(cache_manager=cache_manager, event_bus=bus)
        pm.compile("masterpiece")
        pm.compile("masterpiece")

        assert len(received) == 1

    def test_cache_miss_does_not_emit_cache_hit(self, cache_manager: CacheManager):
        from events.event_bus import EventBus

        bus = EventBus()
        received = []
        bus.on("pipeline.cache_hit", lambda e: received.append(e))

        pm = PipelineManager(cache_manager=cache_manager, event_bus=bus)
        pm.compile("masterpiece")

        assert len(received) == 0


# ══════════════════════════════════════════════════════════════════
# 失敗結果はキャッシュされない
# ══════════════════════════════════════════════════════════════════

class TestCacheSkipsFailures:
    def test_failed_compile_not_cached(self, cache_manager: CacheManager):
        """abort_on_error 等でエラーになった結果はキャッシュされない"""
        from unittest.mock import MagicMock

        rm = MagicMock()
        rm.apply.side_effect = RuntimeError("forced failure")

        pm = PipelineManager(cache_manager=cache_manager)
        pm.set_context(rule_manager=rm)

        r1 = pm.compile("masterpiece")
        assert r1.success is False

        r2 = pm.compile("masterpiece")
        assert r2.success is False
        # 2回ともミスのはず（失敗結果はキャッシュされていない）
        stats = pm.cache_statistics()
        assert stats["hits"] == 0
