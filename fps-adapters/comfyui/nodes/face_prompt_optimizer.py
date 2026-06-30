"""
fps-adapters/comfyui/nodes/face_prompt_optimizer.py
ノード: 🎭 Face Prompt Optimizer

機能:
  - プロンプトを分析して品質スコア・矛盾・冗長性を検出する
  - 改善提案を自動生成する
  - 不足カテゴリのタグ候補を提案する

入力:
  prompt    STRING  分析対象プロンプト

出力:
  report         STRING  分析レポート（スコア・問題点・提案）
  overall_score  FLOAT   総合品質スコア（0-100）
  has_conflicts  BOOLEAN 矛盾の有無
"""

from __future__ import annotations

from typing import Any

from .node_base import FPSNodeBase, _get_pipeline_manager


def _get_optimizer_manager(dictionary_manager: Any = None):
    """OptimizerManager を取得する"""
    from optimizer.manager import OptimizerManager

    return OptimizerManager(dictionary_manager=dictionary_manager)


class FacePromptOptimizerNode(FPSNodeBase):
    """Face Prompt Optimizer ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "FLOAT", "BOOLEAN")
    RETURN_NAMES = ("report", "overall_score", "has_conflicts")
    FUNCTION = "optimize"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "分析対象プロンプト",
                    },
                ),
            },
        }

    def optimize(self, prompt: str) -> tuple[str, float, bool]:
        """
        プロンプトを分析して品質レポートを生成する。

        Returns:
            (report, overall_score, has_conflicts)
        """
        pm = _get_pipeline_manager()
        if pm is None:
            return "[ERROR] PipelineManager の初期化に失敗しました。", 0.0, False

        from comfyui.nodes.node_base import _get_dictionary_manager

        pipeline_result = pm.compile(prompt)
        om = _get_optimizer_manager(dictionary_manager=_get_dictionary_manager())
        result = om.analyze_pipeline_result(pipeline_result)

        # ── レポート生成 ──────────────────────────────────
        lines = [
            "=== Face Prompt Optimizer Report ===",
            "",
            "▶ Quality Score:",
            f"  Overall    : {result.score.overall_score:.1f} / 100",
            f"  Coverage   : {result.score.coverage_score:.1f} / 100",
            f"  Balance    : {result.score.balance_score:.1f} / 100",
            f"  Redundancy : {result.score.redundancy_score:.1f} / 100",
            "",
        ]

        if result.issues:
            lines.append(f"▶ Issues ({result.issue_count}):")
            for issue in result.issues:
                lines.append(f"  [{issue.severity.upper()}] {issue.message}")
                if issue.suggestion:
                    lines.append(f"      → {issue.suggestion}")
        else:
            lines.append("▶ Issues: none detected")

        lines.append("")
        lines.append("▶ Recommendations:")
        for rec in result.recommendations:
            lines.append(f"  - {rec}")

        suggestions = om.suggest_tags(
            [
                {"tag": t.tag, "category": t.category, "weight": t.weight}
                for t in pipeline_result.tags
            ]
        )
        if suggestions:
            lines.append("")
            lines.append("▶ Suggested Tags to Add:")
            lines.append(f"  {', '.join(suggestions)}")

        report = "\n".join(lines)

        has_conflicts = any(issue.type.value == "conflict" for issue in result.issues)

        return report, result.score.overall_score, has_conflicts
