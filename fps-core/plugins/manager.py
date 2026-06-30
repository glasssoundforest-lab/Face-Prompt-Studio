"""
fps-core/plugins/manager.py — PluginManager

プラグインのロード・登録・PipelineManager への統合を一括管理する。

Public API:
  - load_from_dir(path)        ディレクトリから一括ロード・登録
  - load_from_file(path)       単一ファイルからロード・登録
  - register(plugin)           プラグインインスタンスを直接登録
  - get_stage_plugins()        StagePlugin 一覧（PipelineManager 統合用）
  - get_adapter_plugins()      AdapterPlugin 一覧
  - apply_to_pipeline(pm)      PipelineManager にステージプラグインを統合
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base_plugin import AdapterPlugin, BasePlugin, StagePlugin
from .loader import load_plugin_from_file, load_plugins_from_dir
from .models import PluginType
from .registry import PluginRegistry

logger = logging.getLogger(__name__)


class PluginManager:
    """
    FPS プラグイン統合管理クラス。

    使い方:
        pm_plugins = PluginManager()
        pm_plugins.load_from_dir("fps-data/plugins")
        pm_plugins.setup_all()

        from pipeline.manager import PipelineManager
        pipeline = PipelineManager()
        pm_plugins.apply_to_pipeline(pipeline)
    """

    def __init__(self) -> None:
        self._registry = PluginRegistry()

    # ══════════════════════════════════════════════════════════════
    # Load
    # ══════════════════════════════════════════════════════════════

    def load_from_dir(self, directory: str | Path) -> dict[str, int]:
        """ディレクトリから全プラグインをロード・登録する"""
        loaded = load_plugins_from_dir(directory)
        result: dict[str, int] = {}
        for filename, plugins in loaded.items():
            count = 0
            for plugin in plugins:
                try:
                    self._registry.register(plugin)
                    count += 1
                except Exception as e:
                    logger.error("Plugin registration failed: %s — %s", plugin.name, e)
            result[filename] = count
        return result

    def load_from_file(self, path: str | Path) -> int:
        """単一ファイルからプラグインをロード・登録する"""
        plugins = load_plugin_from_file(path)
        count = 0
        for plugin in plugins:
            self._registry.register(plugin)
            count += 1
        return count

    def register(self, plugin: BasePlugin, replace: bool = False) -> None:
        """プラグインインスタンスを直接登録する"""
        self._registry.register(plugin, replace=replace)

    def unregister(self, name: str) -> bool:
        """プラグインの登録を解除する"""
        return self._registry.unregister(name)

    # ══════════════════════════════════════════════════════════════
    # Query
    # ══════════════════════════════════════════════════════════════

    def get(self, name: str) -> BasePlugin:
        return self._registry.get(name)

    def get_or_none(self, name: str) -> BasePlugin | None:
        return self._registry.get_or_none(name)

    def get_stage_plugins(self) -> list[StagePlugin]:
        """登録済み StagePlugin 一覧を返す"""
        return [
            p for p in self._registry.get_by_type(PluginType.STAGE) if isinstance(p, StagePlugin)
        ]

    def get_adapter_plugins(self) -> list[AdapterPlugin]:
        """登録済み AdapterPlugin 一覧を返す"""
        return [
            p
            for p in self._registry.get_by_type(PluginType.ADAPTER)
            if isinstance(p, AdapterPlugin)
        ]

    def list_names(self) -> list[str]:
        return self._registry.list_names()

    def count(self) -> int:
        return self._registry.count()

    # ══════════════════════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════════════════════

    def setup_all(self, context: dict[str, Any] | None = None) -> dict[str, bool]:
        """全プラグインを初期化する"""
        return self._registry.setup_all(context)

    def teardown_all(self) -> None:
        """全プラグインを終了処理する"""
        self._registry.teardown_all()

    # ══════════════════════════════════════════════════════════════
    # Pipeline Integration
    # ══════════════════════════════════════════════════════════════

    def apply_to_pipeline(self, pipeline_manager: Any) -> int:
        """
        登録済み StagePlugin を PipelineManager に統合する。

        Args:
            pipeline_manager: PipelineManager インスタンス

        Returns:
            統合したステージプラグイン数
        """
        stage_plugins = self.get_stage_plugins()
        count = 0
        for plugin in stage_plugins:
            if not plugin.enabled:
                continue
            wrapper = _StagePluginWrapper(plugin)
            pipeline_manager._stages.append(wrapper)
            count += 1
            logger.info("Stage plugin integrated into pipeline: %s", plugin.name)
        return count

    def __repr__(self) -> str:
        return f"PluginManager(plugins={self.list_names()})"


class _StagePluginWrapper:
    """StagePlugin を pipeline.stages.BaseStage 互換にアダプトする内部ラッパー"""

    def __init__(self, plugin: StagePlugin) -> None:
        self._plugin = plugin
        self.name = plugin.stage_name
        self.enabled = plugin.enabled

    def run(self, tags: list[Any], context: dict[str, Any]) -> tuple[list[Any], Any]:
        from pipeline.models import StageResult, StageStatus

        if not self.enabled:
            return tags, StageResult(
                stage=self.name,
                status=StageStatus.SKIPPED,
                tags_in=len(tags),
                tags_out=len(tags),
            )
        try:
            result_tags = self._plugin.process(tags, context)
            return result_tags, StageResult(
                stage=self.name,
                status=StageStatus.DONE,
                tags_in=len(tags),
                tags_out=len(result_tags),
            )
        except Exception as e:
            return tags, StageResult(
                stage=self.name,
                status=StageStatus.ERROR,
                tags_in=len(tags),
                error=str(e),
            )
