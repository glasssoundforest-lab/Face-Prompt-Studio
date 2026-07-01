"""
fps-tools/tests/unit/test_comfyui_template_node.py

FacePromptTemplateNode ユニットテスト（+15件）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from comfyui.nodes.face_prompt_template import FacePromptTemplateNode  # noqa: E402


@pytest.fixture(scope="module")
def node() -> FacePromptTemplateNode:
    return FacePromptTemplateNode()


class TestFacePromptTemplateNodeBasic:
    """基本動作テスト (6件)"""

    def test_node_has_required_attributes(self, node: FacePromptTemplateNode):
        assert node.CATEGORY == "FacePromptStudio"
        assert "STRING" in node.RETURN_TYPES
        assert node.FUNCTION == "render_template"

    def test_return_names_count(self, node: FacePromptTemplateNode):
        assert len(node.RETURN_NAMES) == 3
        assert "rendered" in node.RETURN_NAMES
        assert "missing" in node.RETURN_NAMES
        assert "report" in node.RETURN_NAMES

    def test_input_types_has_template_id(self, node: FacePromptTemplateNode):
        inputs = FacePromptTemplateNode.INPUT_TYPES()
        assert "template_id" in inputs["required"]

    def test_input_types_has_shortcut_fields(self, node: FacePromptTemplateNode):
        inputs = FacePromptTemplateNode.INPUT_TYPES()
        optional = inputs.get("optional", {})
        for field in ("quality", "eye_color", "hair_color", "expression"):
            assert field in optional

    def test_render_returns_tuple_of_three(self, node: FacePromptTemplateNode):
        result = node.render_template("face_basic")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_render_returns_strings(self, node: FacePromptTemplateNode):
        rendered, missing, report = node.render_template("face_basic")
        assert isinstance(rendered, str)
        assert isinstance(missing, str)
        assert isinstance(report, str)


class TestFacePromptTemplateNodeRender:
    """テンプレート展開テスト (6件)"""

    def test_render_with_shortcuts(self, node: FacePromptTemplateNode):
        rendered, missing, report = node.render_template(
            template_id="face_basic",
            quality="masterpiece",
            eye_color="blue_eyes",
            hair_color="blonde",
            hair_length="long",
            expression="smile",
        )
        assert "masterpiece" in rendered
        assert "blue_eyes" in rendered

    def test_render_with_json_variables(self, node: FacePromptTemplateNode):
        variables = {
            "quality": "best_quality",
            "eye_color": "red_eyes",
            "hair_color": "black",
            "hair_length": "short",
            "expression": "serious",
        }
        rendered, missing, report = node.render_template(
            template_id="face_basic",
            variables_json=json.dumps(variables),
        )
        assert "best_quality" in rendered
        assert "red_eyes" in rendered

    def test_shortcut_overrides_json(self, node: FacePromptTemplateNode):
        """ショートカット入力が JSON より優先されること"""
        rendered, _, _ = node.render_template(
            template_id="face_basic",
            variables_json='{"quality": "json_quality"}',
            quality="shortcut_quality",
            eye_color="blue_eyes",
            hair_color="gold",
            hair_length="long",
            expression="smile",
        )
        assert "shortcut_quality" in rendered

    def test_missing_variables_reported(self, node: FacePromptTemplateNode):
        """変数が不足している場合 missing に含まれること"""
        _, missing, _ = node.render_template(
            template_id="face_basic",
            quality="masterpiece",
            # eye_color, hair_color, hair_length, expression を省略
        )
        assert len(missing) > 0

    def test_full_variables_no_missing(self, node: FacePromptTemplateNode):
        """全変数が揃えば missing が空になること"""
        _, missing, _ = node.render_template(
            template_id="face_basic",
            quality="masterpiece",
            eye_color="blue_eyes",
            hair_color="blonde",
            hair_length="long",
            expression="smile",
        )
        assert missing == ""

    def test_invalid_template_id_returns_error(self, node: FacePromptTemplateNode):
        rendered, missing, report = node.render_template(
            template_id="__nonexistent_template__"
        )
        assert rendered == ""
        assert "ERROR" in report or "not found" in report.lower() or missing != ""


class TestFacePromptTemplateNodeTemplates:
    """テンプレート種別テスト (3件)"""

    def test_fantasy_character_template(self, node: FacePromptTemplateNode):
        rendered, _, _ = node.render_template(
            template_id="fantasy_character",
            quality="masterpiece",
            eye_color="purple_eyes",
            hair_color="silver_hair",
            fantasy_feature="cat_ears",
            expression="smile",
        )
        assert "masterpiece" in rendered
        assert "cat_ears" in rendered

    def test_negative_basic_template(self, node: FacePromptTemplateNode):
        rendered, _, _ = node.render_template(
            template_id="negative_basic",
            additional_negative="watermark, text",
        )
        assert "low_quality" in rendered
        assert "watermark" in rendered

    def test_report_contains_template_id(self, node: FacePromptTemplateNode):
        _, _, report = node.render_template(
            template_id="face_basic",
            quality="masterpiece",
        )
        assert "face_basic" in report
