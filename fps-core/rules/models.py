"""
fps-core/rules/models.py — Rule データモデル
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    WEIGHT = "WEIGHT"
    KEEP_CATEGORY = "KEEP_CATEGORY"
    REPLACE = "REPLACE"


class ConditionOp(StrEnum):
    TAG = "tag"  # タグ名が一致
    CATEGORY = "category"  # カテゴリが一致
    WEIGHT_LT = "weight_lt"  # 重み < value
    WEIGHT_GT = "weight_gt"  # 重み > value
    ALIAS = "alias"  # エイリアスが一致


@dataclass(slots=True)
class RuleCondition:
    """ルール適用条件（複数条件は AND で評価）"""

    op: ConditionOp
    value: str | float


@dataclass(slots=True)
class RuleAction:
    """ルールアクション"""

    type: ActionType
    value: Any = None  # ADD: タグ名 / WEIGHT: float / REPLACE: str


@dataclass(slots=True)
class Rule:
    """ルール 1件"""

    id: str
    action: RuleAction
    conditions: list[RuleCondition] = field(default_factory=list)
    description: str = ""
    priority: int = 0  # 高いほど先に適用
    enabled: bool = True


@dataclass(slots=True)
class RuleFile:
    """ルールファイル 1つ分"""

    version: str
    rules: list[Rule] = field(default_factory=list)
    description: str = ""

    @property
    def enabled_rules(self) -> list[Rule]:
        return [r for r in self.rules if r.enabled]


@dataclass(slots=True)
class ApplyResult:
    """ルール適用結果 1件"""

    rule_id: str
    action: ActionType
    target_tag: str
    applied: bool
    detail: str = ""
