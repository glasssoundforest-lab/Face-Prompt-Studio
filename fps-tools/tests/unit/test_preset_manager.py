"""
fps-tools/tests/unit/test_preset_manager.py

PresetManager のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_preset_manager.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))

from preset.exceptions import (
    PresetError,
    PresetLoadError,
    PresetNotFoundError,
    PresetSaveError,
)
from preset.loader import load_preset_dir, load_preset_file
from preset.manager import PresetManager
from preset.merger import diff_presets, merge_presets
from preset.models import MergeResult, Preset, PresetFile, PresetSource, PresetTag


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

PRESET_DATA = {
    "version": "1.0",
    "presets": [
        {
            "id": "anime_portrait",
            "name": "アニメポートレート",
            "description": "アニメ風",
            "version": "1.0",
            "tags": [
                {"tag": "masterpiece", "category": "quality", "weight": 1.5},
                {"tag": "anime",       "category": "style",   "weight": 1.0},
                {"tag": "blue_eyes",   "category": "eyes",    "weight": 1.0},
            ],
            "negative_tags": [
                {"tag": "bad hands",   "category": "negative", "weight": 1.0},
            ],
        },
        {
            "id": "realistic_portrait",
            "name": "リアルポートレート",
            "description": "フォトリアル",
            "version": "1.0",
            "tags": [
                {"tag": "masterpiece", "category": "quality",  "weight": 1.5},
                {"tag": "realistic",   "category": "style",    "weight": 1.2},
            ],
            "negative_tags": [],
        },
    ],
}

USER_DATA = {
    "version": "1.0",
    "presets": [
        {
            "id": "anime_portrait",
            "name": "マイアニメポートレート",
            "description": "ユーザーカスタム",
            "version": "1.0",
            "tags": [
                {"tag": "masterpiece", "category": "quality", "weight": 2.0},
                {"tag": "anime",       "category": "style",   "weight": 1.5},
            ],
            "negative_tags": [],
        }
    ],
}


def make_preset(
    id_:   str = "test",
    name:  str = "Test",
    tags:  list[PresetTag] | None = None,
    negs:  list[PresetTag] | None = None,
    source: PresetSource = PresetSource.SYSTEM,
) -> Preset:
    return Preset(
        id            = id_,
        name          = name,
        tags          = tags or [],
        negative_tags = negs or [],
        source        = source,
    )


@pytest.fixture
def system_dir(tmp_path: Path) -> Path:
    d = tmp_path / "system"
    d.mkdir()
    (d / "presets.json").write_text(json.dumps(PRESET_DATA), encoding="utf-8")
    return d


@pytest.fixture
def user_dir(tmp_path: Path) -> Path:
    d = tmp_path / "user"
    d.mkdir()
    (d / "custom.json").write_text(json.dumps(USER_DATA), encoding="utf-8")
    return d


@pytest.fixture
def pm(system_dir: Path, user_dir: Path) -> PresetManager:
    manager = PresetManager(system_dir=system_dir, user_dir=user_dir)
    manager.load()
    return manager


@pytest.fixture
def system_only(system_dir: Path) -> PresetManager:
    manager = PresetManager(system_dir=system_dir)
    manager.load()
    return manager


# ══════════════════════════════════════════════════════════════════
# models
# ══════════════════════════════════════════════════════════════════

class TestModels:
    def test_preset_tag_count(self):
        p = make_preset(tags=[PresetTag("a"), PresetTag("b")])
        assert p.tag_count == 2

    def test_preset_negative_tag_count(self):
        p = make_preset(negs=[PresetTag("bad hands")])
        assert p.negative_tag_count == 1

    def test_preset_file_count(self):
        p1 = make_preset("p1")
        p2 = make_preset("p2")
        pf = PresetFile(version="1.0", source=PresetSource.SYSTEM, presets=[p1, p2])
        assert pf.preset_count == 2

    def test_merge_result_fields(self):
        p = make_preset()
        mr = MergeResult(preset=p, merged_from=["a", "b"], tag_count=3)
        assert mr.tag_count == 3
        assert mr.merged_from == ["a", "b"]


# ══════════════════════════════════════════════════════════════════
# loader
# ══════════════════════════════════════════════════════════════════

class TestLoader:
    def test_load_json(self, system_dir: Path):
        p = system_dir / "presets.json"
        pf = load_preset_file(p, PresetSource.SYSTEM)
        assert pf.version == "1.0"
        assert len(pf.presets) == 2

    def test_load_nonexistent_raises(self, tmp_path: Path):
        with pytest.raises(PresetLoadError):
            load_preset_file(tmp_path / "ghost.json")

    def test_load_invalid_json_raises(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("{invalid}", encoding="utf-8")
        with pytest.raises(PresetLoadError):
            load_preset_file(p)

    def test_load_missing_id_raises(self, tmp_path: Path):
        data = {"version": "1.0", "presets": [{"name": "no id"}]}
        p    = tmp_path / "r.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(PresetLoadError):
            load_preset_file(p)

    def test_load_dir(self, system_dir: Path):
        files = load_preset_dir(system_dir, PresetSource.SYSTEM)
        assert len(files) == 1
        assert len(files[0].presets) == 2

    def test_load_dir_nonexistent(self, tmp_path: Path):
        files = load_preset_dir(tmp_path / "ghost")
        assert files == []

    def test_source_assigned(self, system_dir: Path):
        p  = system_dir / "presets.json"
        pf = load_preset_file(p, PresetSource.USER)
        assert all(p.source == PresetSource.USER for p in pf.presets)

    def test_tags_parsed(self, system_dir: Path):
        p    = system_dir / "presets.json"
        pf   = load_preset_file(p)
        tags = pf.presets[0].tags
        assert tags[0].tag      == "masterpiece"
        assert tags[0].weight   == 1.5
        assert tags[0].category == "quality"

    def test_negative_tags_parsed(self, system_dir: Path):
        p    = system_dir / "presets.json"
        pf   = load_preset_file(p)
        negs = pf.presets[0].negative_tags
        assert len(negs) == 1
        assert negs[0].tag == "bad hands"


# ══════════════════════════════════════════════════════════════════
# merger
# ══════════════════════════════════════════════════════════════════

class TestMerger:
    def test_merge_two_presets(self):
        p1 = make_preset("p1", tags=[PresetTag("masterpiece", "quality", 1.0)])
        p2 = make_preset("p2", tags=[PresetTag("anime",       "style",   1.0)])
        result = merge_presets([p1, p2])
        tag_names = [t.tag for t in result.preset.tags]
        assert "masterpiece" in tag_names
        assert "anime"       in tag_names

    def test_merge_later_wins(self):
        p1 = make_preset("p1", tags=[PresetTag("masterpiece", "quality", 1.0)])
        p2 = make_preset("p2", tags=[PresetTag("masterpiece", "quality", 2.0)])
        result = merge_presets([p1, p2])
        t = next(t for t in result.preset.tags if t.tag == "masterpiece")
        assert t.weight == 2.0

    def test_merge_records_conflicts(self):
        p1 = make_preset("p1", tags=[PresetTag("masterpiece", "quality", 1.0)])
        p2 = make_preset("p2", tags=[PresetTag("masterpiece", "quality", 2.0)])
        result = merge_presets([p1, p2])
        assert len(result.conflicts) >= 1

    def test_merge_empty(self):
        result = merge_presets([])
        assert result.tag_count == 0
        assert result.merged_from == []

    def test_merge_negative_tags(self):
        p1 = make_preset("p1", negs=[PresetTag("bad hands")])
        p2 = make_preset("p2", negs=[PresetTag("low quality")])
        result = merge_presets([p1, p2])
        neg_names = [t.tag for t in result.preset.negative_tags]
        assert "bad hands"   in neg_names
        assert "low quality" in neg_names

    def test_merge_from_ids(self):
        p1 = make_preset("p1")
        p2 = make_preset("p2")
        result = merge_presets([p1, p2], result_id="combined")
        assert result.merged_from == ["p1", "p2"]
        assert result.preset.id   == "combined"

    def test_diff_presets_added(self):
        base  = make_preset(tags=[PresetTag("masterpiece")])
        other = make_preset(tags=[PresetTag("masterpiece"), PresetTag("anime")])
        d = diff_presets(base, other)
        assert "anime" in d["added"]

    def test_diff_presets_removed(self):
        base  = make_preset(tags=[PresetTag("masterpiece"), PresetTag("anime")])
        other = make_preset(tags=[PresetTag("masterpiece")])
        d = diff_presets(base, other)
        assert "anime" in d["removed"]

    def test_diff_presets_changed(self):
        base  = make_preset(tags=[PresetTag("masterpiece", weight=1.0)])
        other = make_preset(tags=[PresetTag("masterpiece", weight=2.0)])
        d = diff_presets(base, other)
        assert "masterpiece" in d["changed"]


# ══════════════════════════════════════════════════════════════════
# PresetManager — load
# ══════════════════════════════════════════════════════════════════

class TestPresetManagerLoad:
    def test_load_success(self, pm: PresetManager):
        stats = pm.statistics()
        assert stats["total_presets"] > 0

    def test_load_no_dirs(self):
        manager = PresetManager()
        manager.load()
        assert manager.statistics()["total_presets"] == 0

    def test_user_overrides_system(self, pm: PresetManager):
        p = pm.get("anime_portrait")
        assert p.name   == "マイアニメポートレート"   # user が上書き
        assert p.source == PresetSource.USER

    def test_system_preset_survives(self, pm: PresetManager):
        p = pm.get("realistic_portrait")
        assert p.source == PresetSource.SYSTEM

    def test_reload_safe(self, pm: PresetManager):
        pm.reload()
        assert pm.statistics()["total_presets"] > 0

    def test_system_only(self, system_only: PresetManager):
        stats = system_only.statistics()
        assert stats["by_source"]["system"] == 2
        assert stats["by_source"]["user"]   == 0


# ══════════════════════════════════════════════════════════════════
# PresetManager — get / list / search
# ══════════════════════════════════════════════════════════════════

class TestPresetManagerQuery:
    def test_get_existing(self, pm: PresetManager):
        p = pm.get("realistic_portrait")
        assert p.id == "realistic_portrait"

    def test_get_missing_raises(self, pm: PresetManager):
        with pytest.raises(PresetNotFoundError):
            pm.get("nonexistent_id")

    def test_get_or_none_missing(self, pm: PresetManager):
        assert pm.get_or_none("nonexistent") is None

    def test_exists_true(self, pm: PresetManager):
        assert pm.exists("realistic_portrait") is True

    def test_exists_false(self, pm: PresetManager):
        assert pm.exists("ghost") is False

    def test_list_sorted_by_name(self, pm: PresetManager):
        presets = pm.list_presets()
        names   = [p.name for p in presets]
        assert names == sorted(names)

    def test_list_ids(self, pm: PresetManager):
        ids = pm.list_ids()
        assert "realistic_portrait" in ids

    def test_search_by_name(self, pm: PresetManager):
        results = pm.search("リアル")
        assert any(p.id == "realistic_portrait" for p in results)

    def test_search_by_id(self, pm: PresetManager):
        results = pm.search("realistic")
        assert len(results) >= 1

    def test_search_no_results(self, pm: PresetManager):
        results = pm.search("xxxxxxnotfound")
        assert results == []

    def test_search_case_insensitive(self, pm: PresetManager):
        results = pm.search("REALISTIC")
        assert len(results) >= 1


# ══════════════════════════════════════════════════════════════════
# PresetManager — save / delete
# ══════════════════════════════════════════════════════════════════

class TestPresetManagerSaveDelete:
    def test_save_creates_file(self, pm: PresetManager, tmp_path: Path):
        pm._user_dir = tmp_path / "user"
        p = make_preset("my_preset", "マイプリセット",
                        tags=[PresetTag("masterpiece", "quality", 1.5)],
                        source=PresetSource.USER)
        path = pm.save(p)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["presets"][0]["id"] == "my_preset"

    def test_save_adds_to_index(self, pm: PresetManager, tmp_path: Path):
        pm._user_dir = tmp_path / "user"
        p = make_preset("new_preset", "新規", source=PresetSource.USER)
        pm.save(p)
        assert pm.exists("new_preset")

    def test_save_no_user_dir_raises(self):
        manager = PresetManager()
        manager.load()
        p = make_preset("x")
        with pytest.raises(PresetSaveError):
            manager.save(p)

    def test_delete_user_preset(self, pm: PresetManager, tmp_path: Path):
        pm._user_dir = tmp_path / "user"
        p = make_preset("to_delete", "削除対象", source=PresetSource.USER)
        pm.save(p)
        assert pm.exists("to_delete")
        result = pm.delete("to_delete")
        assert result is True
        assert not pm.exists("to_delete")

    def test_delete_system_preset_raises(self, pm: PresetManager):
        with pytest.raises(PresetError):
            pm.delete("realistic_portrait")

    def test_delete_nonexistent_returns_false(self, pm: PresetManager):
        result = pm.delete("nonexistent")
        assert result is False


# ══════════════════════════════════════════════════════════════════
# PresetManager — merge / apply
# ══════════════════════════════════════════════════════════════════

class TestPresetManagerMergeApply:
    def test_merge_two(self, pm: PresetManager):
        result = pm.merge(["anime_portrait", "realistic_portrait"], "combined")
        tag_names = [t.tag for t in result.preset.tags]
        assert "anime"     in tag_names
        assert "realistic" in tag_names

    def test_merge_missing_raises(self, pm: PresetManager):
        with pytest.raises(PresetNotFoundError):
            pm.merge(["anime_portrait", "ghost"])

    def test_apply_returns_tag_dicts(self, pm: PresetManager):
        applied = pm.apply("realistic_portrait")
        assert "tags"          in applied
        assert "negative_tags" in applied
        assert all("tag" in t and "weight" in t for t in applied["tags"])

    def test_apply_missing_raises(self, pm: PresetManager):
        with pytest.raises(PresetNotFoundError):
            pm.apply("ghost")


# ══════════════════════════════════════════════════════════════════
# PresetManager — validate / statistics
# ══════════════════════════════════════════════════════════════════

class TestPresetManagerMeta:
    def test_validate_clean(self, pm: PresetManager):
        errors = pm.validate()
        assert errors == []

    def test_validate_detects_invalid_weight(self, pm: PresetManager):
        pm._index["bad"] = Preset(
            id="bad", name="Bad",
            tags=[PresetTag("x", weight=99.0)],
        )
        errors = pm.validate()
        assert any("weight" in e for e in errors)

    def test_statistics_keys(self, pm: PresetManager):
        stats = pm.statistics()
        for key in ("total_presets", "by_source", "total_tags"):
            assert key in stats

    def test_statistics_total_tags(self, pm: PresetManager):
        stats = pm.statistics()
        assert stats["total_tags"] > 0

    def test_repr(self, pm: PresetManager):
        assert "PresetManager" in repr(pm)
