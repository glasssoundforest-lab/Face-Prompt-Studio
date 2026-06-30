"""
fps-core/plugins/registry.py — Plugin Registry

ロード済みプラグインの登録・検索・依存関係解決を行う。
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from .base_plugin import BasePlugin
from .exceptions import PluginDependencyError, PluginNotFoundError
from .models import PluginType

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    プラグインレジストリ。

    使い方:
        registry = PluginRegistry()
        registry.register(MyPluginInstance)
        plugin = registry.get("my_plugin")
        stages = registry.get_by_type(PluginType.STAGE)
    """

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._lock = threading.RLock()

    # ══════════════════════════════════════════════════════════════
    # Register
    # ══════════════════════════════════════════════════════════════

    def register(self, plugin: BasePlugin, replace: bool = False) -> None:
        """
        プラグインインスタンスを登録する。

        Args:
            plugin:  BasePlugin のサブクラスインスタンス
            replace: True なら同名プラグインを上書き許可
        """
        with self._lock:
            name = plugin.name
            if name in self._plugins and not replace:
                logger.warning("Plugin '%s' is already registered; skipping.", name)
                return

            # 依存関係チェック
            missing = [dep for dep in plugin.info.requires if dep not in self._plugins]
            if missing:
                raise PluginDependencyError(
                    f"プラグイン '{name}' の依存プラグインが未登録です: {missing}"
                )

            self._plugins[name] = plugin
            logger.info(
                "Plugin registered: %s (type=%s, version=%s)",
                name,
                plugin.info.type,
                plugin.info.version,
            )

    def unregister(self, name: str) -> bool:
        """プラグインの登録を解除する"""
        with self._lock:
            if name not in self._plugins:
                return False
            plugin = self._plugins[name]
            if plugin.is_setup:
                plugin.teardown()
            del self._plugins[name]
            logger.info("Plugin unregistered: %s", name)
            return True

    # ══════════════════════════════════════════════════════════════
    # Get / Query
    # ══════════════════════════════════════════════════════════════

    def get(self, name: str) -> BasePlugin:
        """
        名前でプラグインを取得する。

        Raises:
            PluginNotFoundError: 見つからない場合
        """
        with self._lock:
            if name not in self._plugins:
                raise PluginNotFoundError(f"プラグインが見つかりません: '{name}'")
            return self._plugins[name]

    def get_or_none(self, name: str) -> BasePlugin | None:
        """名前でプラグインを取得する（見つからなければ None）"""
        with self._lock:
            return self._plugins.get(name)

    def get_by_type(self, plugin_type: PluginType) -> list[BasePlugin]:
        """指定タイプの全プラグインを返す"""
        with self._lock:
            return [p for p in self._plugins.values() if p.info.type == plugin_type]

    def list_all(self) -> list[BasePlugin]:
        """登録済み全プラグインを返す"""
        with self._lock:
            return list(self._plugins.values())

    def list_names(self) -> list[str]:
        """登録済みプラグイン名一覧を返す"""
        with self._lock:
            return sorted(self._plugins.keys())

    def exists(self, name: str) -> bool:
        with self._lock:
            return name in self._plugins

    def count(self) -> int:
        with self._lock:
            return len(self._plugins)

    # ══════════════════════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════════════════════

    def setup_all(self, context: dict[str, Any] | None = None) -> dict[str, bool]:
        """
        登録済み全プラグインの setup() を依存順に呼び出す。

        Returns:
            {plugin_name: success}
        """
        with self._lock:
            order = self._resolve_dependency_order()
            results: dict[str, bool] = {}
            for name in order:
                plugin = self._plugins[name]
                try:
                    plugin.setup(context)
                    results[name] = True
                except Exception as e:
                    logger.error("Plugin setup failed: %s — %s", name, e)
                    results[name] = False
            return results

    def teardown_all(self) -> None:
        """登録済み全プラグインの teardown() を呼び出す"""
        with self._lock:
            for plugin in self._plugins.values():
                if plugin.is_setup:
                    try:
                        plugin.teardown()
                    except Exception as e:
                        logger.error("Plugin teardown failed: %s — %s", plugin.name, e)

    def _resolve_dependency_order(self) -> list[str]:
        """依存関係を考慮したトポロジカルソート順を返す"""
        visited: set[str] = set()
        order: list[str] = []

        def visit(name: str, stack: set[str]) -> None:
            if name in visited:
                return
            if name in stack:
                raise PluginDependencyError(f"循環依存を検出しました: {name}")
            if name not in self._plugins:
                return
            stack.add(name)
            for dep in self._plugins[name].info.requires:
                visit(dep, stack)
            stack.discard(name)
            visited.add(name)
            order.append(name)

        for name in self._plugins:
            visit(name, set())

        return order

    def __repr__(self) -> str:
        return f"PluginRegistry(plugins={self.list_names()})"
