"""
fps-tools/tests/unit/test_comfyui_history_node.py

FacePromptHistoryNode のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_comfyui_history_node.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from comfyui.nodes.face_prompt_history import FacePromptHistoryNode


@pytest.fixture(autouse=True)
def isolate_history_manager(tmp_path, monkeypatch):
    """各テストで独立した HistoryManager を使うようにモンキーパッチする"""
    import comfyui.nodes.face_prompt_history as fh
    from history.history_manager import HistoryManager

    fh._history_manager = None
    test_path = tmp_path / "test_history.jsonl"

    def _get_isolated_manager():
        global_mgr = HistoryManager(history_file=test_path, max_entries=100)
        global_mgr.load()
        return global_mgr

    monkeypatch.setattr(fh, "_get_history_manager", _get_isolated_manager)
    yield


class TestFacePromptHistoryNode:
    def test_registered(self):
        from comfyui import NODE_CLASS_MAPPINGS

        assert "FacePromptHistory" in NODE_CLASS_MAPPINGS

    def test_display_name(self):
        from comfyui import NODE_DISPLAY_NAME_MAPPINGS

        assert "🎭" in NODE_DISPLAY_NAME_MAPPINGS["FacePromptHistory"]

    def test_input_types_structure(self):
        types = FacePromptHistoryNode.INPUT_TYPES()
        assert "record" in types["required"]

    def test_return_types(self):
        assert FacePromptHistoryNode.RETURN_TYPES == ("STRING", "STRING")

    def test_function_name(self):
        assert FacePromptHistoryNode.FUNCTION == "track_history"

    def test_track_history_records_entry(self):
        node = FacePromptHistoryNode()
        report, entry_id = node.track_history(
            record=True,
            input_prompt="masterpiece",
            output_prompt="Quality.High",
            overall_score=80.0,
        )
        assert entry_id != ""
        assert "Total entries" in report

    def test_track_history_no_record_when_false(self):
        node = FacePromptHistoryNode()
        report, entry_id = node.track_history(
            record=False,
            input_prompt="masterpiece",
            output_prompt="Quality.High",
        )
        assert entry_id == ""

    def test_track_history_no_record_when_empty_prompts(self):
        node = FacePromptHistoryNode()
        report, entry_id = node.track_history(record=True)
        assert entry_id == ""

    def test_track_history_report_contains_stats(self):
        node = FacePromptHistoryNode()
        report, _ = node.track_history(
            record=True,
            input_prompt="a",
            output_prompt="A",
        )
        assert "Avg score" in report
        assert "Favorites" in report

    def test_track_history_shows_recent_entries(self):
        node = FacePromptHistoryNode()
        node.track_history(record=True, input_prompt="first", output_prompt="F")
        report, _ = node.track_history(record=True, input_prompt="second", output_prompt="S")
        assert "second" in report
        assert "first" in report

    def test_track_history_shows_diff_when_multiple_entries(self):
        node = FacePromptHistoryNode()
        node.track_history(record=True, input_prompt="a", output_prompt="masterpiece")
        report, _ = node.track_history(
            record=True, input_prompt="b", output_prompt="masterpiece, blue_eyes"
        )
        assert "Diff" in report

    def test_track_history_with_label(self):
        node = FacePromptHistoryNode()
        report, _ = node.track_history(
            record=True,
            input_prompt="a",
            output_prompt="A",
            label="my favorite",
        )
        assert "my favorite" in report
