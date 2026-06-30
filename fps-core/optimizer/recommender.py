"""
fps-core/optimizer/recommender.py — Recommendation Engine

検出された問題・スコアから自然言語の改善提案を生成する。
"""

from __future__ import annotations

from typing import Any

from .models import IssueType, OptimizationIssue, QualityScore
from .quality_scorer import IMPORTANT_CATEGORIES


def generate_recommendations(
    tags: list[dict[str, Any]],
    issues: list[OptimizationIssue],
    score: QualityScore,
) -> list[str]:
    """
    問題リストとスコアから改善提案の文字列リストを生成する。

    Args:
        tags:   現在のタグリスト
        issues: 検出された問題
        score:  品質スコア

    Returns:
        改善提案メッセージのリスト
    """
    recommendations: list[str] = []

    # ── カバレッジ不足の指摘 ─────────────────────────────
    present_categories = {t.get("category", "") for t in tags}
    missing = [c for c in IMPORTANT_CATEGORIES if c not in present_categories]
    if missing:
        recommendations.append(
            f"次のカテゴリが指定されていません: {', '.join(missing)}。"
            f"追加するとプロンプトの表現力が向上します。"
        )

    # ── 矛盾の指摘 ───────────────────────────────────────
    conflicts = [i for i in issues if i.type == IssueType.CONFLICT]
    for c in conflicts:
        recommendations.append(f"矛盾: {c.message} {c.suggestion}")

    # ── 冗長性の指摘 ─────────────────────────────────────
    redundancies = [i for i in issues if i.type == IssueType.REDUNDANT]
    for r in redundancies:
        recommendations.append(f"冗長: {r.message} {r.suggestion}")

    # ── 重みバランスの指摘 ───────────────────────────────
    if score.balance_score < 50:
        recommendations.append(
            "タグ間の重みに大きな偏りがあります。"
            "極端に高い/低い重みのタグを見直すとバランスが改善します。"
        )

    # ── 総合評価コメント ─────────────────────────────────
    if score.overall_score >= 85:
        recommendations.append("総合スコアは良好です。大きな改善点はありません。")
    elif score.overall_score >= 60:
        recommendations.append("総合スコアは標準的です。上記の指摘を確認してください。")
    else:
        recommendations.append(
            "総合スコアが低めです。カバレッジ・矛盾・冗長性の問題を優先的に解消してください。"
        )

    return recommendations


def suggest_missing_tags(
    tags: list[dict[str, Any]],
    dictionary_manager: Any = None,
) -> list[str]:
    """
    不足している重要カテゴリに対して、辞書から代表的なタグ候補を提案する。

    Args:
        tags:               現在のタグリスト
        dictionary_manager: DictionaryManager（省略時は固定候補を返す）

    Returns:
        提案タグのリスト（カテゴリごとに1つ）
    """
    present_categories = {t.get("category", "") for t in tags}
    missing = [c for c in IMPORTANT_CATEGORIES if c not in present_categories]

    # フォールバック候補（辞書なしでも動作するように）
    fallback_candidates = {
        "quality": "masterpiece",
        "eyes": "blue_eyes",
        "hair": "long_hair",
        "face_shape": "oval_face",
        "expression": "smile",
        "skin": "smooth_skin",
    }

    suggestions: list[str] = []
    for cat in missing:
        if dictionary_manager:
            try:
                stats = dictionary_manager.statistics()
                by_cat = stats.get("by_category", {})
                if by_cat.get(cat, 0) > 0:
                    suggestions.append(fallback_candidates.get(cat, cat))
                    continue
            except Exception:
                pass
        if cat in fallback_candidates:
            suggestions.append(fallback_candidates[cat])

    return suggestions
