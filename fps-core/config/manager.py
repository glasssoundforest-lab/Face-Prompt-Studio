"""
fps-core/config/manager.py — ConfigManager

責務:
  - JSON / YAML 設定ファイルの読み込み・書き込み
  - デフォルト設定とユーザー設定のディープマージ
  - ドット記法アクセス  config.get("logging.level")
  - hot reload（ファイル変更を監視して自動再読み込み）
  - 変更イベントコールバック

優先順位（高い順）:
  1. 環境変数  FPS_<SECTION>__<KEY>
  2. ユーザー設定ファイル
  3. デフォルト設定ファイル
"""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ──────────────────────────────────────────
# Exceptions
# ──────────────────────────────────────────

class ConfigError(Exception):
    """設定ファイル関連の基底例外"""

class ConfigLoadError(ConfigError):
    """読み込み失敗"""

class ConfigKeyError(ConfigError):
    """キーが存在しない"""


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _deep_merge(base: Dict, override: Dict) -> Dict:
    """override を base にディープマージして新しい辞書を返す"""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def _load_file(path: Path) -> Dict:
    """JSON / YAML ファイルを読み込んで辞書を返す"""
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ConfigLoadError(f"JSON parse error in {path}: {e}") from e

    if suffix in (".yaml", ".yml"):
        if not _YAML_AVAILABLE:
            raise ConfigLoadError(
                f"PyYAML is not installed. Cannot load {path}. "
                "Run: pip install pyyaml"
            )
        try:
            return yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            raise ConfigLoadError(f"YAML parse error in {path}: {e}") from e

    raise ConfigLoadError(f"Unsupported config format: {path.suffix}")


def _apply_env_overrides(config: Dict, prefix: str = "FPS") -> Dict:
    """
    環境変数 FPS_SECTION__KEY=value をドット記法キーとして適用する。
    例: FPS_LOGGING__LEVEL=DEBUG → config["logging"]["level"] = "DEBUG"
    区切りは __ (ダブルアンダースコア)
    """
    result = copy.deepcopy(config)
    prefix_upper = prefix.upper() + "_"
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix_upper):
            continue
        parts = env_key[len(prefix_upper):].lower().split("__")
        node = result
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = _coerce(env_val)
    return result


def _coerce(value: str) -> Any:
    """文字列を bool / int / float / str に型変換する"""
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


# ──────────────────────────────────────────
# ConfigManager
# ──────────────────────────────────────────

class ConfigManager:
    """
    FPS 設定管理クラス。

    使い方:
        cm = ConfigManager(default_path="fps-data/config.default.json")
        cm.load(user_path="my_config.json")
        level = cm.get("logging.level")        # "INFO"
        cm.set("logging.level", "DEBUG")
        cm.save("my_config.json")
        cm.watch(callback=my_fn, interval=5)   # hot reload
    """

    def __init__(
        self,
        default_path: Optional[str | Path] = None,
        env_prefix: str = "FPS",
    ) -> None:
        self._default_path: Optional[Path] = Path(default_path) if default_path else None
        self._env_prefix = env_prefix
        self._config: Dict = {}
        self._default: Dict = {}
        self._user_path: Optional[Path] = None
        self._callbacks: List[Callable[[Dict], None]] = []
        self._watch_thread: Optional[threading.Thread] = None
        self._watching = False
        self._last_mtime: float = 0.0
        self._lock = threading.RLock()

        if self._default_path and self._default_path.exists():
            self._default = _load_file(self._default_path)
            self._config = copy.deepcopy(self._default)
            logger.debug("Default config loaded: %s", self._default_path)

    # ── Load / Save ──────────────────────

    def load(self, user_path: Optional[str | Path] = None) -> "ConfigManager":
        """
        ユーザー設定ファイルを読み込んでデフォルトにマージする。
        ファイルが存在しない場合はデフォルトのみで継続。
        """
        with self._lock:
            merged = copy.deepcopy(self._default)
            if user_path:
                p = Path(user_path)
                self._user_path = p
                if p.exists():
                    user_data = _load_file(p)
                    merged = _deep_merge(merged, user_data)
                    self._last_mtime = p.stat().st_mtime
                    logger.info("User config loaded: %s", p)
                else:
                    logger.warning("User config not found, using defaults: %s", p)
            self._config = _apply_env_overrides(merged, self._env_prefix)
            self._notify()
        return self

    def save(self, path: Optional[str | Path] = None) -> None:
        """現在の設定を JSON ファイルに保存する"""
        target = Path(path) if path else self._user_path
        if not target:
            raise ConfigError("No save path specified.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            text = json.dumps(self._config, ensure_ascii=False, indent=2)
        target.write_text(text, encoding="utf-8")
        logger.info("Config saved: %s", target)

    def reload(self) -> None:
        """ユーザー設定ファイルを再読み込みする"""
        self.load(self._user_path)
        logger.info("Config reloaded.")

    # ── Get / Set ────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """
        ドット記法でキーを取得する。
        例: cm.get("logging.level")
            cm.get("cache.max_size", 128)
        """
        with self._lock:
            node = self._config
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node

    def require(self, key: str) -> Any:
        """キーが必ず存在することを要求する。なければ ConfigKeyError"""
        val = self.get(key)
        if val is None:
            raise ConfigKeyError(f"Required config key not found: '{key}'")
        return val

    def set(self, key: str, value: Any) -> None:
        """
        ドット記法でキーを設定する（メモリのみ。永続化は save() を呼ぶ）。
        例: cm.set("logging.level", "DEBUG")
        """
        with self._lock:
            parts = key.split(".")
            node = self._config
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
        logger.debug("Config set: %s = %r", key, value)

    def all(self) -> Dict:
        """現在の設定全体をコピーして返す"""
        with self._lock:
            return copy.deepcopy(self._config)

    # ── Hot Reload ───────────────────────

    def watch(
        self,
        callback: Optional[Callable[[Dict], None]] = None,
        interval: int = 5,
    ) -> None:
        """
        ユーザー設定ファイルの変更を監視してホットリロードする。
        変更検知時に callback(new_config) を呼ぶ。
        """
        if callback:
            self._callbacks.append(callback)
        if self._watching:
            return
        self._watching = True
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(interval,),
            daemon=True,
            name="fps-config-watcher",
        )
        self._watch_thread.start()
        logger.info("Config watcher started (interval=%ds).", interval)

    def unwatch(self) -> None:
        """監視を停止する"""
        self._watching = False
        logger.info("Config watcher stopped.")

    def on_change(self, callback: Callable[[Dict], None]) -> None:
        """変更コールバックを登録する"""
        self._callbacks.append(callback)

    def _watch_loop(self, interval: int) -> None:
        while self._watching:
            time.sleep(interval)
            if not self._user_path or not self._user_path.exists():
                continue
            try:
                mtime = self._user_path.stat().st_mtime
                if mtime != self._last_mtime:
                    self._last_mtime = mtime
                    logger.info("Config file changed, reloading...")
                    self.reload()
            except Exception as e:
                logger.error("Config watch error: %s", e)

    def _notify(self) -> None:
        for cb in self._callbacks:
            try:
                cb(copy.deepcopy(self._config))
            except Exception as e:
                logger.error("Config callback error: %s", e)

    def __repr__(self) -> str:
        return (
            f"ConfigManager("
            f"default={self._default_path}, "
            f"user={self._user_path}, "
            f"keys={list(self._config.keys())})"
        )
