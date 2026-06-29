"""
fps-core/rules/engine.py — Rule Engine

ルールをタグリストに適用して変換結果を返す。

入力:
  タグリスト: [{"tag": "masterpiece", "category": "quality", "weight": 1.2}, ...]

出力:
  変換後タグリスト + ApplyResult リスト
"""

from __future__ import annotations

import logging
from typing import Any

from .evaluator import evaluate
from .models import ActionType, ApplyResult, Rule

logger = logging.getLogger(__name__)

# タグエントリの型エイリアス
TagEntry = dict[str, Any]  # {"tag": str, "category": str, "weight": float}


def apply_rules(
    tags: list[TagEntry],
    rules: list[Rule],
) -> tuple[list[TagEntry], list[ApplyResult]]:
    """
    ルールリストをタグリストに適用する。

    Args:
        tags:  変換対象タグリスト
        rules: 適用するルールリスト（priority 降順でソートして適用）

    Returns:
        (変換後タグリスト, ApplyResult リスト)
    """
    # priority 降順でソート
    sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)

    result_tags = [dict(t) for t in tags]  # ディープコピー
    results: list[ApplyResult] = []

    for rule in sorted_rules:
        if not rule.enabled:
            continue
        result_tags, rule_results = _apply_one(result_tags, rule)
        results.extend(rule_results)

    return result_tags, results


def _apply_one(
    tags: list[TagEntry],
    rule: Rule,
) -> tuple[list[TagEntry], list[ApplyResult]]:
    """ルール 1件を適用する"""
    results: list[ApplyResult] = []
    new_tags = list(tags)

    action = rule.action.type

    if action == ActionType.WEIGHT:
        new_tags, rs = _apply_weight(new_tags, rule)
        results.extend(rs)

    elif action == ActionType.REMOVE:
        new_tags, rs = _apply_remove(new_tags, rule)
        results.extend(rs)

    elif action == ActionType.ADD:
        new_tags, rs = _apply_add(new_tags, rule)
        results.extend(rs)

    elif action == ActionType.KEEP_CATEGORY:
        new_tags, rs = _apply_keep_category(new_tags, rule)
        results.extend(rs)

    elif action == ActionType.REPLACE:
        new_tags, rs = _apply_replace(new_tags, rule)
        results.extend(rs)

    return new_tags, results


# ── Action 実装 ───────────────────────────────────────────────────────


def _apply_weight(tags: list[TagEntry], rule: Rule) -> tuple[list[TagEntry], list[ApplyResult]]:
    """WEIGHT: 条件に一致するタグの重みを変更する"""
    results: list[ApplyResult] = []
    new_weight = float(rule.action.value)

    for t in tags:
        if evaluate(rule, t["tag"], t.get("category", ""), t.get("weight", 1.0)):
            old = t["weight"]
            t["weight"] = new_weight
            results.append(
                ApplyResult(
                    rule_id=rule.id,
                    action=ActionType.WEIGHT,
                    target_tag=t["tag"],
                    applied=True,
                    detail=f"weight {old} → {new_weight}",
                )
            )
            logger.debug("Rule %s: WEIGHT %s %s→%s", rule.id, t["tag"], old, new_weight)

    return tags, results


def _apply_remove(tags: list[TagEntry], rule: Rule) -> tuple[list[TagEntry], list[ApplyResult]]:
    """REMOVE: 条件に一致するタグを削除する"""
    results: list[ApplyResult] = []
    kept: list[TagEntry] = []

    for t in tags:
        if evaluate(rule, t["tag"], t.get("category", ""), t.get("weight", 1.0)):
            results.append(
                ApplyResult(
                    rule_id=rule.id,
                    action=ActionType.REMOVE,
                    target_tag=t["tag"],
                    applied=True,
                    detail=f"removed '{t['tag']}'",
                )
            )
            logger.debug("Rule %s: REMOVE %s", rule.id, t["tag"])
        else:
            kept.append(t)

    return kept, results


def _apply_add(tags: list[TagEntry], rule: Rule) -> tuple[list[TagEntry], list[ApplyResult]]:
    """ADD: 条件に一致するタグがあれば新しいタグを追加する"""
    results: list[ApplyResult] = []
    triggered = any(
        evaluate(rule, t["tag"], t.get("category", ""), t.get("weight", 1.0)) for t in tags
    )

    if not triggered:
        return tags, results

    new_tag = str(rule.action.value).strip().lower().replace(" ", "_")
    # 既に存在する場合はスキップ
    if any(t["tag"] == new_tag for t in tags):
        return tags, results

    tags.append({"tag": new_tag, "category": "auto", "weight": 1.0})
    results.append(
        ApplyResult(
            rule_id=rule.id,
            action=ActionType.ADD,
            target_tag=new_tag,
            applied=True,
            detail=f"added '{new_tag}'",
        )
    )
    logger.debug("Rule %s: ADD %s", rule.id, new_tag)
    return tags, results


def _apply_keep_category(
    tags: list[TagEntry], rule: Rule
) -> tuple[list[TagEntry], list[ApplyResult]]:
    """KEEP_CATEGORY: 指定カテゴリのタグのみ残す（他は削除）"""
    keep_cat = str(rule.action.value).strip().lower()
    results: list[ApplyResult] = []
    kept: list[TagEntry] = []

    for t in tags:
        if t.get("category", "") == keep_cat:
            kept.append(t)
        else:
            results.append(
                ApplyResult(
                    rule_id=rule.id,
                    action=ActionType.KEEP_CATEGORY,
                    target_tag=t["tag"],
                    applied=True,
                    detail=f"removed (not in category '{keep_cat}')",
                )
            )

    return kept, results


def _apply_replace(tags: list[TagEntry], rule: Rule) -> tuple[list[TagEntry], list[ApplyResult]]:
    """REPLACE: 条件に一致するタグを別のタグに置き換える"""
    results: list[ApplyResult] = []
    new_tag = str(rule.action.value).strip().lower().replace(" ", "_")

    for t in tags:
        if evaluate(rule, t["tag"], t.get("category", ""), t.get("weight", 1.0)):
            old_tag = t["tag"]
            t["tag"] = new_tag
            results.append(
                ApplyResult(
                    rule_id=rule.id,
                    action=ActionType.REPLACE,
                    target_tag=new_tag,
                    applied=True,
                    detail=f"replaced '{old_tag}' → '{new_tag}'",
                )
            )
            logger.debug("Rule %s: REPLACE %s → %s", rule.id, old_tag, new_tag)

    return tags, results
