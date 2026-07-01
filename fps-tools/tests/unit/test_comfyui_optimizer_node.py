"""
fps-tools/tests/unit/test_comfyui_optimizer_node.py

FacePromptOptimizerNode のユニットテスト。
RuleEngineStage の meta 引き継ぎバグ修正の回帰テストも含む。

pytest で実行: pytest fps-tools/tests/unit/test_comfyui_optimizer_node.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from comfyui.nodes.face_prompt_optimizer import FacePromptOptimizerNode
from comfyui.nodes.node_base import _get_pipeline_manager


# ══════════════════════════════════════════════════════════════════
# NODE_CLASS_MAPPINGS 統合
# ══════════════════════════════════════════════════════════════════

class TestOptimizerNodeRegistration:
    def test_registered(self):
        from comfyui import NODE_CLASS_MAPPINGS

        assert "FacePromptOptimizer" in NODE_CLASS_MAPPINGS

    def test_display_name(self):
        from comfyui import NODE_DISPLAY_NAME_MAPPINGS

        assert "🎭" in NODE_DISPLAY_NAME_MAPPINGS["FacePromptOptimizer"]

    def test_total_node_count_is_eight(self):
        from comfyui import NODE_CLASS_MAPPINGS

        assert len(NODE_CLASS_MAPPINGS) == 10


# ══════════════════════════════════════════════════════════════════
# FacePromptOptimizerNode
# ══════════════════════════════════════════════════════════════════

class TestFacePromptOptimizerNode:
    def test_input_types_structure(self):
        types = FacePromptOptimizerNode.INPUT_TYPES()
        assert "prompt" in types["required"]

    def test_return_types(self):
        assert FacePromptOptimizerNode.RETURN_TYPES == ("STRING", "FLOAT", "BOOLEAN")

    def test_function_name(self):
        assert FacePromptOptimizerNode.FUNCTION == "optimize"

    def test_category(self):
        assert FacePromptOptimizerNode.CATEGORY == "FacePromptStudio"

    def test_optimize_basic(self):
        node = FacePromptOptimizerNode()
        report, score, has_conflicts = node.optimize(prompt="masterpiece, blue_eyes")
        assert isinstance(report, str)
        assert isinstance(score, float)
        assert isinstance(has_conflicts, bool)
        assert 0 <= score <= 100

    def test_optimize_detects_conflict(self):
        node = FacePromptOptimizerNode()
        report, score, has_conflicts = node.optimize(
            prompt="blue_eyes, brown_eyes"
        )
        assert has_conflicts is True
        assert "eyes_color" in report or "矛盾" in report

    def test_optimize_no_conflict_clean_prompt(self):
        node = FacePromptOptimizerNode()
        _, _, has_conflicts = node.optimize(prompt="blue_eyes, long_hair")
        assert has_conflicts is False

    def test_optimize_report_contains_score_section(self):
        node = FacePromptOptimizerNode()
        report, _, _ = node.optimize(prompt="masterpiece")
        assert "Quality Score" in report
        assert "Overall" in report

    def test_optimize_report_contains_recommendations(self):
        node = FacePromptOptimizerNode()
        report, _, _ = node.optimize(prompt="masterpiece")
        assert "Recommendations" in report

    def test_optimize_empty_prompt(self):
        node = FacePromptOptimizerNode()
        report, score, has_conflicts = node.optimize(prompt="")
        assert isinstance(report, str)
        assert has_conflicts is False

    def test_optimize_suggests_missing_tags(self):
        node = FacePromptOptimizerNode()
        report, _, _ = node.optimize(prompt="masterpiece")
        assert "Suggested Tags" in report


# ══════════════════════════════════════════════════════════════════
# 回帰テスト: RuleEngineStage の meta 引き継ぎ
# ══════════════════════════════════════════════════════════════════

class TestMetaPropagationRegression:
    """
    バグ: RuleEngineStage が TagEntry を再構築する際に meta（resolved含む）
    を引き継いでおらず、ComfyUI ノード経由（rule_manager が常に context に
    設定される）では meta が常に失われていた。
    Optimizer ノード実装時に発見・修正。
    """

    def test_meta_resolved_preserved_through_rule_engine(self):
        pm = _get_pipeline_manager()
        result = pm.compile("masterpiece, blue_eyes")
        for t in result.tags:
            if t.tag in ("masterpiece", "blue_eyes"):
                assert "resolved" in t.meta, (
                    f"'{t.tag}' の meta['resolved'] が失われています: {t.meta}"
                )

    def test_meta_resolved_correct_value(self):
        pm = _get_pipeline_manager()
        result = pm.compile("blue_eyes")
        blue_eyes_tag = next((t for t in result.tags if t.tag == "blue_eyes"), None)
        assert blue_eyes_tag is not None
        assert blue_eyes_tag.meta.get("resolved") == "Eyes.Blue"

    def test_newly_added_rule_tag_has_empty_meta(self):
        """ルールで新規追加されたタグ（high_quality等）は meta が空でも正常"""
        pm = _get_pipeline_manager()
        result = pm.compile("masterpiece")
        added_tag = next((t for t in result.tags if t.tag == "high_quality"), None)
        if added_tag is not None:
            assert isinstance(added_tag.meta, dict)
