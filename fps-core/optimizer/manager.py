"""
fps-core/optimizer/manager.py — OptimizerManager

矛盾検出・冗長検出・品質スコアリング・改善提案を統合する。

Public API:
  - analyze(tags)         矛盾/冗長検出 + スコアリング + 提案を一括実行
  - analyze_prompt(prompt) プロンプト文字列を直接分析（Pipeline経由）
"""

from __future__ import annotations

import logging
from typing import Any

from .conflict_detector import detect_conflicts
from .models import OptimizationResult
from .quality_scorer import calculate_quality_score
from .recommender import generate_recommendations, suggest_missing_tags
from .redundancy_detector import detect_redundancy

logger = logging.getLogger(__name__)


class OptimizerManager:
    """
    FPS プロンプト最適化分析クラス。

    使い方:
        om = OptimizerManager()
        tags = [
            {"tag": "blue_eyes",  "category": "eyes",  "weight": 1.0,
             "meta": {"resolved": "Eyes.Blue"}},
            {"tag": "brown_eyes", "category": "eyes",  "weight": 1.0,
             "meta": {"resolved": "Eyes.Brown"}},
        ]
        result = om.analyze(tags)
        print(result.score.overall_score)
        for issue in result.issues:
            print(issue.message)
    """

    def __init__(self, dictionary_manager: Any = None) -> None:
        self._dictionary_manager = dictionary_manager

    def analyze(self, tags: list[dict[str, Any]]) -> OptimizationResult:
        """
        タグリストを分析して OptimizationResult を返す。

        Args:
            tags: [{"tag": str, "category": str, "weight": float,
                    "meta": {"resolved": str}}, ...]

        Returns:
            OptimizationResult
        """
        conflicts = detect_conflicts(tags)
        redundancies = detect_redundancy(tags)
        issues = conflicts + redundancies

        score = calculate_quality_score(tags, issues=issues)
        recommendations = generate_recommendations(tags, issues, score)

        logger.debug(
            "Optimizer analysis: %d tags, %d issues, overall_score=%.1f",
            len(tags),
            len(issues),
            score.overall_score,
        )

        return OptimizationResult(
            score=score,
            issues=issues,
            recommendations=recommendations,
        )

    def analyze_pipeline_result(self, pipeline_result: Any) -> OptimizationResult:
        """
        PipelineResult（fps-core.pipeline）を直接分析する。

        Args:
            pipeline_result: PipelineManager.compile() の戻り値

        Returns:
            OptimizationResult
        """
        tags = [
            {
                "tag": t.tag,
                "category": t.category,
                "weight": t.weight,
                "meta": dict(t.meta),
            }
            for t in pipeline_result.tags
        ]
        return self.analyze(tags)

    def suggest_tags(self, tags: list[dict[str, Any]]) -> list[str]:
        """不足カテゴリに対するタグ候補を提案する"""
        return suggest_missing_tags(tags, dictionary_manager=self._dictionary_manager)

    def __repr__(self) -> str:
        return f"OptimizerManager(has_dictionary={self._dictionary_manager is not None})"
