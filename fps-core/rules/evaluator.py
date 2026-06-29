"""
fps-core/rules/evaluator.py — Rule Condition Evaluator

条件（RuleCondition）をタグエントリに対して評価する。
"""

from __future__ import annotations

from .models import ConditionOp, Rule, RuleCondition


def evaluate(rule: Rule, tag: str, category: str, weight: float) -> bool:
    """
    ルールの全条件を評価する（AND 結合）。

    Args:
        rule:     評価するルール
        tag:      対象タグ（正規化済み）
        category: タグのカテゴリ
        weight:   タグの重み

    Returns:
        全条件が True の場合 True
    """
    if not rule.conditions:
        return True  # 条件なし = 全タグに適用

    return all(_eval_condition(c, tag, category, weight) for c in rule.conditions)


def _eval_condition(
    cond: RuleCondition,
    tag: str,
    category: str,
    weight: float,
) -> bool:
    op = cond.op
    val = cond.value

    if op == ConditionOp.TAG:
        return tag == str(val).strip().lower().replace(" ", "_")

    if op == ConditionOp.CATEGORY:
        return category == str(val).strip().lower()

    if op == ConditionOp.WEIGHT_LT:
        return weight < float(val)

    if op == ConditionOp.WEIGHT_GT:
        return weight > float(val)

    if op == ConditionOp.ALIAS:
        return tag == str(val).strip().lower().replace(" ", "_")

    return False
