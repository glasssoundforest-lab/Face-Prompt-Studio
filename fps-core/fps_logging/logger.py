"""
fps-core/logging/logger.py — FPS Logger

責務:
  - 構造化ログ（JSON Lines 形式）
  - ローテーティングファイルハンドラ
  - コンソール出力（カラー対応）
  - ConfigManager との連携
  - モジュール別ロガー取得  get_logger(__name__)
  - ログレベル動的変更

ログ形式:
  コンソール: [LEVEL] timestamp  module — message
  ファイル:   JSON Lines  {"ts":..., "level":..., "module":..., "msg":...}
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.manager import ConfigManager


# ──────────────────────────────────────────
# ANSI カラー定義
# ──────────────────────────────────────────

_RESET = "\033[0m"
_BOLD = "\033[1m"
_COLORS = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[35m",  # Magenta
}


def _supports_color() -> bool:
    """ターミナルがカラーをサポートしているか判定する"""
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


# ──────────────────────────────────────────
# Formatters
# ──────────────────────────────────────────


class ConsoleFormatter(logging.Formatter):
    """
    コンソール用フォーマッタ。
    [LEVEL] HH:MM:SS  module — message
    """

    def __init__(self, use_color: bool = True) -> None:
        super().__init__()
        self._use_color = use_color and _supports_color()

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).strftime("%H:%M:%S")
        level = record.levelname
        mod = record.name
        msg = record.getMessage()

        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)

        if self._use_color:
            color = _COLORS.get(level, "")
            level_str = f"{color}{_BOLD}[{level:<8}]{_RESET}"
        else:
            level_str = f"[{level:<8}]"

        return f"{level_str} {ts}  {mod} — {msg}"


class JsonLinesFormatter(logging.Formatter):
    """
    ファイル用フォーマッタ（JSON Lines）。
    各行が独立した JSON オブジェクト。
    {"ts":"...","level":"...","module":"...","msg":"...","extra":{}}
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        payload: dict = {
            "ts": ts,
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # logging.extra で渡した追加フィールドを含める
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in logging.LogRecord.__dict__
            and not k.startswith("_")
            and k
            not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "taskName",
            )
        }
        if extras:
            payload["extra"] = extras

        return json.dumps(payload, ensure_ascii=False)


# ──────────────────────────────────────────
# FPSLogger
# ──────────────────────────────────────────


class FPSLogger:
    """
    FPS ロギングシステム。

    使い方:
        fps_logger = FPSLogger()
        fps_logger.setup(log_dir="logs", level="INFO")
        logger = fps_logger.get("fps_core.config")
        logger.info("Config loaded.")
    """

    _instance: FPSLogger | None = None

    def __init__(self) -> None:
        self._initialized = False
        self._log_dir: Path | None = None
        self._level: int = logging.INFO
        self._root_name = "fps"

    # ── Setup ────────────────────────────

    def setup(
        self,
        log_dir: str | Path = "logs",
        level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        use_color: bool = True,
        to_console: bool = True,
        to_file: bool = True,
    ) -> FPSLogger:
        """
        ロギングシステムを初期化する。
        二重初期化は安全にスキップされる。
        """
        if self._initialized:
            return self

        self._level = getattr(logging, level.upper(), logging.INFO)
        self._log_dir = Path(log_dir)

        root = logging.getLogger(self._root_name)
        root.setLevel(self._level)
        root.handlers.clear()

        # コンソールハンドラ
        if to_console:
            ch = logging.StreamHandler(sys.stderr)
            ch.setLevel(self._level)
            ch.setFormatter(ConsoleFormatter(use_color=use_color))
            root.addHandler(ch)

        # ファイルハンドラ（JSON Lines, ローテーティング）
        if to_file:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            log_path = self._log_dir / "fps.log"
            fh = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            fh.setLevel(self._level)
            fh.setFormatter(JsonLinesFormatter())
            root.addHandler(fh)

        # 外部ライブラリのログを抑制
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)

        self._initialized = True
        log_dir_str = str(log_path) if to_file else "—"
        root.debug("FPSLogger initialized. level=%s log_dir=%s", level, log_dir_str)
        return self

    def setup_from_config(self, config: ConfigManager) -> FPSLogger:
        """ConfigManager から設定を読み込んでセットアップする"""
        return self.setup(
            log_dir=config.get("logging.dir", "logs"),
            level=config.get("logging.level", "INFO"),
            max_bytes=config.get("logging.max_bytes", 10 * 1024 * 1024),
            backup_count=config.get("logging.backup_count", 5),
        )

    # ── Get logger ───────────────────────

    def get(self, name: str) -> logging.Logger:
        """
        モジュール別ロガーを取得する。
        name は fps. プレフィックスがなければ自動付与。
        例: fps_logger.get("config") → logging.getLogger("fps.config")
        """
        if not name.startswith(self._root_name + "."):
            name = f"{self._root_name}.{name}"
        return logging.getLogger(name)

    # ── Level control ────────────────────

    def set_level(self, level: str) -> None:
        """全ハンドラのログレベルを動的に変更する"""
        lvl = getattr(logging, level.upper(), logging.INFO)
        root = logging.getLogger(self._root_name)
        root.setLevel(lvl)
        for handler in root.handlers:
            handler.setLevel(lvl)
        self._level = lvl

    def get_level(self) -> str:
        """現在のログレベル名を返す"""
        return logging.getLevelName(self._level)

    # ── Singleton ────────────────────────

    @classmethod
    def instance(cls) -> FPSLogger:
        """グローバルシングルトンを返す"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __repr__(self) -> str:
        return (
            f"FPSLogger(level={self.get_level()}, "
            f"log_dir={self._log_dir}, "
            f"initialized={self._initialized})"
        )


# ──────────────────────────────────────────
# モジュールレベル便利関数
# ──────────────────────────────────────────


def get_logger(name: str) -> logging.Logger:
    """
    FPSLogger シングルトンからロガーを取得するショートカット。

    使い方（各モジュールの先頭）:
        from logging.logger import get_logger
        logger = get_logger(__name__)
    """
    return FPSLogger.instance().get(name)
