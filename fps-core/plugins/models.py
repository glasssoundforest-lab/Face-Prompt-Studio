"""
fps-core/plugins/models.py — Plugin データモデル
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PluginType(StrEnum):
    STAGE = "stage"  # パイプラインステージプラグイン
    ADAPTER = "adapter"  # 出力アダプタープラグイン
    DICTIONARY_SOURCE = "dictionary_source"  # 辞書ソースプラグイン
    GENERIC = "generic"  # 汎用プラグイン


@dataclass(slots=True)
class PluginInfo:
    """プラグインのメタ情報"""

    name: str
    version: str = "0.1.0"
    type: PluginType = PluginType.GENERIC
    description: str = ""
    author: str = ""
    requires: list[str] = field(default_factory=list)  # 依存プラグイン名
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PluginLoadResult:
    """プラグインロード結果"""

    success: bool
    plugin_name: str
    error: str = ""
