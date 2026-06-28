"""
fps-tools/tests/unit/test_logger.py

FPSLogger のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_logger.py -v
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))

from fps_logging.logger import (
    FPSLogger,
    get_logger,
    ConsoleFormatter,
    JsonLinesFormatter,
)


# ──────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_fps_logger():
    """各テスト前後に FPSLogger シングルトンとロガーをリセットする"""
    FPSLogger._instance = None
    root = logging.getLogger("fps")
    root.handlers.clear()
    root.setLevel(logging.NOTSET)
    yield
    FPSLogger._instance = None
    root = logging.getLogger("fps")
    root.handlers.clear()


@pytest.fixture
def fps_logger(tmp_path: Path) -> FPSLogger:
    fl = FPSLogger()
    fl.setup(log_dir=tmp_path / "logs", level="DEBUG",
             to_console=False, to_file=True)
    return fl


@pytest.fixture
def log_path(fps_logger: FPSLogger) -> Path:
    return fps_logger._log_dir / "fps.log"


# ──────────────────────────────────────────
# ConsoleFormatter
# ──────────────────────────────────────────

class TestConsoleFormatter:
    def _make_record(self, level: int, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="fps.test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None,
        )

    def test_format_contains_level(self):
        fmt    = ConsoleFormatter(use_color=False)
        record = self._make_record(logging.INFO, "hello")
        result = fmt.format(record)
        assert "INFO" in result

    def test_format_contains_message(self):
        fmt    = ConsoleFormatter(use_color=False)
        record = self._make_record(logging.WARNING, "watch out")
        result = fmt.format(record)
        assert "watch out" in result

    def test_format_contains_module(self):
        fmt    = ConsoleFormatter(use_color=False)
        record = self._make_record(logging.DEBUG, "msg")
        result = fmt.format(record)
        assert "fps.test" in result


# ──────────────────────────────────────────
# JsonLinesFormatter
# ──────────────────────────────────────────

class TestJsonLinesFormatter:
    def _make_record(self, level: int, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="fps.test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None,
        )

    def test_valid_json(self):
        fmt    = JsonLinesFormatter()
        record = self._make_record(logging.INFO, "json test")
        result = fmt.format(record)
        parsed = json.loads(result)   # パースできれば OK
        assert parsed["msg"] == "json test"

    def test_required_fields(self):
        fmt    = JsonLinesFormatter()
        record = self._make_record(logging.ERROR, "err")
        parsed = json.loads(fmt.format(record))
        for field in ("ts", "level", "module", "msg"):
            assert field in parsed, f"Missing field: {field}"

    def test_level_name(self):
        fmt    = JsonLinesFormatter()
        record = self._make_record(logging.WARNING, "warn")
        parsed = json.loads(fmt.format(record))
        assert parsed["level"] == "WARNING"

    def test_ts_is_iso8601(self):
        from datetime import datetime
        fmt    = JsonLinesFormatter()
        record = self._make_record(logging.DEBUG, "ts test")
        parsed = json.loads(fmt.format(record))
        # ISO 8601 としてパースできること
        datetime.fromisoformat(parsed["ts"])


# ──────────────────────────────────────────
# FPSLogger — setup
# ──────────────────────────────────────────

class TestFPSLoggerSetup:
    def test_setup_creates_log_file(self, tmp_path: Path):
        fl = FPSLogger()
        fl.setup(log_dir=tmp_path / "logs", level="DEBUG",
                 to_console=False, to_file=True)
        assert (tmp_path / "logs" / "fps.log").exists()

    def test_double_setup_is_safe(self, tmp_path: Path):
        fl = FPSLogger()
        fl.setup(log_dir=tmp_path / "logs", level="INFO",
                 to_console=False, to_file=True)
        fl.setup(log_dir=tmp_path / "logs", level="DEBUG",
                 to_console=False, to_file=True)
        # ハンドラが重複しないこと
        root = logging.getLogger("fps")
        assert len(root.handlers) == 1

    def test_setup_from_config(self, tmp_path: Path):
        sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))
        from config.manager import ConfigManager
        cm = ConfigManager()
        cm.set("logging.level",        "WARNING")
        cm.set("logging.dir",          str(tmp_path / "logs"))
        cm.set("logging.max_bytes",    1024)
        cm.set("logging.backup_count", 3)

        fl = FPSLogger()
        fl.setup_from_config(cm)
        assert fl.get_level() == "WARNING"


# ──────────────────────────────────────────
# FPSLogger — get()
# ──────────────────────────────────────────

class TestFPSLoggerGet:
    def test_get_returns_logger(self, fps_logger: FPSLogger):
        logger = fps_logger.get("config")
        assert isinstance(logger, logging.Logger)

    def test_get_auto_prefix(self, fps_logger: FPSLogger):
        logger = fps_logger.get("config")
        assert logger.name == "fps.config"

    def test_get_already_prefixed(self, fps_logger: FPSLogger):
        logger = fps_logger.get("fps.config")
        assert logger.name == "fps.config"

    def test_different_names_different_loggers(self, fps_logger: FPSLogger):
        l1 = fps_logger.get("config")
        l2 = fps_logger.get("dictionary")
        assert l1 is not l2


# ──────────────────────────────────────────
# FPSLogger — level control
# ──────────────────────────────────────────

class TestFPSLoggerLevel:
    def test_set_level_debug(self, fps_logger: FPSLogger):
        fps_logger.set_level("DEBUG")
        assert fps_logger.get_level() == "DEBUG"

    def test_set_level_error(self, fps_logger: FPSLogger):
        fps_logger.set_level("ERROR")
        assert fps_logger.get_level() == "ERROR"

    def test_handlers_level_updated(self, fps_logger: FPSLogger):
        fps_logger.set_level("WARNING")
        root = logging.getLogger("fps")
        for handler in root.handlers:
            assert handler.level == logging.WARNING


# ──────────────────────────────────────────
# FPSLogger — ファイル出力
# ──────────────────────────────────────────

class TestFPSLoggerFileOutput:
    def test_info_written_to_file(self, fps_logger: FPSLogger, log_path: Path):
        logger = fps_logger.get("test")
        logger.info("file output test")
        logging.getLogger("fps").handlers[0].flush()
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert any("file output test" in l for l in lines)

    def test_output_is_valid_json_lines(self, fps_logger: FPSLogger, log_path: Path):
        logger = fps_logger.get("test")
        logger.info("json line 1")
        logger.warning("json line 2")
        logging.getLogger("fps").handlers[0].flush()
        lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        for line in lines:
            json.loads(line)   # 各行が有効な JSON であること

    def test_debug_below_level_not_written(self, tmp_path: Path):
        fl = FPSLogger()
        fl.setup(log_dir=tmp_path / "logs", level="WARNING",
                 to_console=False, to_file=True)
        logger = fl.get("test")
        logger.debug("should not appear")
        logging.getLogger("fps").handlers[0].flush()
        content = (tmp_path / "logs" / "fps.log").read_text(encoding="utf-8")
        assert "should not appear" not in content


# ──────────────────────────────────────────
# get_logger() ショートカット
# ──────────────────────────────────────────

class TestGetLoggerShortcut:
    def test_get_logger_returns_logger(self, fps_logger: FPSLogger):
        FPSLogger._instance = fps_logger
        logger = get_logger("mymodule")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "fps.mymodule"

    def test_get_logger_creates_instance_if_needed(self):
        # シングルトンがなくても動作すること
        logger = get_logger("bootstrap")
        assert isinstance(logger, logging.Logger)


# ──────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────

class TestSingleton:
    def test_instance_returns_same_object(self):
        a = FPSLogger.instance()
        b = FPSLogger.instance()
        assert a is b

    def test_repr(self, fps_logger: FPSLogger):
        r = repr(fps_logger)
        assert "FPSLogger" in r
        assert "DEBUG" in r
