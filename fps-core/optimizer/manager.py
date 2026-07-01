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

from .conflict_detector import detect_conflicts, detect_cross_conflicts
from .models import OptimizationResult
from .quality_scorer import calculate_negative_coverage_score, calculate_quality_score
from .recommender import generate_recommendations, suggest_missing_tags
from .redundancy_detector import detect_negative_redundancy, detect_redundancy

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

    def analyze(
        self,
        tags: list[dict[str, Any]],
        negative_tags: list[dict[str, Any]] | None = None,
    ) -> OptimizationResult:
        """タグリストを分析して OptimizationResult を返す。

        Args:
            tags:          ポジティブプロンプトのタグリスト
            negative_tags: ★M6-1 ネガティブプロンプトのタグリスト（省略可）

        Returns:
            OptimizationResult
        """
        neg = negative_tags or []

        conflicts = detect_conflicts(tags)
        redundancies = detect_redundancy(tags)

        # M6-1: ネガティブプロンプト解析
        cross_conflicts: list = []
        neg_redundancies: list = []
        if neg:
            cross_conflicts = detect_cross_conflicts(tags, neg)
            neg_redundancies = detect_negative_redundancy(neg)

        issues = conflicts + redundancies + cross_conflicts + neg_redundancies

        score = calculate_quality_score(tags, issues=issues)

        # M6-1: ネガティブ網羅度スコアを付加
        neg_coverage = calculate_negative_coverage_score(neg)
        score.negative_coverage_score = neg_coverage

        recommendations = generate_recommendations(tags, issues, score)

        # M6-1: ネガティブプロンプト関連の推奨事項を追加
        if neg:
            if cross_conflicts:
                recommendations.append(
                    f"ポジティブ/ネガティブ間で {len(cross_conflicts)} 件の競合が検出されました。"
                    "ネガティブで打ち消したい属性をポジティブから除くことを推奨します。"
                )
            if neg_coverage < 50:
                recommendations.append(
                    "ネガティブプロンプトの網羅度が低めです。"
                    "low_quality, bad_anatomy, blurry, watermark を追加すると品質向上が期待できます。"
                )
        else:
            recommendations.append(
                "ネガティブプロンプトが未設定です。"
                "low_quality, bad_anatomy などを指定すると生成品質が向上します。"
            )

        logger.debug(
            "Optimizer analysis: %d pos-tags, %d neg-tags, %d issues, overall=%.1f",
            len(tags), len(neg), len(issues), score.overall_score,
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
