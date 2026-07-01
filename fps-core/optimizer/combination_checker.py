"""
fps-core/optimizer/combination_checker.py — Combination Checker (v1.5)

スタイル一貫性チェックとトークンバジェット警告を実装する。

機能:
  1. スタイル組み合わせチェック
     - 非推奨ペア（例: photorealistic + anime）→ STYLE_CONFLICT
     - 推奨ペアへのボーナス
  2. トークンバジェット警告
     - SD の CLIP トークン上限（デフォルト75）に対して
       使用率が閾値を超えたら TOKEN_BUDGET 警告
     - 削除候補タグを suggestion に含める

ルール定義:
  fps-data/rules/style_combinations.json からロードする。
  ファイルがなければ組み込みデフォルトにフォールバック。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .models import IssueSeverity, IssueType, OptimizationIssue

logger = logging.getLogger(__name__)

# デフォルトルールファイルのパス
_DEFAULT_RULES_PATH = (
    Path(__file__).parents[2] / "fps-data" / "rules" / "style_combinations.json"
)

# ルールキャッシュ（初回ロード後はキャッシュを使用）
_rules_cache: dict | None = None


def _load_rules(rules_path: Path | None = None) -> dict:
    """スタイル組み合わせルールを JSON からロードする。"""
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache

    path = rules_path or _DEFAULT_RULES_PATH
    if path.exists():
        try:
            _rules_cache = json.loads(path.read_text(encoding="utf-8"))
            logger.debug("Combination rules loaded from %s", path)
            return _rules_cache
        except Exception as exc:
            logger.warning("Failed to load combination rules: %s", exc)

    # フォールバック: 最小限の組み込みルール
    _rules_cache = {
        "incompatible_pairs": [
            {
                "id": "photorealistic_vs_anime",
                "resolved_a": ["Style.Photorealistic"],
                "resolved_b": ["Style.Anime", "Style.Manga"],
                "severity": "warning",
                "message": "写実的スタイルとアニメスタイルが混在しています",
                "suggestion": "どちらかのスタイルに統一することを推奨します。",
            },
            {
                "id": "high_vs_low_quality",
                "resolved_a": ["Quality.High", "Quality.UltraHD"],
                "resolved_b": ["Quality.Low", "Quality.Bad"],
                "severity": "error",
                "message": "高品質指定と低品質指定が同時に存在します",
                "suggestion": "どちらか一方を除去してください。",
            },
        ],
        "recommended_pairs": [],
        "token_budget": {
            "max_tokens": 75,
            "warn_threshold": 0.8,
            "critical_threshold": 1.0,
            "avg_tokens_per_tag": 1.5,
            "priority_trim_categories": ["accessories", "clothing", "body"],
            "protected_categories": ["quality", "eyes", "hair", "expression"],
        },
    }
    return _rules_cache


def reload_rules() -> None:
    """ルールキャッシュをクリアして次回アクセス時に再ロードさせる。"""
    global _rules_cache
    _rules_cache = None


# ── 内部ヘルパー ──────────────────────────────────────────────────

def _get_resolved(tag: dict[str, Any]) -> str:
    return (
        tag.get("meta", {}).get("resolved")
        or tag.get("resolved")
        or tag.get("tag", "")
    )


def _resolved_set(tags: list[dict[str, Any]]) -> set[str]:
    return {_get_resolved(t) for t in tags}


def _severity(s: str) -> IssueSeverity:
    return {
        "error": IssueSeverity.ERROR,
        "warning": IssueSeverity.WARNING,
    }.get(s, IssueSeverity.INFO)


# ── スタイル組み合わせチェック ────────────────────────────────────

def check_style_combinations(
    tags: list[dict[str, Any]],
    rules_path: Path | None = None,
) -> tuple[list[OptimizationIssue], float]:
    """非推奨スタイル組み合わせを検出し、組み合わせスコアを返す。

    Args:
        tags:       分析対象タグリスト
        rules_path: カスタムルールファイルのパス（省略時はデフォルト）

    Returns:
        (issues, combination_score)
        - issues:            検出された STYLE_CONFLICT 問題リスト
        - combination_score: 0-100（問題なし=100、推奨ペアでボーナス付加）
    """
    rules = _load_rules(rules_path)
    resolved = _resolved_set(tags)
    issues: list[OptimizationIssue] = []
    score = 100.0

    # ── 非推奨ペアチェック ─────────────────────────────────────
    for pair in rules.get("incompatible_pairs", []):
        set_a = set(pair["resolved_a"])
        set_b = set(pair["resolved_b"])
        found_a = resolved & set_a
        found_b = resolved & set_b

        if found_a and found_b:
            sev = _severity(pair.get("severity", "warning"))
            deduction = {"error": 30.0, "warning": 15.0}.get(pair.get("severity", "warning"), 5.0)
            score -= deduction
            issues.append(
                OptimizationIssue(
                    type=IssueType.STYLE_CONFLICT,
                    severity=sev,
                    message=pair.get("message", f"スタイルの非互換: {pair['id']}"),
                    tags=sorted(found_a | found_b),
                    category=pair.get("id", "style"),
                    suggestion=pair.get("suggestion", "スタイルを統一することを推奨します。"),
                )
            )

    # ── 推奨ペアボーナス ───────────────────────────────────────
    for pair in rules.get("recommended_pairs", []):
        set_a = set(pair["resolved_a"])
        set_b = set(pair["resolved_b"])
        if resolved & set_a and resolved & set_b:
            bonus = float(pair.get("bonus", 3.0))
            score = min(100.0, score + bonus)

    return issues, round(max(0.0, score), 2)


# ── トークンバジェット計算 ────────────────────────────────────────

def estimate_token_count(tags: list[dict[str, Any]]) -> int:
    """タグリストの推定 CLIP トークン数を返す。

    推定方法:
      - resolved 値を `Category.Value` 形式で取得
      - `.` と `_` で分割して単語に分解
      - 単語数 × 係数（短い単語=0.75、長い単語=1.5）で推定
      - 最小 1 トークン/タグ

    Args:
        tags: タグリスト

    Returns:
        推定トークン数（整数）
    """
    total = 0
    for tag in tags:
        resolved = _get_resolved(tag)
        # "Eyes.Blue" → ["Eyes", "Blue"]
        words = [w for part in resolved.split(".") for w in part.split("_") if w]
        for w in words:
            # 短い単語 (≤4文字) は 0.75 トークン、長い単語は 1.5 トークン
            total += 0.75 if len(w) <= 4 else 1.5
    return max(len(tags), round(total))


def check_token_budget(
    tags: list[dict[str, Any]],
    rules_path: Path | None = None,
) -> tuple[list[OptimizationIssue], float]:
    """トークンバジェット超過を検出し、トークンスコアを返す。

    Args:
        tags:       分析対象タグリスト
        rules_path: カスタムルールファイルのパス

    Returns:
        (issues, token_score)
        - issues:       TOKEN_BUDGET 警告リスト
        - token_score:  0-100（余裕あり=100、超過=0に近づく）
    """
    rules = _load_rules(rules_path)
    budget = rules.get("token_budget", {})
    max_tokens: int = int(budget.get("max_tokens", 75))
    warn_threshold: float = float(budget.get("warn_threshold", 0.8))
    critical_threshold: float = float(budget.get("critical_threshold", 1.0))
    trim_categories: list[str] = budget.get("priority_trim_categories", [])
    protected: list[str] = budget.get("protected_categories", [])

    estimated = estimate_token_count(tags)
    usage = estimated / max_tokens if max_tokens > 0 else 0.0
    issues: list[OptimizationIssue] = []

    if usage >= warn_threshold:
        # 削除候補タグ（優先度低カテゴリ）
        trimmable = [
            t.get("tag", t.get("key", ""))
            for t in tags
            if t.get("category", "") in trim_categories
               and t.get("category", "") not in protected
        ]

        if usage >= critical_threshold:
            sev = IssueSeverity.ERROR
            msg = (
                f"推定トークン数 {estimated} が上限 {max_tokens} を超えています "
                f"（使用率 {usage:.0%}）。"
            )
        else:
            sev = IssueSeverity.WARNING
            msg = (
                f"推定トークン数 {estimated} がトークン上限 {max_tokens} の "
                f"{usage:.0%} に達しています。"
            )

        suggestion = "トークン数削減のため "
        if trimmable:
            suggestion += (
                f"優先度の低いタグを削除することを検討してください: "
                f"{', '.join(trimmable[:5])}"
                + ("..." if len(trimmable) > 5 else "")
            )
        else:
            suggestion += (
                "accessories / clothing / body カテゴリのタグを "
                "削減することを検討してください。"
            )

        issues.append(
            OptimizationIssue(
                type=IssueType.TOKEN_BUDGET,
                severity=sev,
                message=msg,
                tags=[t.get("tag", "") for t in tags][:10],
                category="token_budget",
                suggestion=suggestion,
            )
        )

    # token_score: 使用率が 0% → 100点、warn_threshold → 70点、critical → 0点
    if usage <= warn_threshold:
        token_score = 100.0 - (usage / warn_threshold) * 30.0
    else:
        token_score = max(0.0, 70.0 - ((usage - warn_threshold) / (critical_threshold - warn_threshold + 1e-9)) * 70.0)

    return issues, round(min(100.0, max(0.0, token_score)), 2)


# ── 総合スコア計算 ────────────────────────────────────────────────

def calculate_combination_score(
    tags: list[dict[str, Any]],
    rules_path: Path | None = None,
) -> float:
    """スタイル組み合わせスコアだけを返すショートカット関数。"""
    _, score = check_style_combinations(tags, rules_path)
    return score


def calculate_token_score(
    tags: list[dict[str, Any]],
    rules_path: Path | None = None,
) -> float:
    """トークンスコアだけを返すショートカット関数。"""
    _, score = check_token_budget(tags, rules_path)
    return score
