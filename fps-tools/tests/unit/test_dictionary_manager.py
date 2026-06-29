"""
fps-tools/tests/unit/test_dictionary_manager.py

DictionaryManager のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_dictionary_manager.py -v
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))

from dictionary.exceptions import DictLoadError, DictValidationError
from dictionary.manager import DictionaryManager
from dictionary.merger import diff, merge
from dictionary.models import DictEntry, DictFile, DictSource, LookupResult
from dictionary.validator import validate_dict_file


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

SYSTEM_DATA = {
    "version": "1.0",
    "category": "quality",
    "description": "test",
    "entries": [
        {
            "key": "masterpiece",
            "resolved": "Quality.High",
            "aliases": ["best quality"],
            "weight": 1.2,
        },
        {
            "key": "low_quality",
            "resolved": "Quality.Low",
            "aliases": ["bad quality"],
            "weight": 0.8,
        },
    ],
}

USER_DATA = {
    "version": "1.0",
    "category": "quality",
    "description": "user override",
    "entries": [
        {
            "key": "masterpiece",
            "resolved": "Quality.High",
            "aliases": ["best quality", "my_best"],
            "weight": 1.5,
        }
    ],
}

EYES_DATA = {
    "version": "1.0",
    "category": "eyes",
    "entries": [
        {"key": "blue_eyes", "resolved": "Eyes.Blue", "aliases": ["blue eye"]},
        {"key": "red_eyes",  "resolved": "Eyes.Red",  "aliases": ["red eye"]},
    ],
}


@pytest.fixture
def system_dir(tmp_path: Path) -> Path:
    d = tmp_path / "system"
    d.mkdir()
    (d / "quality.json").write_text(json.dumps(SYSTEM_DATA), encoding="utf-8")
    (d / "eyes.json").write_text(json.dumps(EYES_DATA), encoding="utf-8")
    return d


@pytest.fixture
def user_dir(tmp_path: Path) -> Path:
    d = tmp_path / "user"
    d.mkdir()
    (d / "quality_override.json").write_text(json.dumps(USER_DATA), encoding="utf-8")
    return d


@pytest.fixture
def dm(system_dir: Path, user_dir: Path) -> DictionaryManager:
    manager = DictionaryManager(system_dir=system_dir, user_dir=user_dir)
    manager.load()
    return manager


@pytest.fixture
def system_only(system_dir: Path) -> DictionaryManager:
    manager = DictionaryManager(system_dir=system_dir)
    manager.load()
    return manager


# ══════════════════════════════════════════════════════════════════
# models
# ══════════════════════════════════════════════════════════════════

class TestDictEntry:
    def test_key_normalized(self):
        e = DictEntry(key="Blue Eyes", resolved="Eyes.Blue", category="eyes")
        assert e.key == "blue_eyes"

    def test_all_keys_includes_aliases(self):
        e = DictEntry(
            key="blue_eyes",
            resolved="Eyes.Blue",
            category="eyes",
            aliases=["blue eye", "eyes blue"],
        )
        assert "blue_eyes" in e.all_keys
        assert "blue_eye" in e.all_keys
        assert "eyes_blue" in e.all_keys

    def test_default_weight(self):
        e = DictEntry(key="test", resolved="Test.Value", category="test")
        assert e.weight == 1.0

    def test_default_source(self):
        e = DictEntry(key="test", resolved="Test.Value", category="test")
        assert e.source == DictSource.SYSTEM


class TestLookupResult:
    def _entry(self) -> DictEntry:
        return DictEntry(key="masterpiece", resolved="Quality.High", category="quality", weight=1.2)

    def test_found_resolved(self):
        r = LookupResult(found=True, key="masterpiece", entry=self._entry())
        assert r.resolved == "Quality.High"

    def test_not_found(self):
        r = LookupResult(found=False, key="unknown")
        assert r.resolved is None
        assert r.category is None
        assert r.weight == 1.0


# ══════════════════════════════════════════════════════════════════
# validator
# ══════════════════════════════════════════════════════════════════

class TestValidator:
    def _make_file(self, entries: list[dict]) -> DictFile:
        from dictionary.loader import _parse
        raw = {"version": "1.0", "category": "test", "entries": entries}
        return _parse(raw, Path("test.json"), DictSource.SYSTEM)

    def test_valid_passes(self):
        df = self._make_file([
            {"key": "masterpiece", "resolved": "Quality.High"}
        ])
        validate_dict_file(df)   # 例外なし

    def test_invalid_key_raises(self):
        df = self._make_file([
            {"key": "INVALID KEY!", "resolved": "Quality.High"}
        ])
        with pytest.raises(DictValidationError) as exc:
            validate_dict_file(df)
        assert any("key" in e for e in exc.value.errors)

    def test_invalid_resolved_raises(self):
        df = self._make_file([
            {"key": "test", "resolved": "invalid_format"}
        ])
        with pytest.raises(DictValidationError) as exc:
            validate_dict_file(df)
        assert any("resolved" in e for e in exc.value.errors)

    def test_duplicate_key_raises(self):
        df = self._make_file([
            {"key": "masterpiece", "resolved": "Quality.High"},
            {"key": "masterpiece", "resolved": "Quality.Medium"},
        ])
        with pytest.raises(DictValidationError) as exc:
            validate_dict_file(df)
        assert any("重複" in e for e in exc.value.errors)

    def test_weight_out_of_range_raises(self):
        df = self._make_file([
            {"key": "test", "resolved": "Quality.High", "weight": 5.0}
        ])
        with pytest.raises(DictValidationError):
            validate_dict_file(df)

    def test_empty_entries_raises(self):
        df = self._make_file([])
        with pytest.raises(DictValidationError):
            validate_dict_file(df)


# ══════════════════════════════════════════════════════════════════
# loader
# ══════════════════════════════════════════════════════════════════

class TestLoader:
    def test_load_json(self, tmp_path: Path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps(SYSTEM_DATA), encoding="utf-8")
        from dictionary.loader import load_dict_file
        df = load_dict_file(p, DictSource.SYSTEM)
        assert df.category == "quality"
        assert len(df.entries) == 2

    def test_load_nonexistent_raises(self, tmp_path: Path):
        from dictionary.loader import load_dict_file
        with pytest.raises(DictLoadError):
            load_dict_file(tmp_path / "ghost.json")

    def test_load_invalid_json_raises(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("{invalid}", encoding="utf-8")
        from dictionary.loader import load_dict_file
        with pytest.raises(DictLoadError):
            load_dict_file(p)

    def test_load_dir_loads_all(self, system_dir: Path):
        from dictionary.loader import load_dict_dir
        files = load_dict_dir(system_dir, DictSource.SYSTEM)
        assert len(files) == 2

    def test_load_dir_empty(self, tmp_path: Path):
        from dictionary.loader import load_dict_dir
        files = load_dict_dir(tmp_path / "nonexistent")
        assert files == []

    def test_source_assigned(self, tmp_path: Path):
        p = tmp_path / "q.json"
        p.write_text(json.dumps(SYSTEM_DATA), encoding="utf-8")
        from dictionary.loader import load_dict_file
        df = load_dict_file(p, DictSource.USER)
        assert all(e.source == DictSource.USER for e in df.entries)


# ══════════════════════════════════════════════════════════════════
# merger
# ══════════════════════════════════════════════════════════════════

class TestMerger:
    def _make_files(self, data: dict, source: DictSource) -> list[DictFile]:
        from dictionary.loader import _parse
        return [_parse(data, Path("f.json"), source)]

    def test_user_overrides_system(self):
        sys_files = self._make_files(SYSTEM_DATA, DictSource.SYSTEM)
        usr_files = self._make_files(USER_DATA, DictSource.USER)
        index = merge(sys_files, usr_files)
        assert index["masterpiece"].weight == 1.5      # user 優先
        assert index["low_quality"].resolved == "Quality.Low"  # system 残存

    def test_alias_registered(self):
        sys_files = self._make_files(SYSTEM_DATA, DictSource.SYSTEM)
        index = merge(sys_files, [])
        assert "best_quality" in index   # alias がインデックス登録される

    def test_diff_detects_change(self):
        sys_files = self._make_files(SYSTEM_DATA, DictSource.SYSTEM)
        before = merge(sys_files, [])
        usr_files = self._make_files(USER_DATA, DictSource.USER)
        after = merge(sys_files, usr_files)
        changes = diff(before, after)
        assert "masterpiece" in changes["changed"]

    def test_no_diff_when_same(self):
        sys_files = self._make_files(SYSTEM_DATA, DictSource.SYSTEM)
        before = merge(sys_files, [])
        after = merge(sys_files, [])
        changes = diff(before, after)
        assert not any(changes.values())


# ══════════════════════════════════════════════════════════════════
# DictionaryManager — load
# ══════════════════════════════════════════════════════════════════

class TestDictionaryManagerLoad:
    def test_load_success(self, dm: DictionaryManager):
        stats = dm.statistics()
        assert stats["total_keys"] > 0

    def test_load_no_dirs(self):
        manager = DictionaryManager()
        manager.load()
        assert manager.statistics()["total_keys"] == 0

    def test_load_system_only(self, system_only: DictionaryManager):
        stats = system_only.statistics()
        assert stats["by_source"]["system"] > 0
        assert stats["by_source"]["user"] == 0

    def test_reload_is_safe(self, dm: DictionaryManager):
        dm.reload()   # 2回呼んでも問題ない
        assert dm.statistics()["total_keys"] > 0

    def test_load_file_adds_entries(self, dm: DictionaryManager, tmp_path: Path):
        extra = {
            "version": "1.0",
            "category": "expression",
            "entries": [{"key": "smile", "resolved": "Expression.Smile"}],
        }
        p = tmp_path / "extra.json"
        p.write_text(json.dumps(extra), encoding="utf-8")
        before = dm.statistics()["total_keys"]
        dm.load_file(p, DictSource.USER)
        assert dm.statistics()["total_keys"] > before


# ══════════════════════════════════════════════════════════════════
# DictionaryManager — lookup
# ══════════════════════════════════════════════════════════════════

class TestDictionaryManagerLookup:
    def test_lookup_hit(self, dm: DictionaryManager):
        r = dm.lookup("masterpiece")
        assert r.found is True
        assert r.resolved == "Quality.High"

    def test_lookup_user_weight(self, dm: DictionaryManager):
        r = dm.lookup("masterpiece")
        assert r.weight == 1.5   # user が 1.2 → 1.5 に上書き

    def test_lookup_miss(self, dm: DictionaryManager):
        r = dm.lookup("unknown_tag_xyz")
        assert r.found is False
        assert r.resolved is None

    def test_lookup_alias(self, dm: DictionaryManager):
        r = dm.lookup("best quality")   # スペースでも OK
        assert r.found is True
        assert r.resolved == "Quality.High"

    def test_lookup_case_insensitive(self, dm: DictionaryManager):
        r = dm.lookup("MASTERPIECE")
        assert r.found is True

    def test_lookup_hyphen_normalized(self, dm: DictionaryManager):
        # "blue-eyes" → "blue_eyes"
        r = dm.lookup("blue-eyes")
        assert r.found is True
        assert r.resolved == "Eyes.Blue"

    def test_lookup_alias_method(self, dm: DictionaryManager):
        r = dm.lookup_alias("best quality")
        assert r.found is True

    def test_lookup_many(self, dm: DictionaryManager):
        results = dm.lookup_many(["masterpiece", "blue_eyes", "unknown"])
        assert results[0].found is True
        assert results[1].found is True
        assert results[2].found is False

    def test_lookup_user_alias(self, dm: DictionaryManager):
        r = dm.lookup("my_best")    # ユーザー辞書のエイリアス
        assert r.found is True


# ══════════════════════════════════════════════════════════════════
# DictionaryManager — metadata
# ══════════════════════════════════════════════════════════════════

class TestDictionaryManagerMeta:
    def test_categories(self, dm: DictionaryManager):
        cats = dm.categories()
        assert "quality" in cats
        assert "eyes" in cats
        assert cats == sorted(cats)   # ソート済み

    def test_statistics_keys(self, dm: DictionaryManager):
        stats = dm.statistics()
        for key in ("total_keys", "by_source", "by_category", "system_files", "user_files"):
            assert key in stats

    def test_validate_returns_empty_on_clean(self, dm: DictionaryManager):
        errors = dm.validate()
        assert errors == []


# ══════════════════════════════════════════════════════════════════
# DictionaryManager — export
# ══════════════════════════════════════════════════════════════════

class TestDictionaryManagerExport:
    def test_export_json_string(self, dm: DictionaryManager):
        import json as _json
        text = dm.export_json()
        parsed = _json.loads(text)
        assert "entries" in parsed
        assert len(parsed["entries"]) > 0

    def test_export_json_file(self, dm: DictionaryManager, tmp_path: Path):
        p = tmp_path / "export.json"
        dm.export_json(p)
        assert p.exists()
        data = json.loads(p.read_text())
        assert "entries" in data

    def test_export_sorted_by_key(self, dm: DictionaryManager):
        text = dm.export_json()
        entries = json.loads(text)["entries"]
        keys = [e["key"] for e in entries]
        assert keys == sorted(keys)

    def test_repr(self, dm: DictionaryManager):
        r = repr(dm)
        assert "DictionaryManager" in r


# ══════════════════════════════════════════════════════════════════
# DictionaryManager — hot reload
# ══════════════════════════════════════════════════════════════════

class TestDictionaryManagerWatch:
    def test_watch_and_unwatch(self, dm: DictionaryManager):
        dm.watch(interval=1)
        assert dm._watcher is not None
        assert dm._watcher.is_running()
        dm.unwatch()
        assert not dm._watcher.is_running()

    def test_watch_detects_file_change(
        self, system_dir: Path, user_dir: Path, tmp_path: Path
    ):
        manager = DictionaryManager(system_dir=system_dir, user_dir=user_dir)
        manager.load()

        reloaded = []
        manager.watch(callback=lambda: reloaded.append(True), interval=1)

        # 新しいユーザー辞書ファイルを追加
        time.sleep(0.3)
        new_file = user_dir / "extra.json"
        new_file.write_text(
            json.dumps({
                "version": "1.0",
                "category": "extra",
                "entries": [{"key": "smile", "resolved": "Expression.Smile"}],
            }),
            encoding="utf-8",
        )
        time.sleep(1.8)

        manager.unwatch()
        assert len(reloaded) >= 1
        assert manager.lookup("smile").found is True
