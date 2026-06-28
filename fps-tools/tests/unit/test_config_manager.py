"""
fps-tools/tests/unit/test_config_manager.py

ConfigManager のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_config_manager.py -v
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

# fps-core をパスに追加
sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))

from config.manager import (
    ConfigManager,
    ConfigError,
    ConfigKeyError,
    ConfigLoadError,
    _deep_merge,
    _coerce,
)


# ──────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────

DEFAULT_CONFIG = {
    "fps": {"version": "0.2.0-dev", "debug": False},
    "logging": {"level": "INFO", "dir": "logs"},
    "cache": {"enabled": True, "max_size": 256},
}

USER_CONFIG = {
    "logging": {"level": "DEBUG"},
    "cache": {"max_size": 512},
}


@pytest.fixture
def default_json(tmp_path: Path) -> Path:
    p = tmp_path / "config.default.json"
    p.write_text(json.dumps(DEFAULT_CONFIG), encoding="utf-8")
    return p


@pytest.fixture
def user_json(tmp_path: Path) -> Path:
    p = tmp_path / "config.user.json"
    p.write_text(json.dumps(USER_CONFIG), encoding="utf-8")
    return p


@pytest.fixture
def cm(default_json: Path) -> ConfigManager:
    return ConfigManager(default_path=default_json)


# ──────────────────────────────────────────
# _deep_merge
# ──────────────────────────────────────────

class TestDeepMerge:
    def test_flat_override(self):
        base     = {"a": 1, "b": 2}
        override = {"b": 99, "c": 3}
        result   = _deep_merge(base, override)
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_nested_merge(self):
        base     = {"logging": {"level": "INFO", "dir": "logs"}}
        override = {"logging": {"level": "DEBUG"}}
        result   = _deep_merge(base, override)
        assert result["logging"]["level"] == "DEBUG"
        assert result["logging"]["dir"] == "logs"   # 残存確認

    def test_does_not_mutate_base(self):
        base     = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        _deep_merge(base, override)
        assert base["a"]["b"] == 1   # 元は変わらない


# ──────────────────────────────────────────
# _coerce
# ──────────────────────────────────────────

class TestCoerce:
    def test_bool_true(self):
        assert _coerce("true") is True
        assert _coerce("yes")  is True
        assert _coerce("1")    is True

    def test_bool_false(self):
        assert _coerce("false") is False
        assert _coerce("no")    is False
        assert _coerce("0")     is False

    def test_int(self):
        assert _coerce("42") == 42
        assert isinstance(_coerce("42"), int)

    def test_float(self):
        assert _coerce("3.14") == pytest.approx(3.14)

    def test_str(self):
        assert _coerce("hello") == "hello"


# ──────────────────────────────────────────
# ConfigManager — 初期化
# ──────────────────────────────────────────

class TestConfigManagerInit:
    def test_load_default(self, cm: ConfigManager):
        assert cm.get("fps.version") == "0.2.0-dev"

    def test_no_default_path(self):
        cm = ConfigManager()
        assert cm.get("anything") is None

    def test_nonexistent_default(self, tmp_path: Path):
        cm = ConfigManager(default_path=tmp_path / "nonexistent.json")
        assert cm.get("fps.version") is None


# ──────────────────────────────────────────
# ConfigManager — load()
# ──────────────────────────────────────────

class TestConfigManagerLoad:
    def test_user_overrides_default(self, cm: ConfigManager, user_json: Path):
        cm.load(user_json)
        assert cm.get("logging.level") == "DEBUG"    # user override
        assert cm.get("logging.dir")   == "logs"     # default 残存

    def test_cache_merge(self, cm: ConfigManager, user_json: Path):
        cm.load(user_json)
        assert cm.get("cache.max_size") == 512       # user override
        assert cm.get("cache.enabled")  is True      # default 残存

    def test_missing_user_file(self, cm: ConfigManager, tmp_path: Path):
        cm.load(tmp_path / "no_such.json")           # 警告のみ、エラーなし
        assert cm.get("logging.level") == "INFO"     # default が生きている

    def test_invalid_json(self, cm: ConfigManager, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{invalid json}", encoding="utf-8")
        with pytest.raises(ConfigLoadError):
            cm.load(bad)


# ──────────────────────────────────────────
# ConfigManager — get / set / require
# ──────────────────────────────────────────

class TestConfigManagerGetSet:
    def test_get_nested(self, cm: ConfigManager):
        assert cm.get("cache.enabled") is True

    def test_get_default_fallback(self, cm: ConfigManager):
        assert cm.get("nonexistent.key", "fallback") == "fallback"

    def test_get_returns_none_when_missing(self, cm: ConfigManager):
        assert cm.get("no.such.key") is None

    def test_set_creates_nested(self, cm: ConfigManager):
        cm.set("new.nested.key", 123)
        assert cm.get("new.nested.key") == 123

    def test_set_overrides_existing(self, cm: ConfigManager):
        cm.set("logging.level", "ERROR")
        assert cm.get("logging.level") == "ERROR"

    def test_require_existing(self, cm: ConfigManager):
        assert cm.require("fps.version") == "0.2.0-dev"

    def test_require_missing_raises(self, cm: ConfigManager):
        with pytest.raises(ConfigKeyError):
            cm.require("no.such.key")

    def test_all_returns_copy(self, cm: ConfigManager):
        snapshot = cm.all()
        snapshot["fps"]["version"] = "mutated"
        assert cm.get("fps.version") == "0.2.0-dev"  # 元は変わらない


# ──────────────────────────────────────────
# ConfigManager — save()
# ──────────────────────────────────────────

class TestConfigManagerSave:
    def test_save_and_reload(self, cm: ConfigManager, tmp_path: Path):
        cm.set("logging.level", "WARNING")
        save_path = tmp_path / "saved.json"
        cm.save(save_path)

        cm2 = ConfigManager()
        cm2.load(save_path)
        assert cm2.get("logging.level") == "WARNING"

    def test_save_no_path_raises(self, cm: ConfigManager):
        with pytest.raises(ConfigError):
            cm.save()


# ──────────────────────────────────────────
# ConfigManager — 環境変数オーバーライド
# ──────────────────────────────────────────

class TestEnvOverride:
    def test_env_overrides_value(self, default_json: Path, monkeypatch):
        monkeypatch.setenv("FPS_LOGGING__LEVEL", "CRITICAL")
        cm = ConfigManager(default_path=default_json)
        cm.load()
        assert cm.get("logging.level") == "CRITICAL"

    def test_env_type_coercion_bool(self, default_json: Path, monkeypatch):
        monkeypatch.setenv("FPS_FPS__DEBUG", "true")
        cm = ConfigManager(default_path=default_json)
        cm.load()
        assert cm.get("fps.debug") is True

    def test_env_type_coercion_int(self, default_json: Path, monkeypatch):
        monkeypatch.setenv("FPS_CACHE__MAX_SIZE", "1024")
        cm = ConfigManager(default_path=default_json)
        cm.load()
        assert cm.get("cache.max_size") == 1024


# ──────────────────────────────────────────
# ConfigManager — hot reload
# ──────────────────────────────────────────

class TestHotReload:
    def test_callback_on_load(self, cm: ConfigManager, user_json: Path):
        received = []
        cm.on_change(lambda cfg: received.append(cfg))
        cm.load(user_json)
        assert len(received) == 1
        assert received[0]["logging"]["level"] == "DEBUG"

    def test_watch_detects_change(self, default_json: Path, tmp_path: Path):
        user_path = tmp_path / "watch_test.json"
        user_path.write_text(json.dumps({"logging": {"level": "INFO"}}))

        cm = ConfigManager(default_path=default_json)
        cm.load(user_path)

        received = []
        cm.watch(callback=lambda cfg: received.append(cfg["logging"]["level"]), interval=1)

        # ファイルを書き換え
        time.sleep(0.5)
        user_path.write_text(json.dumps({"logging": {"level": "WARNING"}}))
        time.sleep(1.8)   # watcher が検知するまで待つ

        cm.unwatch()
        assert "WARNING" in received
