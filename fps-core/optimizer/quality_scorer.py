"""
fps-core/optimizer/quality_scorer.py — Quality Scorer

プロンプトの品質を0〜100でスコアリングする。

スコア構成:
  - coverage_score   : 重要カテゴリ（quality/eyes/hair等）の網羅度
  - balance_score    : タグ間の重みバランス（極端な偏りがないか）
  - redundancy_score : 非冗長性（100 = 重複なし）
  - overall_score    : 上記の加重平均
"""

from __future__ import annotations

import statistics
from typing import Any

from .conflict_detector import detect_conflicts
from .models import OptimizationIssue, QualityScore

# 顔プロンプトとして重要視するカテゴリ（網羅度評価の基準）
IMPORTANT_CATEGORIES = [
    "quality",
    "eyes",
    "hair",
    "face_shape",
    "expression",
    "skin",
]

# スコア合成の重み
WEIGHTS = {
    "coverage": 0.35,
    "balance": 0.30,
    "redundancy": 0.35,
}


def calculate_coverage_score(tags: list[dict[str, Any]]) -> float:
    """
    重要カテゴリの網羅度をスコア化する（0-100）。
    IMPORTANT_CATEGORIES のうち何割がプロンプトに含まれているか。
    """
    present_categories = {t.get("category", "") for t in tags}
    covered = sum(1 for c in IMPORTANT_CATEGORIES if c in present_categories)
    if not IMPORTANT_CATEGORIES:
        return 100.0
    return round((covered / len(IMPORTANT_CATEGORIES)) * 100, 2)


def calculate_balance_score(tags: list[dict[str, Any]]) -> float:
    """
    重みの分散をスコア化する（0-100）。
    分散が小さい（重みが均等に近い）ほど高スコア。
    極端に1タグだけ重い・他が軽いケースを減点する。
    """
    weights = [t.get("weight", 1.0) for t in tags]
    if len(weights) < 2:
        return 100.0  # タグが0-1個なら判定不能、満点扱い

    mean_w = statistics.mean(weights)
    if mean_w == 0:
        return 0.0

    stdev_w = statistics.stdev(weights)
    cv = stdev_w / mean_w  # 変動係数（小さいほどバランスが良い）

    # cv=0 → 100点, cv>=1.0 → 0点 の線形マッピング（負値は0でクランプ）
    score = max(0.0, 100.0 - cv * 100.0)
    return round(score, 2)


def calculate_redundancy_score(issues: list[OptimizationIssue]) -> float:
    """
    冗長性・矛盾の検出結果からスコアを算出する（0-100、100=問題なし）。
    ERROR: -30点, WARNING: -15点, INFO: -5点 を100点から減算。
    """
    score = 100.0
    for issue in issues:
        if issue.severity.value == "error":
            score -= 30
        elif issue.severity.value == "warning":
            score -= 15
        else:
            score -= 5
    return round(max(0.0, score), 2)


def calculate_quality_score(
    tags: list[dict[str, Any]],
    issues: list[OptimizationIssue] | None = None,
) -> QualityScore:
    """
    タグリストから総合品質スコアを算出する。

    Args:
        tags:   [{"tag": str, "category": str, "weight": float}, ...]
        issues: 事前計算済みの問題リスト（省略時は内部で矛盾検出のみ実行）

    Returns:
        QualityScore
    """
    if issues is None:
        issues = detect_conflicts(tags)

    coverage = calculate_coverage_score(tags)
    balance = calculate_balance_score(tags)
    redundancy = calculate_redundancy_score(issues)

    overall = round(
        coverage * WEIGHTS["coverage"]
        + balance * WEIGHTS["balance"]
        + redundancy * WEIGHTS["redundancy"],
        2,
    )

    return QualityScore(
        coverage_score=coverage,
        balance_score=balance,
        redundancy_score=redundancy,
        overall_score=overall,
    )
