"""
fps-tools/tests/unit/test_plugins.py

Plugin System のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_plugins.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from plugins.base_plugin import AdapterPlugin, BasePlugin, StagePlugin
from plugins.exceptions import (
    PluginDependencyError,
    PluginLoadError,
    PluginNotFoundError,
    PluginValidationError,
)
from plugins.loader import (
    load_plugin_from_file,
    load_plugins_from_dir,
    safe_load_plugin_from_file,
    validate_plugin,
)
from plugins.manager import PluginManager
from plugins.models import PluginInfo, PluginType
from plugins.registry import PluginRegistry


# ══════════════════════════════════════════════════════════════════
# Test fixtures: サンプルプラグインクラス
# ══════════════════════════════════════════════════════════════════

class DummyStagePlugin(StagePlugin):
    info = PluginInfo(name="dummy_stage", version="1.0.0", type=PluginType.STAGE)
    stage_name = "dummy_stage"

    def process(self, tags, context):
        return tags


class DummyAdapterPlugin(AdapterPlugin):
    info = PluginInfo(name="dummy_adapter", version="1.0.0", type=PluginType.ADAPTER)

    def convert(self, pipeline_result):
        return {"prompt": getattr(pipeline_result, "prompt", "")}


class FailingStagePlugin(StagePlugin):
    info = PluginInfo(name="failing_stage", type=PluginType.STAGE)
    stage_name = "failing_stage"

    def process(self, tags, context):
        raise RuntimeError("intentional failure")


@pytest.fixture
def plugin_file(tmp_path: Path) -> Path:
    """テスト用プラグインファイルを動的に生成する"""
    content = f'''
import sys
sys.path.insert(0, "{ROOT / "fps-core"}")
from plugins.base_plugin import StagePlugin
from plugins.models import PluginInfo, PluginType

class FileBasedPlugin(StagePlugin):
    info = PluginInfo(name="file_based_plugin", type=PluginType.STAGE)
    stage_name = "file_based_stage"

    def process(self, tags, context):
        return tags
'''
    p = tmp_path / "sample_plugin.py"
    p.write_text(content, encoding="utf-8")
    return p


# ══════════════════════════════════════════════════════════════════
# models
# ══════════════════════════════════════════════════════════════════

class TestModels:
    def test_plugin_info_defaults(self):
        info = PluginInfo(name="test")
        assert info.version == "0.1.0"
        assert info.type == PluginType.GENERIC

    def test_plugin_info_with_requires(self):
        info = PluginInfo(name="test", requires=["dep1", "dep2"])
        assert "dep1" in info.requires


# ══════════════════════════════════════════════════════════════════
# base_plugin
# ══════════════════════════════════════════════════════════════════

class TestBasePlugin:
    def test_stage_plugin_name_property(self):
        plugin = DummyStagePlugin()
        assert plugin.name == "dummy_stage"

    def test_stage_plugin_process(self):
        plugin = DummyStagePlugin()
        result = plugin.process([], {})
        assert result == []

    def test_adapter_plugin_convert(self):
        plugin = DummyAdapterPlugin()
        from types import SimpleNamespace
        result = plugin.convert(SimpleNamespace(prompt="test"))
        assert result["prompt"] == "test"

    def test_setup_teardown_lifecycle(self):
        plugin = DummyStagePlugin()
        assert plugin.is_setup is False
        plugin.setup()
        assert plugin.is_setup is True
        plugin.teardown()
        assert plugin.is_setup is False

    def test_plugin_without_info_raises(self):
        class NoInfoPlugin(BasePlugin):
            pass

        with pytest.raises(NotImplementedError):
            NoInfoPlugin()


# ══════════════════════════════════════════════════════════════════
# registry
# ══════════════════════════════════════════════════════════════════

class TestPluginRegistry:
    def test_register_and_get(self):
        registry = PluginRegistry()
        plugin = DummyStagePlugin()
        registry.register(plugin)
        assert registry.get("dummy_stage") is plugin

    def test_get_missing_raises(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.get("nonexistent")

    def test_get_or_none_missing(self):
        registry = PluginRegistry()
        assert registry.get_or_none("nonexistent") is None

    def test_register_duplicate_skipped(self):
        registry = PluginRegistry()
        p1 = DummyStagePlugin()
        p2 = DummyStagePlugin()
        registry.register(p1)
        registry.register(p2)  # skip (no replace)
        assert registry.get("dummy_stage") is p1

    def test_register_duplicate_with_replace(self):
        registry = PluginRegistry()
        p1 = DummyStagePlugin()
        p2 = DummyStagePlugin()
        registry.register(p1)
        registry.register(p2, replace=True)
        assert registry.get("dummy_stage") is p2

    def test_unregister(self):
        registry = PluginRegistry()
        registry.register(DummyStagePlugin())
        assert registry.unregister("dummy_stage") is True
        assert registry.exists("dummy_stage") is False

    def test_unregister_missing_returns_false(self):
        registry = PluginRegistry()
        assert registry.unregister("nonexistent") is False

    def test_get_by_type(self):
        registry = PluginRegistry()
        registry.register(DummyStagePlugin())
        registry.register(DummyAdapterPlugin())
        stages = registry.get_by_type(PluginType.STAGE)
        assert len(stages) == 1

    def test_list_all(self):
        registry = PluginRegistry()
        registry.register(DummyStagePlugin())
        assert len(registry.list_all()) == 1

    def test_list_names_sorted(self):
        registry = PluginRegistry()
        registry.register(DummyAdapterPlugin())
        registry.register(DummyStagePlugin())
        names = registry.list_names()
        assert names == sorted(names)

    def test_count(self):
        registry = PluginRegistry()
        registry.register(DummyStagePlugin())
        registry.register(DummyAdapterPlugin())
        assert registry.count() == 2

    def test_dependency_missing_raises(self):
        class DependentPlugin(StagePlugin):
            info = PluginInfo(name="dependent", requires=["missing_dep"])
            stage_name = "dependent"

            def process(self, tags, context):
                return tags

        registry = PluginRegistry()
        with pytest.raises(PluginDependencyError):
            registry.register(DependentPlugin())

    def test_setup_all(self):
        registry = PluginRegistry()
        registry.register(DummyStagePlugin())
        results = registry.setup_all()
        assert results["dummy_stage"] is True

    def test_setup_all_handles_failures(self):
        class BadSetupPlugin(StagePlugin):
            info = PluginInfo(name="bad_setup", type=PluginType.STAGE)
            stage_name = "bad_setup"

            def setup(self, context=None):
                raise RuntimeError("setup failed")

            def process(self, tags, context):
                return tags

        registry = PluginRegistry()
        registry.register(BadSetupPlugin())
        results = registry.setup_all()
        assert results["bad_setup"] is False

    def test_teardown_all(self):
        registry = PluginRegistry()
        plugin = DummyStagePlugin()
        registry.register(plugin)
        plugin.setup()
        registry.teardown_all()
        assert plugin.is_setup is False

    def test_repr(self):
        registry = PluginRegistry()
        registry.register(DummyStagePlugin())
        assert "PluginRegistry" in repr(registry)


# ══════════════════════════════════════════════════════════════════
# loader
# ══════════════════════════════════════════════════════════════════

class TestLoader:
    def test_load_from_file(self, plugin_file: Path):
        plugins = load_plugin_from_file(plugin_file)
        assert len(plugins) == 1
        assert plugins[0].name == "file_based_stage"

    def test_load_nonexistent_raises(self, tmp_path: Path):
        with pytest.raises(PluginLoadError):
            load_plugin_from_file(tmp_path / "ghost.py")

    def test_load_non_py_file_raises(self, tmp_path: Path):
        p = tmp_path / "not_python.txt"
        p.write_text("hello")
        with pytest.raises(PluginLoadError):
            load_plugin_from_file(p)

    def test_load_broken_python_raises(self, tmp_path: Path):
        p = tmp_path / "broken.py"
        p.write_text("this is not valid python !!!")
        with pytest.raises(PluginLoadError):
            load_plugin_from_file(p)

    def test_load_from_dir(self, tmp_path: Path, plugin_file: Path):
        plugins_dir = tmp_path
        loaded = load_plugins_from_dir(plugins_dir)
        assert plugin_file.name in loaded

    def test_load_from_nonexistent_dir(self, tmp_path: Path):
        loaded = load_plugins_from_dir(tmp_path / "ghost_dir")
        assert loaded == {}

    def test_load_skips_underscore_files(self, tmp_path: Path):
        p = tmp_path / "_private.py"
        p.write_text("x = 1")
        loaded = load_plugins_from_dir(tmp_path)
        assert "_private.py" not in loaded

    def test_validate_plugin_passes(self):
        plugin = DummyStagePlugin()
        validate_plugin(plugin)  # 例外なし

    def test_safe_load_success(self, plugin_file: Path):
        result = safe_load_plugin_from_file(plugin_file)
        assert result.success is True

    def test_safe_load_failure(self, tmp_path: Path):
        result = safe_load_plugin_from_file(tmp_path / "ghost.py")
        assert result.success is False
        assert result.error != ""


# ══════════════════════════════════════════════════════════════════
# PluginManager
# ══════════════════════════════════════════════════════════════════

class TestPluginManager:
    def test_register_and_get(self):
        manager = PluginManager()
        manager.register(DummyStagePlugin())
        assert manager.get("dummy_stage") is not None

    def test_get_stage_plugins(self):
        manager = PluginManager()
        manager.register(DummyStagePlugin())
        manager.register(DummyAdapterPlugin())
        stages = manager.get_stage_plugins()
        assert len(stages) == 1

    def test_get_adapter_plugins(self):
        manager = PluginManager()
        manager.register(DummyAdapterPlugin())
        adapters = manager.get_adapter_plugins()
        assert len(adapters) == 1

    def test_load_from_file(self, plugin_file: Path):
        manager = PluginManager()
        count = manager.load_from_file(plugin_file)
        assert count == 1
        assert "file_based_stage" in manager.list_names()

    def test_load_from_dir(self, tmp_path: Path, plugin_file: Path):
        manager = PluginManager()
        result = manager.load_from_dir(tmp_path)
        assert sum(result.values()) == 1

    def test_count(self):
        manager = PluginManager()
        manager.register(DummyStagePlugin())
        assert manager.count() == 1

    def test_unregister(self):
        manager = PluginManager()
        manager.register(DummyStagePlugin())
        assert manager.unregister("dummy_stage") is True

    def test_setup_all(self):
        manager = PluginManager()
        manager.register(DummyStagePlugin())
        results = manager.setup_all()
        assert results["dummy_stage"] is True

    def test_teardown_all(self):
        manager = PluginManager()
        plugin = DummyStagePlugin()
        manager.register(plugin)
        plugin.setup()
        manager.teardown_all()
        assert plugin.is_setup is False

    def test_repr(self):
        manager = PluginManager()
        assert "PluginManager" in repr(manager)


# ══════════════════════════════════════════════════════════════════
# Pipeline 統合
# ══════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    def test_apply_to_pipeline_adds_stage(self):
        from pipeline.manager import PipelineManager

        manager = PluginManager()
        manager.register(DummyStagePlugin())
        pipeline = PipelineManager()

        count = manager.apply_to_pipeline(pipeline)
        assert count == 1
        assert "dummy_stage" in pipeline.stage_names()

    def test_plugin_stage_executes_in_pipeline(self):
        from pipeline.manager import PipelineManager

        class UppercasePlugin(StagePlugin):
            info = PluginInfo(name="uppercase_test", type=PluginType.STAGE)
            stage_name = "uppercase_test"

            def process(self, tags, context):
                for t in tags:
                    t.tag = t.tag.upper()
                return tags

        manager = PluginManager()
        manager.register(UppercasePlugin())
        pipeline = PipelineManager()
        manager.apply_to_pipeline(pipeline)

        result = pipeline.compile("masterpiece")
        tag_names = [t.tag for t in result.tags]
        assert any(t.isupper() for t in tag_names)

    def test_disabled_plugin_skipped(self):
        from pipeline.manager import PipelineManager
        from pipeline.models import StageStatus

        class DisabledPlugin(StagePlugin):
            info = PluginInfo(name="disabled_plugin", type=PluginType.STAGE)
            stage_name = "disabled_plugin"
            enabled = False

            def process(self, tags, context):
                raise RuntimeError("should not be called via wrapper.enabled check")

        manager = PluginManager()
        plugin = DisabledPlugin()
        manager.register(plugin)
        pipeline = PipelineManager()
        manager.apply_to_pipeline(pipeline)

        # apply_to_pipeline は enabled=False のプラグインを統合しない
        assert "disabled_plugin" not in pipeline.stage_names()

    def test_failing_plugin_reports_error(self):
        from pipeline.manager import PipelineManager

        manager = PluginManager()
        manager.register(FailingStagePlugin())
        pipeline = PipelineManager()
        manager.apply_to_pipeline(pipeline)

        result = pipeline.compile("masterpiece")
        failing_stage_results = [
            sr for sr in result.stage_results if sr.stage == "failing_stage"
        ]
        assert len(failing_stage_results) == 1
        assert failing_stage_results[0].error != ""
