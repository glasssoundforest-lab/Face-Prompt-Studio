"""
fps-core/plugins/base_plugin.py — Plugin 基底クラス

プラグイン開発者はこれらの基底クラスを継承して独自機能を実装する。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .models import PluginInfo, PluginType


class BasePlugin(ABC):
    """
    全プラグインの基底クラス。

    使い方:
        class MyPlugin(BasePlugin):
            info = PluginInfo(name="my_plugin", version="1.0.0")

            def setup(self, context):
                # 初期化処理
                pass

            def teardown(self):
                # 後始末処理
                pass
    """

    info: PluginInfo

    def __init__(self) -> None:
        if not hasattr(self, "info"):
            raise NotImplementedError(
                f"{self.__class__.__name__} は 'info' (PluginInfo) を定義する必要があります。"
            )
        self._setup_done = False

    def setup(self, context: dict[str, Any] | None = None) -> None:
        """プラグイン初期化処理（オーバーライド可能）"""
        self._setup_done = True

    def teardown(self) -> None:
        """プラグイン終了処理（オーバーライド可能）"""
        self._setup_done = False

    @property
    def name(self) -> str:
        return self.info.name

    @property
    def is_setup(self) -> bool:
        return self._setup_done


class StagePlugin(BasePlugin):
    """
    パイプラインステージプラグインの基底クラス。

    fps-core.pipeline.stages.BaseStage と互換のインターフェース
    （process メソッド）を実装することで PipelineManager に直接組み込める。

    使い方:
        class MyCustomStage(StagePlugin):
            info = PluginInfo(name="my_stage", type=PluginType.STAGE)
            stage_name = "my_custom_stage"

            def process(self, tags, context):
                # tags: list[TagEntry] 互換オブジェクト
                # context: dict
                return tags
    """

    stage_name: str = "custom_stage"
    enabled: bool = True

    def __init__(self) -> None:
        super().__init__()
        if not hasattr(self, "info"):
            self.info = PluginInfo(name=self.stage_name, type=PluginType.STAGE)

    @abstractmethod
    def process(self, tags: list[Any], context: dict[str, Any]) -> list[Any]:
        """
        タグリストを処理して返す（pipeline.stages.BaseStage.process 互換）。

        Args:
            tags:    TagEntry 互換オブジェクトのリスト
            context: パイプラインコンテキスト

        Returns:
            処理後のタグリスト
        """
        ...

    @property
    def name(self) -> str:
        return self.stage_name


class AdapterPlugin(BasePlugin):
    """
    出力アダプタープラグインの基底クラス。

    使い方:
        class MyAdapter(AdapterPlugin):
            info = PluginInfo(name="my_adapter", type=PluginType.ADAPTER)

            def convert(self, pipeline_result):
                return {"prompt": pipeline_result.prompt}
    """

    def __init__(self) -> None:
        super().__init__()
        if not hasattr(self, "info"):
            self.info = PluginInfo(name=self.__class__.__name__, type=PluginType.ADAPTER)

    @abstractmethod
    def convert(self, pipeline_result: Any) -> dict[str, Any]:
        """
        PipelineResult を任意の出力形式に変換する。

        Args:
            pipeline_result: PipelineResult オブジェクト

        Returns:
            変換結果の辞書
        """
        ...


class DictionarySourcePlugin(BasePlugin):
    """
    辞書ソースプラグインの基底クラス。
    外部 API・データベース等から動的に辞書エントリを供給する場合に使う。

    使い方:
        class MyDictSource(DictionarySourcePlugin):
            info = PluginInfo(name="my_dict_source", type=PluginType.DICTIONARY_SOURCE)

            def fetch_entries(self):
                return [{"key": "...", "resolved": "...", ...}]
    """

    def __init__(self) -> None:
        super().__init__()
        if not hasattr(self, "info"):
            self.info = PluginInfo(name=self.__class__.__name__, type=PluginType.DICTIONARY_SOURCE)

    @abstractmethod
    def fetch_entries(self) -> list[dict[str, Any]]:
        """
        辞書エントリを動的に取得する。

        Returns:
            辞書エントリのリスト [{"key": str, "resolved": str, ...}, ...]
        """
        ...
