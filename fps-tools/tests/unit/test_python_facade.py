"""
fps-tools/tests/unit/test_python_facade.py

FacePromptStudio ファサード（Gap 5 対応）のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_python_facade.py -v
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from python.facade import FacePromptStudio


@pytest.fixture
def studio(tmp_path: Path) -> FacePromptStudio:
    s = FacePromptStudio()
    s.root = tmp_path
    return s


@pytest.fixture
def studio_with_local_data(tmp_path: Path) -> FacePromptStudio:
    data_copy = tmp_path / "fps-data"
    shutil.copytree(ROOT / "fps-data", data_copy)
    s = FacePromptStudio(data_root=data_copy)
    s.root = tmp_path
    return s


class TestInitialization:
    def test_default_initialization(self):
        s = FacePromptStudio()
        assert s.dictionary_stats()["total_keys"] > 1000

    def test_repr(self):
        s = FacePromptStudio()
        assert "FacePromptStudio" in repr(s)

    def test_cache_disabled(self):
        s = FacePromptStudio(enable_cache=False)
        result = s.compile("masterpiece")
        assert result.success is True

    def test_events_enabled(self):
        s = FacePromptStudio(enable_events=True)
        assert s._event_bus is not None

    def test_events_disabled_by_default(self):
        s = FacePromptStudio()
        assert s._event_bus is None

    def test_custom_data_root(self, tmp_path: Path):
        data_copy = tmp_path / "data"
        shutil.copytree(ROOT / "fps-data", data_copy)
        s = FacePromptStudio(data_root=data_copy)
        assert s.data_root == data_copy
        assert s.dictionary_stats()["total_keys"] > 1000


class TestCompileExport:
    def test_compile_basic(self, studio: FacePromptStudio):
        result = studio.compile("masterpiece, blue_eyes")
        assert result.success is True
        assert result.tag_count >= 1

    def test_compile_dsl_syntax(self, studio: FacePromptStudio):
        result = studio.compile("(quality:high:1.5)")
        assert result.success is True

    def test_export_comfyui(self, studio: FacePromptStudio):
        result = studio.compile("masterpiece")
        out = studio.export(result, "comfyui")
        assert "prompt" in out

    def test_export_a1111(self, studio: FacePromptStudio):
        result = studio.compile("masterpiece")
        out = studio.export(result, "a1111")
        assert "prompt" in out

    def test_export_novelai(self, studio: FacePromptStudio):
        result = studio.compile("masterpiece")
        out = studio.export(result, "novelai")
        assert "prompt" in out

    def test_export_unknown_adapter_raises(self, studio: FacePromptStudio):
        result = studio.compile("masterpiece")
        with pytest.raises(ValueError):
            studio.export(result, "unknown_adapter_xyz")

    def test_compile_with_track_history(self, tmp_path: Path):
        s = FacePromptStudio(track_history=True)
        s.root = tmp_path
        s.compile("masterpiece")
        assert len(s.history()) == 1


class TestDictionary:
    def test_lookup_found(self, studio: FacePromptStudio):
        result = studio.lookup("blue_eyes")
        assert result.found is True
        assert result.resolved == "Eyes.Blue"

    def test_lookup_not_found(self, studio: FacePromptStudio):
        result = studio.lookup("nonexistent_xyz_999")
        assert result.found is False

    def test_dictionary_stats(self, studio: FacePromptStudio):
        stats = studio.dictionary_stats()
        assert stats["total_keys"] > 1000

    def test_dictionary_categories(self, studio: FacePromptStudio):
        cats = studio.dictionary_categories()
        assert "eyes" in cats
        assert len(cats) > 10


class TestPresets:
    def test_list_presets(self, studio: FacePromptStudio):
        presets = studio.list_presets()
        assert len(presets) >= 3

    def test_apply_preset(self, studio: FacePromptStudio):
        result = studio.apply_preset("anime_portrait")
        assert result.success is True
        assert result.tag_count > 0

    def test_save_preset(self, studio_with_local_data: FacePromptStudio):
        path = studio_with_local_data.save_preset(
            "test_preset_xyz",
            "テストプリセット",
            tags=[{"tag": "masterpiece", "category": "quality", "weight": 1.5}],
        )
        assert path.exists()

    def test_save_preset_with_negative(self, studio_with_local_data: FacePromptStudio):
        path = studio_with_local_data.save_preset(
            "test_preset_neg",
            "テスト2",
            tags=[{"tag": "masterpiece"}],
            negative_tags=[{"tag": "bad_hands"}],
        )
        assert path.exists()

    def test_saved_preset_appears_in_list(self, studio_with_local_data: FacePromptStudio):
        studio_with_local_data.save_preset(
            "test_preset_list", "リスト確認", tags=[{"tag": "masterpiece"}]
        )
        presets = studio_with_local_data.list_presets()
        assert any(p.id == "test_preset_list" for p in presets)


class TestOptimizer:
    def test_optimize_returns_score(self, studio: FacePromptStudio):
        analysis = studio.optimize("masterpiece")
        assert 0 <= analysis.score.overall_score <= 100

    def test_optimize_detects_conflict(self, studio: FacePromptStudio):
        analysis = studio.optimize("blue_eyes, brown_eyes")
        assert len(analysis.issues) >= 1

    def test_optimize_has_recommendations(self, studio: FacePromptStudio):
        analysis = studio.optimize("masterpiece")
        assert len(analysis.recommendations) > 0


class TestHistory:
    def test_record_history(self, studio: FacePromptStudio):
        result = studio.compile("masterpiece")
        entry = studio.record_history(result, input_prompt="masterpiece")
        assert entry.id != ""

    def test_history_list(self, studio: FacePromptStudio):
        result = studio.compile("masterpiece")
        studio.record_history(result, input_prompt="masterpiece")
        entries = studio.history()
        assert len(entries) == 1

    def test_history_records_score(self, studio: FacePromptStudio):
        result = studio.compile("masterpiece, blue_eyes")
        entry = studio.record_history(result, input_prompt="masterpiece, blue_eyes")
        assert entry.overall_score > 0

    def test_history_limit(self, studio: FacePromptStudio):
        for i in range(5):
            result = studio.compile(f"tag_{i}")
            studio.record_history(result, input_prompt=f"tag_{i}")
        entries = studio.history(limit=2)
        assert len(entries) == 2


class TestBackup:
    def test_backup_all(self, studio: FacePromptStudio):
        result = studio.backup()
        assert result.success is True

    def test_backup_specific_target(self, studio: FacePromptStudio):
        result = studio.backup(target="rules")
        assert result.success is True

    def test_list_backups(self, studio: FacePromptStudio):
        studio.backup(target="rules")
        backups = studio.list_backups()
        assert len(backups) >= 1

    def test_restore_backup(self, studio: FacePromptStudio):
        studio.backup(target="rules")
        backups = studio.list_backups()
        result = studio.restore_backup(backups[0].id)
        assert result.success is True


class TestPlugins:
    def test_load_plugin(self, studio: FacePromptStudio, tmp_path: Path):
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text(
            f'''
import sys
sys.path.insert(0, "{ROOT / "fps-core"}")
from plugins.base_plugin import StagePlugin
from plugins.models import PluginInfo, PluginType

class TestPlugin(StagePlugin):
    info = PluginInfo(name="facade_unit_test_plugin", type=PluginType.STAGE)
    stage_name = "facade_unit_test_plugin"
    def process(self, tags, context):
        return tags
'''
        )
        count = studio.load_plugin(plugin_file)
        assert count == 1

    def test_apply_plugins_integrates_stage(self, studio: FacePromptStudio, tmp_path: Path):
        plugin_file = tmp_path / "uppercase_plugin.py"
        plugin_file.write_text(
            f'''
import sys
sys.path.insert(0, "{ROOT / "fps-core"}")
from plugins.base_plugin import StagePlugin
from plugins.models import PluginInfo, PluginType

class UppercasePlugin(StagePlugin):
    info = PluginInfo(name="facade_uppercase_plugin", type=PluginType.STAGE)
    stage_name = "facade_uppercase_plugin"
    def process(self, tags, context):
        for t in tags:
            t.tag = t.tag.upper()
        return tags
'''
        )
        studio.load_plugin(plugin_file)
        integrated = studio.apply_plugins()
        assert integrated == 1

        result = studio.compile("masterpiece")
        assert any(t.tag.isupper() for t in result.tags)


class TestValidation:
    def test_validate_returns_empty_dict_when_valid(self, studio: FacePromptStudio):
        errors = studio.validate()
        assert errors == {}

    def test_is_valid_true(self, studio: FacePromptStudio):
        assert studio.is_valid() is True


class TestStatistics:
    def test_statistics_structure(self, studio: FacePromptStudio):
        stats = studio.statistics()
        assert "dictionary" in stats
        assert "rules" in stats
        assert "pipeline" in stats

    def test_statistics_includes_cache_when_enabled(self):
        s = FacePromptStudio(enable_cache=True)
        stats = s.statistics()
        assert "cache" in stats

    def test_statistics_excludes_cache_when_disabled(self):
        s = FacePromptStudio(enable_cache=False)
        stats = s.statistics()
        assert "cache" not in stats
