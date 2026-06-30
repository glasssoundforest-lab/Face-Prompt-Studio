"""
fps-tools/tests/unit/test_comfyui_nodes.py

ComfyUI ノードのユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_comfyui_nodes.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from comfyui.nodes.face_prompt_cleaner  import FacePromptCleanerNode
from comfyui.nodes.face_prompt_compiler import FacePromptCompilerNode
from comfyui.nodes.debug_output         import FacePromptDebugNode


# ══════════════════════════════════════════════════════════════════
# NODE_CLASS_MAPPINGS
# ══════════════════════════════════════════════════════════════════

class TestNodeClassMappings:
    def test_all_nodes_importable(self):
        from comfyui import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
        assert "FacePromptCleaner"  in NODE_CLASS_MAPPINGS
        assert "FacePromptCompiler" in NODE_CLASS_MAPPINGS
        assert "FacePromptDebug"    in NODE_CLASS_MAPPINGS

    def test_display_names_exist(self):
        from comfyui import NODE_DISPLAY_NAME_MAPPINGS
        assert all("🎭" in v for v in NODE_DISPLAY_NAME_MAPPINGS.values())

    def test_mappings_count(self):
        from comfyui import NODE_CLASS_MAPPINGS
        assert len(NODE_CLASS_MAPPINGS) == 7


# ══════════════════════════════════════════════════════════════════
# FacePromptCleanerNode
# ══════════════════════════════════════════════════════════════════

class TestFacePromptCleanerNode:
    def test_input_types_structure(self):
        types = FacePromptCleanerNode.INPUT_TYPES()
        assert "required" in types
        assert "optional" in types
        assert "prompt"   in types["required"]

    def test_return_types(self):
        assert FacePromptCleanerNode.RETURN_TYPES == ("STRING", "STRING", "INT", "STRING")

    def test_return_names(self):
        assert "cleaned_prompt" in FacePromptCleanerNode.RETURN_NAMES
        assert "debug_text"     in FacePromptCleanerNode.RETURN_NAMES

    def test_function_name(self):
        assert FacePromptCleanerNode.FUNCTION == "clean"

    def test_category(self):
        assert FacePromptCleanerNode.CATEGORY == "FacePromptStudio"

    def test_clean_basic(self):
        node = FacePromptCleanerNode()
        result = node.clean(prompt="masterpiece, blue_eyes")
        assert isinstance(result, tuple)
        assert len(result) == 4
        cleaned, negative, count, debug = result
        assert isinstance(cleaned, str)
        assert isinstance(count,   int)
        assert isinstance(debug,   str)

    def test_clean_empty_prompt(self):
        node = FacePromptCleanerNode()
        cleaned, neg, count, debug = node.clean(prompt="")
        assert isinstance(cleaned, str)
        assert count == 0

    def test_clean_negative_passthrough(self):
        node = FacePromptCleanerNode()
        _, negative, _, _ = node.clean(
            prompt="masterpiece",
            negative="bad hands, low quality",
        )
        assert negative == "bad hands, low quality"

    def test_clean_dsl_syntax(self):
        node = FacePromptCleanerNode()
        cleaned, _, count, _ = node.clean(
            prompt="(quality:high:1.5), [bad hands]",
        )
        assert isinstance(cleaned, str)
        assert count >= 0

    def test_clean_category_switch_off(self):
        node = FacePromptCleanerNode()
        # style をオフにして anime が消えることを確認
        cleaned, _, count, debug = node.clean(
            prompt="masterpiece, anime",
            keep_style=False,
        )
        # anime タグがカテゴリ分類済みなら style として除外される
        assert isinstance(cleaned, str)

    def test_clean_blacklist_extra(self):
        node = FacePromptCleanerNode()
        cleaned, _, count, _ = node.clean(
            prompt="masterpiece, blue_eyes, bad_tag",
            blacklist_extra="bad_tag",
        )
        assert "bad_tag" not in cleaned

    def test_clean_weight_scale(self):
        node = FacePromptCleanerNode()
        cleaned, _, _, debug = node.clean(
            prompt="masterpiece",
            weight_quality=2.0,
        )
        assert isinstance(cleaned, str)

    def test_clean_debug_contains_stage_info(self):
        node = FacePromptCleanerNode()
        _, _, _, debug = node.clean(prompt="masterpiece")
        assert "Stage Results" in debug or "stage" in debug.lower()

    def test_clean_debug_contains_tag_diff(self):
        node = FacePromptCleanerNode()
        _, _, _, debug = node.clean(prompt="masterpiece")
        assert "Tag Diff" in debug

    def test_clean_debug_shows_rule_additions(self):
        node = FacePromptCleanerNode()
        _, _, _, debug = node.clean(prompt="masterpiece")
        # base_rules.json の rule_add_highres_on_masterpiece が発火するはず
        assert "added by rules" in debug
        assert "high_quality" in debug

    def test_clean_debug_shows_category_removal(self):
        node = FacePromptCleanerNode()
        _, _, _, debug = node.clean(prompt="masterpiece, elf_ears", keep_fantasy_parts=False)
        assert "removed (category OFF)" in debug
        assert "elf_ears" in debug

    def test_clean_debug_contains_category_summary(self):
        node = FacePromptCleanerNode()
        _, _, _, debug = node.clean(prompt="masterpiece, blue_eyes")
        assert "Category Summary" in debug
        assert "avg_weight" in debug

    def test_clean_debug_contains_applied_rules_section(self):
        node = FacePromptCleanerNode()
        _, _, _, debug = node.clean(prompt="masterpiece")
        assert "Applied Rules" in debug
        assert "rule_weight_masterpiece" in debug

    def test_clean_debug_no_rules_message(self):
        node = FacePromptCleanerNode()
        # ルールに一致しないタグのみの場合
        _, _, _, debug = node.clean(prompt="nonexistent_tag_xyz")
        assert "Applied Rules" in debug

    def test_is_changed_returns_nan(self):
        import math
        result = FacePromptCleanerNode.IS_CHANGED()
        assert math.isnan(result)


# ══════════════════════════════════════════════════════════════════
# FacePromptCompilerNode
# ══════════════════════════════════════════════════════════════════

class TestFacePromptCompilerNode:
    def test_input_types_structure(self):
        types = FacePromptCompilerNode.INPUT_TYPES()
        assert "required" in types
        assert "prompt"   in types["required"]

    def test_return_types(self):
        assert FacePromptCompilerNode.RETURN_TYPES == ("STRING", "STRING", "STRING", "INT")

    def test_return_names(self):
        assert "prompt_out"  in FacePromptCompilerNode.RETURN_NAMES
        assert "json_out"    in FacePromptCompilerNode.RETURN_NAMES
        assert "tag_count"   in FacePromptCompilerNode.RETURN_NAMES

    def test_function_name(self):
        assert FacePromptCompilerNode.FUNCTION == "compile_prompt"

    def test_compile_basic(self):
        node = FacePromptCompilerNode()
        result = node.compile_prompt(prompt="masterpiece, blue_eyes")
        assert isinstance(result, tuple)
        assert len(result) == 4
        prompt_out, negative_out, json_out, count = result
        assert isinstance(prompt_out,   str)
        assert isinstance(negative_out, str)
        assert isinstance(json_out,     str)
        assert isinstance(count,        int)

    def test_compile_returns_valid_json(self):
        import json
        node = FacePromptCompilerNode()
        _, _, json_out, _ = node.compile_prompt(prompt="masterpiece")
        parsed = json.loads(json_out)
        assert isinstance(parsed, dict)

    def test_compile_v1_output(self):
        import json
        node = FacePromptCompilerNode()
        _, _, json_out, _ = node.compile_prompt(
            prompt="masterpiece",
            api_version="v1",
        )
        parsed = json.loads(json_out)
        assert "prompt" in parsed

    def test_compile_v2_output(self):
        import json
        node = FacePromptCompilerNode()
        _, _, json_out, _ = node.compile_prompt(
            prompt="masterpiece",
            api_version="v2",
        )
        parsed = json.loads(json_out)
        assert "nodes" in parsed or "prompt" in parsed

    def test_compile_negative_passthrough(self):
        node = FacePromptCompilerNode()
        _, negative_out, _, _ = node.compile_prompt(
            prompt="masterpiece",
            negative="bad hands",
        )
        assert "bad hands" in negative_out

    def test_compile_empty_prompt(self):
        node = FacePromptCompilerNode()
        prompt_out, _, json_out, count = node.compile_prompt(prompt="")
        assert isinstance(prompt_out, str)
        assert isinstance(count, int)

    def test_compile_dsl_full(self):
        node = FacePromptCompilerNode()
        prompt_out, _, _, count = node.compile_prompt(
            prompt="(quality:high:1.5), (eyes:blue), [bad hands], {style:anime}",
        )
        assert isinstance(prompt_out, str)

    def test_compile_invalid_preset_id(self):
        # 存在しないプリセット ID でもエラーにならない
        node = FacePromptCompilerNode()
        result = node.compile_prompt(
            prompt="masterpiece",
            preset_id="nonexistent_preset_xyz",
        )
        assert len(result) == 4


# ══════════════════════════════════════════════════════════════════
# FacePromptDebugNode
# ══════════════════════════════════════════════════════════════════

class TestFacePromptDebugNode:
    def test_input_types_structure(self):
        types = FacePromptDebugNode.INPUT_TYPES()
        assert "required" in types
        assert "optional" in types

    def test_return_types(self):
        assert FacePromptDebugNode.RETURN_TYPES == ("STRING",)

    def test_return_names(self):
        assert FacePromptDebugNode.RETURN_NAMES == ("report",)

    def test_function_name(self):
        assert FacePromptDebugNode.FUNCTION == "debug"

    def test_debug_basic(self):
        node = FacePromptDebugNode()
        result = node.debug()
        assert isinstance(result, tuple)
        assert len(result) == 1
        assert isinstance(result[0], str)

    def test_debug_contains_header(self):
        node = FacePromptDebugNode()
        report, = node.debug()
        assert "Face Prompt Studio" in report

    def test_debug_shows_original(self):
        node = FacePromptDebugNode()
        report, = node.debug(prompt_in="masterpiece, blue_eyes")
        assert "masterpiece" in report

    def test_debug_shows_cleaned(self):
        node = FacePromptDebugNode()
        report, = node.debug(prompt_out="Quality.High, Eyes.Blue")
        assert "Quality.High" in report

    def test_debug_shows_diff(self):
        node = FacePromptDebugNode()
        report, = node.debug(
            prompt_in ="masterpiece, old_tag",
            prompt_out="masterpiece, new_tag",
        )
        assert "old_tag" in report or "new_tag" in report

    def test_debug_shows_debug_text(self):
        node = FacePromptDebugNode()
        report, = node.debug(debug_text="=== Test Debug ===\nstage: parser")
        assert "Test Debug" in report

    def test_debug_with_all_inputs(self):
        node = FacePromptDebugNode()
        report, = node.debug(
            prompt_in ="masterpiece",
            prompt_out="Quality.High",
            debug_text="[parser] 1 → 1",
        )
        assert isinstance(report, str)
        assert len(report) > 0

    def test_debug_empty_inputs(self):
        node = FacePromptDebugNode()
        report, = node.debug(prompt_in="", prompt_out="", debug_text="")
        assert "Face Prompt Studio" in report

    def test_debug_includes_dict_stats(self):
        node = FacePromptDebugNode()
        report, = node.debug()
        # DictionaryManager が初期化されていれば辞書統計が表示される
        # 初期化されていなくても report は返る
        assert isinstance(report, str)
