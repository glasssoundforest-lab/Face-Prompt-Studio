"""
fps-core/plugins/exceptions.py — Plugin 例外定義
"""

from __future__ import annotations


class PluginError(Exception):
    """プラグイン操作の基底例外"""


class PluginLoadError(PluginError):
    """プラグインのロード失敗"""


class PluginNotFoundError(PluginError):
    """指定名のプラグインが見つからない"""


class PluginDependencyError(PluginError):
    """プラグイン依存関係の解決失敗"""


class PluginValidationError(PluginError):
    """プラグインがインターフェース要件を満たしていない"""
