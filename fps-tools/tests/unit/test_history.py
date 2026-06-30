"""
fps-tools/tests/unit/test_history.py

HistoryManager のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_history.py -v
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from history.diff_viewer import diff_entries, diff_prompts, format_diff_report
from history.history_manager import HistoryManager
from history.models import DiffEntry, HistoryEntry


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def hm(tmp_path: Path) -> HistoryManager:
    manager = HistoryManager(history_file=tmp_path / "history.jsonl", max_entries=100)
    manager.load()
    return manager


def make_entry(
    id_: str = "e1",
    input_prompt: str = "masterpiece",
    output_prompt: str = "Quality.High",
    score: float = 80.0,
) -> HistoryEntry:
    return HistoryEntry(
        id=id_,
        input_prompt=input_prompt,
        output_prompt=output_prompt,
        overall_score=score,
    )


# ══════════════════════════════════════════════════════════════════
# models
# ══════════════════════════════════════════════════════════════════

class TestModels:
    def test_to_dict_from_dict_roundtrip(self):
        e = make_entry()
        d = e.to_dict()
        e2 = HistoryEntry.from_dict(d)
        assert e2.id == e.id
        assert e2.input_prompt == e.input_prompt
        assert e2.overall_score == e.overall_score

    def test_created_at_str_format(self):
        from datetime import datetime
        e = make_entry()
        e.created_at = datetime(2026, 6, 30, 12, 0, 0)
        assert e.created_at_str == "2026-06-30 12:00:00"

    def test_diff_entry_has_changes_true(self):
        d = DiffEntry(added_tags=["a"], removed_tags=[])
        assert d.has_changes is True

    def test_diff_entry_has_changes_false(self):
        d = DiffEntry()
        assert d.has_changes is False


# ══════════════════════════════════════════════════════════════════
# diff_viewer
# ══════════════════════════════════════════════════════════════════

class TestDiffViewer:
    def test_diff_prompts_added(self):
        diff = diff_prompts("masterpiece", "masterpiece, blue_eyes")
        assert "blue_eyes" in diff.added_tags

    def test_diff_prompts_removed(self):
        diff = diff_prompts("masterpiece, blue_eyes", "masterpiece")
        assert "blue_eyes" in diff.removed_tags

    def test_diff_prompts_unchanged(self):
        diff = diff_prompts("masterpiece, blue_eyes", "masterpiece, blue_eyes")
        assert "masterpiece" in diff.unchanged_tags
        assert diff.has_changes is False

    def test_diff_prompts_weighted_tags(self):
        diff = diff_prompts("(masterpiece:1.5)", "(masterpiece:1.5)")
        assert "masterpiece" in diff.unchanged_tags

    def test_diff_entries_score_delta(self):
        e1 = make_entry(output_prompt="masterpiece", score=70.0)
        e2 = make_entry(output_prompt="masterpiece", score=85.0)
        diff = diff_entries(e1, e2)
        assert diff.score_delta == 15.0

    def test_format_diff_report_contains_sections(self):
        diff = diff_prompts("masterpiece", "masterpiece, blue_eyes")
        report = format_diff_report(diff, "Before", "After")
        assert "Before" in report
        assert "After" in report
        assert "Added" in report

    def test_format_diff_report_no_changes(self):
        diff = diff_prompts("a", "a")
        report = format_diff_report(diff)
        assert "no tag changes" in report

    def test_format_diff_report_score_change(self):
        diff = DiffEntry(score_delta=10.0)
        report = format_diff_report(diff)
        assert "+10.0" in report


# ══════════════════════════════════════════════════════════════════
# HistoryManager — record / load
# ══════════════════════════════════════════════════════════════════

class TestHistoryManagerRecord:
    def test_record_returns_entry(self, hm: HistoryManager):
        entry = hm.record(input_prompt="masterpiece", output_prompt="Quality.High")
        assert entry.id != ""
        assert entry.input_prompt == "masterpiece"

    def test_record_persists_to_file(self, tmp_path: Path):
        path = tmp_path / "h.jsonl"
        hm = HistoryManager(history_file=path)
        hm.load()
        hm.record(input_prompt="masterpiece", output_prompt="Quality.High")
        assert path.exists()
        assert path.read_text().strip() != ""

    def test_load_restores_entries(self, tmp_path: Path):
        path = tmp_path / "h.jsonl"
        hm1 = HistoryManager(history_file=path)
        hm1.load()
        hm1.record(input_prompt="masterpiece", output_prompt="Quality.High")

        hm2 = HistoryManager(history_file=path)
        hm2.load()
        assert len(hm2.list_entries()) == 1

    def test_load_nonexistent_file_empty(self, tmp_path: Path):
        hm = HistoryManager(history_file=tmp_path / "ghost.jsonl")
        hm.load()
        assert hm.list_entries() == []

    def test_unique_ids_for_rapid_records(self, hm: HistoryManager):
        e1 = hm.record(input_prompt="a", output_prompt="A")
        e2 = hm.record(input_prompt="b", output_prompt="B")
        assert e1.id != e2.id


# ══════════════════════════════════════════════════════════════════
# HistoryManager — query
# ══════════════════════════════════════════════════════════════════

class TestHistoryManagerQuery:
    def test_list_entries_newest_first(self, hm: HistoryManager):
        hm.record(input_prompt="first", output_prompt="F")
        time.sleep(0.01)
        hm.record(input_prompt="second", output_prompt="S")
        entries = hm.list_entries()
        assert entries[0].input_prompt == "second"

    def test_list_entries_with_limit(self, hm: HistoryManager):
        for i in range(5):
            hm.record(input_prompt=f"p{i}", output_prompt=f"P{i}")
        entries = hm.list_entries(limit=2)
        assert len(entries) == 2

    def test_get_existing(self, hm: HistoryManager):
        entry = hm.record(input_prompt="masterpiece", output_prompt="Quality.High")
        fetched = hm.get(entry.id)
        assert fetched is not None
        assert fetched.id == entry.id

    def test_get_missing_returns_none(self, hm: HistoryManager):
        assert hm.get("nonexistent") is None

    def test_search_by_input_prompt(self, hm: HistoryManager):
        hm.record(input_prompt="masterpiece, blue_eyes", output_prompt="Quality.High")
        hm.record(input_prompt="unrelated", output_prompt="Other")
        results = hm.search("blue_eyes")
        assert len(results) == 1

    def test_search_by_label(self, hm: HistoryManager):
        entry = hm.record(input_prompt="a", output_prompt="A", label="my favorite combo")
        results = hm.search("favorite")
        assert len(results) == 1

    def test_search_empty_query_returns_all(self, hm: HistoryManager):
        hm.record(input_prompt="a", output_prompt="A")
        hm.record(input_prompt="b", output_prompt="B")
        results = hm.search("")
        assert len(results) == 2

    def test_favorites_filter(self, hm: HistoryManager):
        e1 = hm.record(input_prompt="a", output_prompt="A")
        hm.record(input_prompt="b", output_prompt="B")
        hm.toggle_favorite(e1.id)
        favs = hm.favorites()
        assert len(favs) == 1
        assert favs[0].id == e1.id


# ══════════════════════════════════════════════════════════════════
# HistoryManager — mutate
# ══════════════════════════════════════════════════════════════════

class TestHistoryManagerMutate:
    def test_delete_existing(self, hm: HistoryManager):
        entry = hm.record(input_prompt="a", output_prompt="A")
        assert hm.delete(entry.id) is True
        assert hm.get(entry.id) is None

    def test_delete_nonexistent_returns_false(self, hm: HistoryManager):
        assert hm.delete("ghost") is False

    def test_toggle_favorite(self, hm: HistoryManager):
        entry = hm.record(input_prompt="a", output_prompt="A")
        result1 = hm.toggle_favorite(entry.id)
        assert result1 is True
        result2 = hm.toggle_favorite(entry.id)
        assert result2 is False

    def test_toggle_favorite_missing_raises(self, hm: HistoryManager):
        with pytest.raises(KeyError):
            hm.toggle_favorite("ghost")

    def test_set_label(self, hm: HistoryManager):
        entry = hm.record(input_prompt="a", output_prompt="A")
        assert hm.set_label(entry.id, "my label") is True
        assert hm.get(entry.id).label == "my label"

    def test_set_label_missing_returns_false(self, hm: HistoryManager):
        assert hm.set_label("ghost", "x") is False

    def test_clear_keeps_favorites(self, hm: HistoryManager):
        e1 = hm.record(input_prompt="a", output_prompt="A")
        hm.record(input_prompt="b", output_prompt="B")
        hm.toggle_favorite(e1.id)
        removed = hm.clear(keep_favorites=True)
        assert removed == 1
        assert len(hm.list_entries()) == 1

    def test_clear_all(self, hm: HistoryManager):
        hm.record(input_prompt="a", output_prompt="A")
        hm.record(input_prompt="b", output_prompt="B")
        removed = hm.clear(keep_favorites=False)
        assert removed == 2
        assert len(hm.list_entries()) == 0


# ══════════════════════════════════════════════════════════════════
# HistoryManager — max_entries
# ══════════════════════════════════════════════════════════════════

class TestHistoryManagerMaxEntries:
    def test_max_entries_enforced(self, tmp_path: Path):
        hm = HistoryManager(history_file=tmp_path / "h.jsonl", max_entries=3)
        hm.load()
        for i in range(5):
            hm.record(input_prompt=f"p{i}", output_prompt=f"P{i}")
        assert len(hm.list_entries()) == 3

    def test_max_entries_keeps_favorites(self, tmp_path: Path):
        hm = HistoryManager(history_file=tmp_path / "h.jsonl", max_entries=2)
        hm.load()
        e1 = hm.record(input_prompt="keep_me", output_prompt="A")
        hm.toggle_favorite(e1.id)
        hm.record(input_prompt="p2", output_prompt="B")
        hm.record(input_prompt="p3", output_prompt="C")
        hm.record(input_prompt="p4", output_prompt="D")

        assert hm.get(e1.id) is not None   # favorite は保護される


# ══════════════════════════════════════════════════════════════════
# HistoryManager — compare
# ══════════════════════════════════════════════════════════════════

class TestHistoryManagerCompare:
    def test_compare_two_entries(self, hm: HistoryManager):
        e1 = hm.record(input_prompt="a", output_prompt="masterpiece", overall_score=70.0)
        e2 = hm.record(input_prompt="b", output_prompt="masterpiece, blue_eyes", overall_score=85.0)
        diff = hm.compare(e1.id, e2.id)
        assert "blue_eyes" in diff.added_tags
        assert diff.score_delta == 15.0

    def test_compare_missing_id_raises(self, hm: HistoryManager):
        e1 = hm.record(input_prompt="a", output_prompt="A")
        with pytest.raises(KeyError):
            hm.compare(e1.id, "ghost")

    def test_compare_with_latest(self, hm: HistoryManager):
        e1 = hm.record(input_prompt="a", output_prompt="masterpiece")
        time.sleep(0.01)
        hm.record(input_prompt="b", output_prompt="masterpiece, blue_eyes")
        diff = hm.compare_with_latest(e1.id)
        assert diff is not None
        assert "blue_eyes" in diff.added_tags

    def test_compare_with_latest_self_returns_none(self, hm: HistoryManager):
        e1 = hm.record(input_prompt="a", output_prompt="A")
        diff = hm.compare_with_latest(e1.id)
        assert diff is None

    def test_compare_with_latest_empty_history(self, hm: HistoryManager):
        diff = hm.compare_with_latest("ghost")
        assert diff is None


# ══════════════════════════════════════════════════════════════════
# HistoryManager — statistics
# ══════════════════════════════════════════════════════════════════

class TestHistoryManagerStatistics:
    def test_statistics_keys(self, hm: HistoryManager):
        hm.record(input_prompt="a", output_prompt="A", overall_score=80.0)
        stats = hm.statistics()
        for key in ("total_entries", "favorite_count", "avg_score", "max_score", "min_score"):
            assert key in stats

    def test_statistics_avg_score(self, hm: HistoryManager):
        hm.record(input_prompt="a", output_prompt="A", overall_score=60.0)
        hm.record(input_prompt="b", output_prompt="B", overall_score=80.0)
        stats = hm.statistics()
        assert stats["avg_score"] == 70.0

    def test_statistics_empty(self, hm: HistoryManager):
        stats = hm.statistics()
        assert stats["total_entries"] == 0
        assert stats["avg_score"] == 0.0

    def test_repr(self, hm: HistoryManager):
        assert "HistoryManager" in repr(hm)
