"""
fps-tools/tests/unit/test_config.py — ConfigManager ユニットテスト
"""

import json
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# fps-core をパスに追加
sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))

from config.manager import ConfigManager, ConfigError, _deep_merge


class TestDeepMerge(unittest.TestCase):
    """_deep_merge ユーティリティのテスト"""

    def test_simple_override(self):
        base     = {"a": 1, "b": 2}
        override = {"b": 99, "c": 3}
        result   = _deep_merge(base, override)
        self.assertEqual(result, {"a": 1, "b": 99, "c": 3})

    def test_nested_merge(self):
        base     = {"pipeline": {"max_tokens": 128, "language": "en"}}
        override = {"pipeline": {"max_tokens": 256}}
        result   = _deep_merge(base, override)
        self.assertEqual(result["pipeline"]["max_tokens"], 256)
        self.assertEqual(result["pipeline"]["language"], "en")

    def test_does_not_mutate_base(self):
        base     = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        _deep_merge(base, override)
        self.assertNotIn("c", base["a"])


class TestConfigManagerLoad(unittest.TestCase):
    """ファイル読み込みのテスト"""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name: str, data: dict) -> Path:
        p = self.tmp_path / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_load_default_json(self):
        p = self._write("default.json", {"a": 1, "b": {"c": 2}})
        cfg = ConfigManager(default_path=p)
        self.assertEqual(cfg.get("a"), 1)
        self.assertEqual(cfg.get("b.c"), 2)

    def test_load_user_overrides_default(self):
        dp = self._write("default.json", {"x": 10, "y": 20})
        up = self._write("user.json",    {"y": 99})
        cfg = ConfigManager(default_path=dp)
        cfg.load_user(up)
        self.assertEqual(cfg.get("x"), 10)   # default
        self.assertEqual(cfg.get("y"), 99)   # user override

    def test_missing_default_raises(self):
        with self.assertRaises(ConfigError):
            ConfigManager(default_path=self.tmp_path / "nonexistent.json")

    def test_missing_user_is_silent(self):
        dp = self._write("default.json", {"a": 1})
        cfg = ConfigManager(default_path=dp)
        cfg.load_user(self.tmp_path / "nonexistent.json")   # 例外を出さない
        self.assertEqual(cfg.get("a"), 1)

    def test_invalid_json_raises(self):
        p = self.tmp_path / "bad.json"
        p.write_text("{invalid json}", encoding="utf-8")
        with self.assertRaises(ConfigError):
            ConfigManager(default_path=p)

    def test_unsupported_extension_raises(self):
        p = self.tmp_path / "config.toml"
        p.write_text("[section]\nkey = 'value'", encoding="utf-8")
        with self.assertRaises(ConfigError):
            ConfigManager(default_path=p)


class TestConfigManagerGetSet(unittest.TestCase):
    """get / set のテスト"""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        p = Path(self.tmp.name) / "cfg.json"
        p.write_text(json.dumps({
            "pipeline": {"max_tokens": 128, "language": "en"},
            "flag": True,
        }), encoding="utf-8")
        self.cfg = ConfigManager(default_path=p)

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_top_level(self):
        self.assertTrue(self.cfg.get("flag"))

    def test_get_nested(self):
        self.assertEqual(self.cfg.get("pipeline.max_tokens"), 128)

    def test_get_missing_returns_default(self):
        self.assertIsNone(self.cfg.get("no.such.key"))
        self.assertEqual(self.cfg.get("no.such.key", default=42), 42)

    def test_set_top_level(self):
        self.cfg.set("flag", False)
        self.assertFalse(self.cfg.get("flag"))

    def test_set_nested(self):
        self.cfg.set("pipeline.max_tokens", 512)
        self.assertEqual(self.cfg.get("pipeline.max_tokens"), 512)

    def test_set_new_key(self):
        self.cfg.set("new.deep.key", "hello")
        self.assertEqual(self.cfg.get("new.deep.key"), "hello")


class TestConfigManagerSave(unittest.TestCase):
    """save_user のテスト"""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_reload(self):
        dp = self.tmp_path / "default.json"
        dp.write_text(json.dumps({"a": 1}), encoding="utf-8")
        up = self.tmp_path / "user.json"

        cfg = ConfigManager(default_path=dp)
        cfg.load_user(up)
        cfg.set("a", 99)

        # user_data に反映させてから保存
        cfg._user_data = {"a": 99}
        cfg.save_user(up)

        # 新しいインスタンスで読み直す
        cfg2 = ConfigManager(default_path=dp)
        cfg2.load_user(up)
        self.assertEqual(cfg2.get("a"), 99)


class TestConfigManagerHotReload(unittest.TestCase):
    """Hot reload のテスト"""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_hot_reload_detects_change(self):
        dp = self.tmp_path / "default.json"
        up = self.tmp_path / "user.json"
        dp.write_text(json.dumps({"v": 1}), encoding="utf-8")
        up.write_text(json.dumps({"v": 1}), encoding="utf-8")

        cfg = ConfigManager(default_path=dp, hot_reload_interval=0.2)
        cfg.load_user(up)

        reloaded = []
        cfg.on_reload(lambda: reloaded.append(True))
        cfg.start_hot_reload()

        # ファイルを書き換え
        time.sleep(0.3)
        up.write_text(json.dumps({"v": 999}), encoding="utf-8")
        time.sleep(0.5)

        cfg.stop_hot_reload()
        self.assertTrue(len(reloaded) > 0)
        self.assertEqual(cfg.get("v"), 999)


if __name__ == "__main__":
    unittest.main(verbosity=2)
