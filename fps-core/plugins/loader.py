"""
fps-core/plugins/loader.py — Plugin Loader

ファイルパス・ディレクトリ・モジュール名からプラグインを動的にロードする。
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from types import ModuleType

from .base_plugin import BasePlugin
from .exceptions import PluginLoadError, PluginValidationError
from .models import PluginLoadResult

logger = logging.getLogger(__name__)


def load_plugin_from_file(path: str | Path) -> list[BasePlugin]:
    """
    単一の .py ファイルから BasePlugin サブクラスを発見してインスタンス化する。

    Args:
        path: プラグインファイルのパス

    Returns:
        発見した BasePlugin インスタンスのリスト

    Raises:
        PluginLoadError: ファイルの読み込み・実行に失敗した場合
    """
    p = Path(path)
    if not p.exists():
        raise PluginLoadError(f"プラグインファイルが見つかりません: {p}")
    if p.suffix != ".py":
        raise PluginLoadError(f"プラグインファイルは .py である必要があります: {p}")

    module_name = f"fps_plugin_{p.stem}_{id(p)}"
    spec = importlib.util.spec_from_file_location(module_name, p)
    if spec is None or spec.loader is None:
        raise PluginLoadError(f"モジュール仕様の作成に失敗しました: {p}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        sys.modules.pop(module_name, None)
        raise PluginLoadError(f"プラグインファイルの実行に失敗しました: {p}\n{e}") from e

    return _discover_plugin_classes(module)


def load_plugins_from_dir(directory: str | Path) -> dict[str, list[BasePlugin]]:
    """
    ディレクトリ内の全 .py ファイルからプラグインをロードする。

    Args:
        directory: プラグインディレクトリ

    Returns:
        {filename: [BasePlugin, ...]}（ロード失敗ファイルは含まない）
    """
    d = Path(directory)
    if not d.exists():
        return {}

    results: dict[str, list[BasePlugin]] = {}
    for py_file in sorted(d.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            plugins = load_plugin_from_file(py_file)
            if plugins:
                results[py_file.name] = plugins
        except PluginLoadError as e:
            logger.error("Plugin load failed: %s — %s", py_file.name, e)

    return results


def load_plugin_from_module(module_path: str) -> list[BasePlugin]:
    """
    インストール済み Python モジュールから BasePlugin サブクラスをロードする。

    Args:
        module_path: モジュールパス（例: "my_package.my_plugin"）

    Returns:
        発見した BasePlugin インスタンスのリスト
    """
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise PluginLoadError(f"モジュールのインポートに失敗しました: {module_path}\n{e}") from e

    return _discover_plugin_classes(module)


def validate_plugin(plugin: BasePlugin) -> None:
    """
    プラグインインスタンスが基本要件を満たしているか検証する。

    Raises:
        PluginValidationError: 要件を満たさない場合
    """
    if not hasattr(plugin, "info"):
        raise PluginValidationError(f"{plugin.__class__.__name__}: 'info' が定義されていません")
    if not plugin.info.name:
        raise PluginValidationError(f"{plugin.__class__.__name__}: info.name が空です")


# ── Private ──────────────────────────────────────────────────────────


def _discover_plugin_classes(module: ModuleType) -> list[BasePlugin]:
    """モジュール内の BasePlugin サブクラスを発見してインスタンス化する"""
    instances: list[BasePlugin] = []

    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, BasePlugin)
            and obj is not BasePlugin
            and not inspect.isabstract(obj)
            and obj.__module__ == module.__name__
        ):
            try:
                instance = obj()
                validate_plugin(instance)
                instances.append(instance)
            except Exception as e:
                logger.error("Plugin instantiation failed: %s — %s", obj.__name__, e)

    return instances


def safe_load_plugin_from_file(path: str | Path) -> PluginLoadResult:
    """
    load_plugin_from_file の例外安全版。失敗しても PluginLoadResult を返す。
    """
    try:
        plugins = load_plugin_from_file(path)
        if not plugins:
            return PluginLoadResult(
                success=False,
                plugin_name=str(path),
                error="No BasePlugin subclass found in file.",
            )
        names = ", ".join(p.name for p in plugins)
        return PluginLoadResult(success=True, plugin_name=names)
    except PluginLoadError as e:
        return PluginLoadResult(success=False, plugin_name=str(path), error=str(e))
