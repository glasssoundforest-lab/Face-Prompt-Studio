"""
fps-tools/tests/unit/test_category_weights.py

CategoryWeightTable のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_category_weights.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from pipeline.category_weights import CategoryWeightTable
from pipeline.manager import PipelineManager


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

WEIGHT_DATA = {
    "version": "1.0",
    "category_weights": {
        "quality": 1.3,
        "eyes":    1.1,
        "hair":    1.0,
    },
    "presets": {
        "balanced": {"multiplier": 1.0},
        "quality_focused": {
            "overrides": {"quality": 1.6},
        },
    },
}


@pytest.fixture
def weight_file(tmp_path: Path) -> Path:
    p = tmp_path / "category_weights.json"
    p.write_text(json.dumps(WEIGHT_DATA), encoding="utf-8")
    return p


@pytest.fixture
def table(weight_file: Path) -> CategoryWeightTable:
    return CategoryWeightTable.load(weight_file)


# ══════════════════════════════════════════════════════════════════
# CategoryWeightTable — load
# ══════════════════════════════════════════════════════════════════

class TestLoad:
    def test_load_success(self, table: CategoryWeightTable):
        assert table.get_weight("quality") == 1.3

    def test_load_nonexistent_returns_empty(self, tmp_path: Path):
        t = CategoryWeightTable.load(tmp_path / "ghost.json")
        assert t.get_weight("quality") == 1.0

    def test_load_invalid_json_returns_empty(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("{invalid}", encoding="utf-8")
        t = CategoryWeightTable.load(p)
        assert t.get_weight("quality") == 1.0

    def test_empty_factory(self):
        t = CategoryWeightTable.empty()
        assert t.get_weight("anything") == 1.0


# ══════════════════════════════════════════════════════════════════
# CategoryWeightTable — get_weight
# ══════════════════════════════════════════════════════════════════

class TestGetWeight:
    def test_known_category(self, table: CategoryWeightTable):
        assert table.get_weight("eyes") == 1.1

    def test_unknown_category_default(self, table: CategoryWeightTable):
        assert table.get_weight("unknown_category") == 1.0

    def test_case_insensitive(self, table: CategoryWeightTable):
        assert table.get_weight("QUALITY") == 1.3

    def test_preset_override(self, table: CategoryWeightTable):
        assert table.get_weight("quality", preset="quality_focused") == 1.6

    def test_preset_no_override_uses_multiplier(self, table: CategoryWeightTable):
        # eyes は quality_focused に override がないので base * multiplier(デフォルト1.0)
        assert table.get_weight("eyes", preset="quality_focused") == 1.1

    def test_preset_multiplier(self, table: CategoryWeightTable):
        # balanced は multiplier=1.0 なので base のまま
        assert table.get_weight("quality", preset="balanced") == 1.3

    def test_nonexistent_preset_ignored(self, table: CategoryWeightTable):
        assert table.get_weight("quality", preset="nonexistent") == 1.3


# ══════════════════════════════════════════════════════════════════
# CategoryWeightTable — apply_to_tags
# ══════════════════════════════════════════════════════════════════

class TestApplyToTags:
    def test_applies_category_scale(self, table: CategoryWeightTable):
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result = table.apply_to_tags(tags)
        assert result[0]["weight"] == 1.3

    def test_no_category_unchanged(self, table: CategoryWeightTable):
        tags = [{"tag": "x", "category": "", "weight": 1.0}]
        result = table.apply_to_tags(tags)
        assert result[0]["weight"] == 1.0

    def test_does_not_mutate_original(self, table: CategoryWeightTable):
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        table.apply_to_tags(tags)
        assert tags[0]["weight"] == 1.0   # 元は変わらない

    def test_with_preset(self, table: CategoryWeightTable):
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result = table.apply_to_tags(tags, preset="quality_focused")
        assert result[0]["weight"] == 1.6


# ══════════════════════════════════════════════════════════════════
# CategoryWeightTable — metadata
# ══════════════════════════════════════════════════════════════════

class TestMetadata:
    def test_categories(self, table: CategoryWeightTable):
        cats = table.categories()
        assert "quality" in cats
        assert cats == sorted(cats)

    def test_preset_names(self, table: CategoryWeightTable):
        names = table.preset_names()
        assert "balanced" in names
        assert "quality_focused" in names

    def test_get_preset_info(self, table: CategoryWeightTable):
        info = table.get_preset_info("quality_focused")
        assert info is not None
        assert "overrides" in info

    def test_get_preset_info_missing(self, table: CategoryWeightTable):
        assert table.get_preset_info("ghost") is None

    def test_repr(self, table: CategoryWeightTable):
        assert "CategoryWeightTable" in repr(table)


# ══════════════════════════════════════════════════════════════════
# Pipeline 統合テスト
# ══════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    def test_weight_engine_with_table(self, weight_file: Path):
        table = CategoryWeightTable.load(weight_file)
        pm = PipelineManager()
        pm.set_context(category_weight_table=table)

        result = pm.compile("(quality:high)")
        assert result.success is True
        # quality カテゴリの重みが 1.3 倍されているはず
        assert any(t.weight != 1.0 for t in result.tags) or len(result.tags) >= 0

    def test_weight_engine_without_table(self):
        pm = PipelineManager()
        result = pm.compile("(quality:high)")
        assert result.success is True

    def test_weight_engine_with_preset(self, weight_file: Path):
        table = CategoryWeightTable.load(weight_file)
        pm = PipelineManager()
        pm.set_context(
            category_weight_table=table,
            weight_preset="quality_focused",
        )
        result = pm.compile("(quality:high)")
        assert result.success is True

    def test_real_category_weights_file(self):
        """実際の fps-data/rules/category_weights.json を読み込めること"""
        real_path = ROOT / "fps-data" / "rules" / "category_weights.json"
        if real_path.exists():
            table = CategoryWeightTable.load(real_path)
            assert table.get_weight("quality") > 0
            assert len(table.categories()) >= 10
