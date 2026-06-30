"""
fps-tools/tests/unit/test_comfyui_extra_nodes.py

M2-5 で追加した ComfyUI ノード3種のユニットテスト。
  - FacePromptPresetNode
  - FacePromptRuleEditorNode
  - FacePromptCategoryFilterNode

pytest で実行: pytest fps-tools/tests/unit/test_comfyui_extra_nodes.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from comfyui.nodes.face_prompt_category_filter import FacePromptCategoryFilterNode
from comfyui.nodes.face_prompt_preset import FacePromptPresetNode, _list_preset_ids
from comfyui.nodes.face_prompt_rule_editor import FacePromptRuleEditorNode


# ══════════════════════════════════════════════════════════════════
# NODE_CLASS_MAPPINGS 統合確認
# ══════════════════════════════════════════════════════════════════

class TestNodeRegistration:
    def test_all_six_nodes_registered(self):
        from comfyui import NODE_CLASS_MAPPINGS

        expected = {
            "FacePromptCleaner",
            "FacePromptCompiler",
            "FacePromptDebug",
            "FacePromptPreset",
            "FacePromptRuleEditor",
            "FacePromptCategoryFilter",
        }
        assert expected.issubset(set(NODE_CLASS_MAPPINGS.keys()))

    def test_new_nodes_have_display_names(self):
        from comfyui import NODE_DISPLAY_NAME_MAPPINGS

        for node_id in ("FacePromptPreset", "FacePromptRuleEditor", "FacePromptCategoryFilter"):
            assert node_id in NODE_DISPLAY_NAME_MAPPINGS
            assert "🎭" in NODE_DISPLAY_NAME_MAPPINGS[node_id]


# ══════════════════════════════════════════════════════════════════
# FacePromptPresetNode
# ══════════════════════════════════════════════════════════════════

class TestFacePromptPresetNode:
    def test_input_types_structure(self):
        types = FacePromptPresetNode.INPUT_TYPES()
        assert "required" in types
        assert "preset_id" in types["required"]

    def test_return_types(self):
        assert FacePromptPresetNode.RETURN_TYPES == ("STRING", "STRING", "STRING", "INT")

    def test_function_name(self):
        assert FacePromptPresetNode.FUNCTION == "apply_preset"

    def test_apply_known_preset(self):
        node = FacePromptPresetNode()
        prompt, negative, name, count = node.apply_preset(preset_id="anime_portrait")
        assert count > 0
        assert isinstance(prompt, str)
        assert name != ""

    def test_apply_unknown_preset_returns_error(self):
        node = FacePromptPresetNode()
        prompt, negative, name, count = node.apply_preset(preset_id="nonexistent_xyz")
        assert count == 0
        assert "[ERROR]" in name

    def test_apply_with_extra_prompt(self):
        node = FacePromptPresetNode()
        prompt, _, _, _ = node.apply_preset(
            preset_id="anime_portrait",
            extra_prompt="extra_custom_tag",
        )
        assert "extra_custom_tag" in prompt

    def test_apply_with_merge(self):
        node = FacePromptPresetNode()
        prompt, _, name, count = node.apply_preset(
            preset_id="anime_portrait",
            merge_with="realistic_portrait",
        )
        assert "Merged" in name
        assert count > 0

    def test_apply_negative_tags_included(self):
        node = FacePromptPresetNode()
        _, negative, _, _ = node.apply_preset(preset_id="anime_portrait")
        assert isinstance(negative, str)

    def test_list_preset_ids_not_empty(self):
        ids = _list_preset_ids()
        assert len(ids) > 0

    def test_list_preset_ids_contains_known(self):
        ids = _list_preset_ids()
        assert "anime_portrait" in ids


# ══════════════════════════════════════════════════════════════════
# FacePromptRuleEditorNode
# ══════════════════════════════════════════════════════════════════

class TestFacePromptRuleEditorNode:
    def test_input_types_structure(self):
        types = FacePromptRuleEditorNode.INPUT_TYPES()
        assert "optional" in types

    def test_return_types(self):
        assert FacePromptRuleEditorNode.RETURN_TYPES == ("STRING", "STRING")

    def test_function_name(self):
        assert FacePromptRuleEditorNode.FUNCTION == "edit_rules"

    def test_edit_rules_basic_report(self):
        node = FacePromptRuleEditorNode()
        report, test_result = node.edit_rules()
        assert "Face Prompt Rule Editor" in report
        assert "Total rules" in report

    def test_edit_rules_lists_all_rules(self):
        node = FacePromptRuleEditorNode()
        report, _ = node.edit_rules()
        assert "rule_weight_masterpiece" in report

    def test_edit_rules_with_test_prompt(self):
        node = FacePromptRuleEditorNode()
        _, test_result = node.edit_rules(test_prompt="masterpiece")
        assert "Input  :" in test_result
        assert "Output :" in test_result

    def test_edit_rules_test_prompt_shows_applied_rules(self):
        node = FacePromptRuleEditorNode()
        _, test_result = node.edit_rules(test_prompt="masterpiece")
        assert "Applied rules" in test_result

    def test_edit_rules_empty_test_prompt(self):
        node = FacePromptRuleEditorNode()
        report, test_result = node.edit_rules(test_prompt="")
        assert test_result == ""
        assert report != ""

    def test_disable_rule_id_does_not_persist(self):
        """ノードでの一時無効化が他のテストに影響を残さないこと"""
        node = FacePromptRuleEditorNode()
        node.edit_rules(disable_rule_ids="rule_weight_masterpiece")

        from comfyui.nodes.node_base import _get_rule_manager
        rm = _get_rule_manager()
        rule = rm.get_rule("rule_weight_masterpiece")
        assert rule is not None
        assert rule.enabled is True   # 元に戻っていること

    def test_disable_rule_reflected_in_report(self):
        node = FacePromptRuleEditorNode()
        report, _ = node.edit_rules(disable_rule_ids="rule_weight_masterpiece")
        assert "Temporarily Disabled" in report


# ══════════════════════════════════════════════════════════════════
# FacePromptCategoryFilterNode
# ══════════════════════════════════════════════════════════════════

class TestFacePromptCategoryFilterNode:
    def test_input_types_structure(self):
        types = FacePromptCategoryFilterNode.INPUT_TYPES()
        assert "prompt" in types["required"]
        assert "categories" in types["required"]
        assert "mode" in types["required"]

    def test_return_types(self):
        assert FacePromptCategoryFilterNode.RETURN_TYPES == ("STRING", "INT", "STRING")

    def test_function_name(self):
        assert FacePromptCategoryFilterNode.FUNCTION == "filter_category"

    def test_keep_only_mode(self):
        node = FacePromptCategoryFilterNode()
        filtered, count, report = node.filter_category(
            prompt="masterpiece, blue_eyes, elf_ears",
            categories="eyes",
            mode="keep_only",
        )
        assert count == 1
        assert "blue_eyes" in filtered or "Eyes" in filtered

    def test_exclude_mode(self):
        node = FacePromptCategoryFilterNode()
        filtered, count, report = node.filter_category(
            prompt="anime, blue_eyes, elf_ears",
            categories="eyes",
            mode="exclude",
        )
        assert count == 2

    def test_multiple_categories(self):
        node = FacePromptCategoryFilterNode()
        _, count, _ = node.filter_category(
            prompt="masterpiece, blue_eyes, elf_ears, long_hair",
            categories="eyes,hair",
            mode="keep_only",
        )
        assert count == 2

    def test_no_match_returns_zero(self):
        node = FacePromptCategoryFilterNode()
        _, count, _ = node.filter_category(
            prompt="masterpiece",
            categories="nonexistent_category",
            mode="keep_only",
        )
        assert count == 0

    def test_report_shows_all_categories(self):
        node = FacePromptCategoryFilterNode()
        _, _, report = node.filter_category(
            prompt="masterpiece, blue_eyes",
            categories="eyes",
            mode="keep_only",
        )
        assert "Category Filter Report" in report
        assert "All Categories in Input" in report

    def test_empty_prompt(self):
        node = FacePromptCategoryFilterNode()
        filtered, count, _ = node.filter_category(
            prompt="",
            categories="eyes",
            mode="keep_only",
        )
        assert count == 0


# ══════════════════════════════════════════════════════════════════
# 全ノード共通インターフェース整合性（追加分）
# ══════════════════════════════════════════════════════════════════

class TestExtraNodesInterface:
    @pytest.mark.parametrize(
        "node_class",
        [FacePromptPresetNode, FacePromptRuleEditorNode, FacePromptCategoryFilterNode],
    )
    def test_category_set(self, node_class):
        assert node_class.CATEGORY == "FacePromptStudio"

    @pytest.mark.parametrize(
        "node_class",
        [FacePromptPresetNode, FacePromptRuleEditorNode, FacePromptCategoryFilterNode],
    )
    def test_return_names_match_types_length(self, node_class):
        assert len(node_class.RETURN_TYPES) == len(node_class.RETURN_NAMES)

    @pytest.mark.parametrize(
        "node_class",
        [FacePromptPresetNode, FacePromptRuleEditorNode, FacePromptCategoryFilterNode],
    )
    def test_function_method_exists(self, node_class):
        assert hasattr(node_class, node_class.FUNCTION)
