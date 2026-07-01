"""
fps-core/optimizer/quality_scorer.py — Quality Scorer

プロンプトの品質を0〜100でスコアリングする。

スコア構成（v1.5更新）:
  - coverage_score   : 重要カテゴリ（quality/eyes/hair等）の網羅度
  - balance_score    : タグ間の重みバランス（極端な偏りがないか）
  - redundancy_score : 非冗長性（100 = 重複なし）
  - combination_score: ★v1.5 スタイル組み合わせ一貫性
  - token_score      : ★v1.5 トークンバジェット余裕度
  - overall_score    : 上記の加重平均
"""

from __future__ import annotations

import statistics
from typing import Any

from .combination_checker import check_style_combinations, check_token_budget
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

# スコア合成の重み（v1.5: combination / token を追加）
WEIGHTS = {
    "coverage":    0.25,
    "balance":     0.20,
    "redundancy":  0.25,
    "combination": 0.20,   # ★v1.5
    "token":       0.10,   # ★v1.5
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
        tags:   [{\"tag\": str, \"category\": str, \"weight\": float}, ...]
        issues: 事前計算済みの問題リスト（省略時は内部で矛盾検出のみ実行）

    Returns:
        QualityScore（v1.5: combination_score / token_score を含む）
    """
    if issues is None:
        issues = detect_conflicts(tags)

    coverage = calculate_coverage_score(tags)
    balance = calculate_balance_score(tags)
    redundancy = calculate_redundancy_score(issues)

    # ★v1.5: スタイル組み合わせスコア + トークンスコア
    _, combination = check_style_combinations(tags)
    _, token = check_token_budget(tags)

    overall = round(
        coverage    * WEIGHTS["coverage"]
        + balance   * WEIGHTS["balance"]
        + redundancy * WEIGHTS["redundancy"]
        + combination * WEIGHTS["combination"]
        + token     * WEIGHTS["token"],
        2,
    )

    return QualityScore(
        coverage_score=coverage,
        balance_score=balance,
        redundancy_score=redundancy,
        overall_score=overall,
        combination_score=combination,
        token_score=token,
    )


# ── M6-1 ネガティブプロンプト品質評価 ────────────────────────────

# ネガティブプロンプトとして推奨されるカテゴリ（代表タグの resolved prefix）
RECOMMENDED_NEGATIVE_PREFIXES: list[str] = [
    "Quality.Low",
    "Quality.Bad",
    "Body.BadHands",
    "Body.BadAnatomy",
    "Style.Blur",
    "Style.Watermark",
]


def calculate_negative_coverage_score(negative_tags: list[dict]) -> float:
    """ネガティブプロンプトの網羅度をスコア化する（0-100）。"""
    if not negative_tags:
        return 0.0

    neg_resolved = {
        t.get("meta", {}).get("resolved") or t.get("resolved") or t.get("tag", "")
        for t in negative_tags
    }

    covered_prefixes = set()
    for prefix in RECOMMENDED_NEGATIVE_PREFIXES:
        if any(r.startswith(prefix.split(".")[0]) for r in neg_resolved):
            covered_prefixes.add(prefix)

    return round(len(covered_prefixes) / len(RECOMMENDED_NEGATIVE_PREFIXES) * 100, 2)
