"""
fps-tools/tests/unit/test_comfyui_group_control_node.py

FacePromptGroupControlNode のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_comfyui_group_control_node.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from comfyui.nodes.face_prompt_group_control import FacePromptGroupControlNode


class TestNodeRegistration:
    def test_registered(self):
        from comfyui import NODE_CLASS_MAPPINGS

        assert "FacePromptGroupControl" in NODE_CLASS_MAPPINGS

    def test_display_name(self):
        from comfyui import NODE_DISPLAY_NAME_MAPPINGS

        assert "🎭" in NODE_DISPLAY_NAME_MAPPINGS["FacePromptGroupControl"]

    def test_total_node_count_is_ten(self):
        from comfyui import NODE_CLASS_MAPPINGS

        assert len(NODE_CLASS_MAPPINGS) == 10


class TestFacePromptGroupControlNode:
    def test_input_types_structure(self):
        types = FacePromptGroupControlNode.INPUT_TYPES()
        assert "prompt" in types["required"]
        assert "group_hair" in types["optional"]
        assert "weight_hair" in types["optional"]

    def test_input_types_has_five_group_switches(self):
        types = FacePromptGroupControlNode.INPUT_TYPES()
        group_switches = [k for k in types["optional"] if k.startswith("group_")]
        assert len(group_switches) == 5

    def test_return_types(self):
        assert FacePromptGroupControlNode.RETURN_TYPES == ("STRING", "STRING", "INT", "STRING")

    def test_function_name(self):
        assert FacePromptGroupControlNode.FUNCTION == "clean_by_group"

    def test_category(self):
        assert FacePromptGroupControlNode.CATEGORY == "FacePromptStudio"

    def test_clean_basic(self):
        node = FacePromptGroupControlNode()
        cleaned, neg, count, report = node.clean_by_group(prompt="masterpiece, blue_eyes")
        assert isinstance(cleaned, str)
        assert count >= 1
        assert "Group Control Report" in report

    def test_group_fantasy_off_excludes_fantasy_tags(self):
        node = FacePromptGroupControlNode()
        cleaned, _, count, report = node.clean_by_group(
            prompt="masterpiece, elf_ears",
            group_fantasy=False,
        )
        assert "elf_ears" not in cleaned
        assert "Skipped" in report

    def test_group_fantasy_on_includes_fantasy_tags(self):
        node = FacePromptGroupControlNode()
        cleaned, _, count, _ = node.clean_by_group(
            prompt="masterpiece, elf_ears",
            group_fantasy=True,
        )
        assert "Fantasy.ElfEars" in cleaned or "elf_ears" in cleaned

    def test_weight_face_parts_applied(self):
        node = FacePromptGroupControlNode()
        cleaned_default, _, _, _ = node.clean_by_group(prompt="blue_eyes")
        cleaned_boosted, _, _, _ = node.clean_by_group(
            prompt="blue_eyes",
            weight_face_parts=2.0,
        )
        # 重み倍率2.0を掛けた方が常に高い重みになっているはず
        import re

        def extract_weight(s: str) -> float:
            m = re.search(r":(\d+\.\d+)\)", s)
            return float(m.group(1)) if m else 1.0

        assert extract_weight(cleaned_boosted) > extract_weight(cleaned_default)

    def test_report_shows_all_groups(self):
        node = FacePromptGroupControlNode()
        _, _, _, report = node.clean_by_group(prompt="masterpiece")
        for label in ("品質・画風", "顔パーツ", "髪", "アクセサリー・メイク", "ファンタジー"):
            assert label in report

    def test_negative_passthrough(self):
        node = FacePromptGroupControlNode()
        _, negative, _, _ = node.clean_by_group(prompt="masterpiece, [bad hands]")
        assert "bad_hands" in negative

    def test_empty_prompt(self):
        node = FacePromptGroupControlNode()
        cleaned, _, count, _ = node.clean_by_group(prompt="")
        assert count == 0

    def test_all_groups_off(self):
        """
        全グループOFF時、定義済み17カテゴリのタグは全て除外される。
        ただし RuleEngine が動的追加するタグ（category="auto" 等、
        どのグループにも属さない）はフィルタ対象外のため残る可能性がある
        （これは仕様：未知カテゴリは安全側に倒して除外しない）。
        """
        node = FacePromptGroupControlNode()
        cleaned, _, count, _ = node.clean_by_group(
            prompt="blue_eyes, long_hair, elf_ears",
            group_quality_style=False,
            group_face_parts=False,
            group_hair=False,
            group_accessories=False,
            group_fantasy=False,
        )
        assert count == 0
        assert cleaned == ""

    def test_max_weight_clamping(self):
        node = FacePromptGroupControlNode()
        cleaned, _, _, _ = node.clean_by_group(
            prompt="blue_eyes",
            weight_face_parts=3.0,
            max_weight=1.5,
        )
        assert ":3.00" not in cleaned
