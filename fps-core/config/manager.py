"""
fps-core/config/manager.py — ConfigManager

責務:
  - JSON / YAML 設定ファイルの読み込み・書き込み
  - デフォルト値のマージ（ユーザー設定がデフォルトを上書き）
  - Hot reload（ファイル変更を検知して自動再読み込み）
  - 設定値への型安全なアクセス（ドット記法対応）

優先順位（高→低）:
  1. ユーザー設定   fps-data/config/user.json
  2. デフォルト設定 fps-data/config/default.json
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


class ConfigError(Exception):
    """設定ファイル関連の例外"""


class ConfigManager:
    """
    JSON 優先・YAML 対応の設定マネージャー。

    Usage:
        cfg = ConfigManager(default_path="fps-data/config/default.json")
        cfg.load_user("fps-data/config/user.json")
        cfg.start_hot_reload()

        value = cfg.get("pipeline.max_tokens", default=128)
    """

    def __init__(
        self,
        default_path: str | Path | None = None,
        *,
        hot_reload_interval: float = 2.0,
    ) -> None:
        self._data: dict[str, Any] = {}
        self._defaults: dict[str, Any] = {}
        self._user_path: Path | None = None
        self._hot_reload_interval = hot_reload_interval
        self._hot_reload_thread: threading.Thread | None = None
        self._hot_reload_active = False
        self._last_mtime: float | None = None
        self._on_reload_callbacks: list[Callable[[], None]] = []

        if default_path is not None:
            self.load_default(default_path)

    # ──────────────────────────────────────────
    # Load
    # ──────────────────────────────────────────

    def load_default(self, path: str | Path) -> None:
        """デフォルト設定を読み込む（ユーザー設定で上書き可能）"""
        self._defaults = self._read_file(Path(path))
        self._merge()

    def load_user(self, path: str | Path) -> None:
        """ユーザー設定を読み込む（デフォルトを上書き）"""
        self._user_path = Path(path)
        if self._user_path.exists():
            user_data = self._read_file(self._user_path)
            self._last_mtime = self._user_path.stat().st_mtime
        else:
            user_data = {}
            self._last_mtime = None
        self._user_data = user_data
        self._merge()

    def reload(self) -> bool:
        """ユーザー設定を手動で再読み込みする。変更があった場合 True を返す"""
        if self._user_path is None or not self._user_path.exists():
            return False
        try:
            user_data = self._read_file(self._user_path)
            self._last_mtime = self._user_path.stat().st_mtime
            if user_data == getattr(self, "_user_data", {}):
                return False
            self._user_data = user_data
            self._merge()
            for cb in self._on_reload_callbacks:
                cb()
            return True
        except ConfigError:
            return False

    # ──────────────────────────────────────────
    # Hot reload
    # ──────────────────────────────────────────

    def start_hot_reload(self) -> None:
        """バックグラウンドスレッドでファイル変更を監視する"""
        if self._hot_reload_active:
            return
        self._hot_reload_active = True
        self._hot_reload_thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="fps-config-watcher"
        )
        self._hot_reload_thread.start()

    def stop_hot_reload(self) -> None:
        """ホットリロードを停止する"""
        self._hot_reload_active = False

    def on_reload(self, callback: Callable[[], None]) -> None:
        """再読み込み時に呼ばれるコールバックを登録する"""
        self._on_reload_callbacks.append(callback)

    def _watch_loop(self) -> None:
        while self._hot_reload_active:
            time.sleep(self._hot_reload_interval)
            if self._user_path and self._user_path.exists():
                mtime = self._user_path.stat().st_mtime
                if self._last_mtime is not None and mtime != self._last_mtime:
                    self.reload()

    # ──────────────────────────────────────────
    # Get / Set
    # ──────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """
        ドット記法で設定値を取得する。

        例: cfg.get("pipeline.max_tokens", default=128)
        """
        keys = key.split(".")
        node = self._data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def set(self, key: str, value: Any) -> None:
        """
        ドット記法で設定値を変更する（メモリのみ・ファイルは変更しない）。

        例: cfg.set("pipeline.max_tokens", 256)
        """
        keys = key.split(".")
        node = self._data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value

    def save_user(self, path: str | Path | None = None) -> None:
        """ユーザー設定をファイルに書き出す"""
        target = Path(path) if path else self._user_path
        if target is None:
            raise ConfigError("保存先パスが指定されていません")
        target.parent.mkdir(parents=True, exist_ok=True)
        user_data = getattr(self, "_user_data", {})
        self._write_file(target, user_data)

    def all(self) -> dict[str, Any]:
        """マージ済み設定全体を返す"""
        return dict(self._data)

    # ──────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────

    def _merge(self) -> None:
        """デフォルト + ユーザー設定をディープマージする"""
        self._data = _deep_merge(self._defaults, getattr(self, "_user_data", {}))

    @staticmethod
    def _read_file(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ConfigError(f"設定ファイルが見つかりません: {path}")
        suffix = path.suffix.lower()
        text = path.read_text(encoding="utf-8")
        if suffix == ".json":
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                raise ConfigError(f"JSON パースエラー ({path}): {e}") from e
        if suffix in (".yaml", ".yml"):
            if not _YAML_AVAILABLE:
                raise ConfigError("PyYAML がインストールされていません: pip install pyyaml")
            try:
                return yaml.safe_load(text) or {}
            except yaml.YAMLError as e:
                raise ConfigError(f"YAML パースエラー ({path}): {e}") from e
        raise ConfigError(f"未対応の拡張子: {suffix}（.json / .yaml / .yml のみ）")

    @staticmethod
    def _write_file(path: Path, data: dict[str, Any]) -> None:
        suffix = path.suffix.lower()
        if suffix == ".json":
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        elif suffix in (".yaml", ".yml"):
            if not _YAML_AVAILABLE:
                raise ConfigError("PyYAML がインストールされていません")
            path.write_text(
                yaml.dump(data, allow_unicode=True, default_flow_style=False),
                encoding="utf-8",
            )
        else:
            raise ConfigError(f"未対応の拡張子: {suffix}")


# ──────────────────────────────────────────
# Utility
# ──────────────────────────────────────────


def _deep_merge(base: dict, override: dict) -> dict:
    """
    base に override をディープマージして新しい dict を返す。
    override の値が優先される。
    """
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
