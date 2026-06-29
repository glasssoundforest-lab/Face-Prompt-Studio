"""
fps-tools/tests/unit/test_rule_manager.py

RuleManager のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_rule_manager.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))

from rules.engine import apply_rules
from rules.evaluator import evaluate, _eval_condition
from rules.exceptions import RuleLoadError, RuleValidationError
from rules.loader import load_rule_file, load_rule_dir
from rules.manager import RuleManager
from rules.models import (
    ActionType,
    ApplyResult,
    ConditionOp,
    Rule,
    RuleAction,
    RuleCondition,
    RuleFile,
)


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

RULE_DATA = {
    "version": "1.0",
    "description": "テストルール",
    "rules": [
        {
            "id": "r_weight",
            "description": "masterpiece 重み強化",
            "priority": 10,
            "enabled": True,
            "conditions": [{"op": "tag", "value": "masterpiece"}],
            "action": {"type": "WEIGHT", "value": 1.5},
        },
        {
            "id": "r_remove",
            "description": "低品質タグ削除",
            "priority": 8,
            "enabled": True,
            "conditions": [
                {"op": "category", "value": "quality"},
                {"op": "weight_lt", "value": 0.9},
            ],
            "action": {"type": "REMOVE"},
        },
        {
            "id": "r_add",
            "description": "masterpiece があれば high_quality を追加",
            "priority": 5,
            "enabled": True,
            "conditions": [{"op": "tag", "value": "masterpiece"}],
            "action": {"type": "ADD", "value": "high_quality"},
        },
        {
            "id": "r_disabled",
            "description": "無効ルール",
            "priority": 1,
            "enabled": False,
            "conditions": [],
            "action": {"type": "REMOVE"},
        },
    ],
}

TAGS = [
    {"tag": "masterpiece", "category": "quality", "weight": 1.2},
    {"tag": "blue_eyes",   "category": "eyes",    "weight": 1.0},
    {"tag": "low_quality", "category": "quality", "weight": 0.8},
]


def make_rule(
    id_: str = "r_test",
    action_type: ActionType = ActionType.WEIGHT,
    action_value: object = 1.5,
    conditions: list[RuleCondition] | None = None,
    priority: int = 0,
    enabled: bool = True,
) -> Rule:
    return Rule(
        id=id_,
        action=RuleAction(type=action_type, value=action_value),
        conditions=conditions or [],
        priority=priority,
        enabled=enabled,
    )


@pytest.fixture
def rule_file_path(tmp_path: Path) -> Path:
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(RULE_DATA), encoding="utf-8")
    return p


@pytest.fixture
def rule_dir(tmp_path: Path) -> Path:
    d = tmp_path / "rules"
    d.mkdir()
    (d / "base.json").write_text(json.dumps(RULE_DATA), encoding="utf-8")
    return d


@pytest.fixture
def rm(rule_dir: Path) -> RuleManager:
    manager = RuleManager(rule_dir=rule_dir)
    manager.load()
    return manager


# ══════════════════════════════════════════════════════════════════
# models
# ══════════════════════════════════════════════════════════════════

class TestModels:
    def test_rule_file_enabled_rules(self):
        r1 = make_rule("r1", enabled=True)
        r2 = make_rule("r2", enabled=False)
        rf = RuleFile(version="1.0", rules=[r1, r2])
        assert len(rf.enabled_rules) == 1
        assert rf.enabled_rules[0].id == "r1"

    def test_apply_result_fields(self):
        ar = ApplyResult(
            rule_id="r1",
            action=ActionType.WEIGHT,
            target_tag="masterpiece",
            applied=True,
            detail="weight 1.0 → 1.5",
        )
        assert ar.applied is True
        assert ar.action == ActionType.WEIGHT


# ══════════════════════════════════════════════════════════════════
# evaluator
# ══════════════════════════════════════════════════════════════════

class TestEvaluator:
    def _rule(self, *conditions: RuleCondition) -> Rule:
        return make_rule(conditions=list(conditions))

    def test_no_conditions_always_true(self):
        rule = make_rule(conditions=[])
        assert evaluate(rule, "anything", "any", 1.0) is True

    def test_tag_condition_match(self):
        cond = RuleCondition(op=ConditionOp.TAG, value="masterpiece")
        rule = self._rule(cond)
        assert evaluate(rule, "masterpiece", "quality", 1.0) is True

    def test_tag_condition_no_match(self):
        cond = RuleCondition(op=ConditionOp.TAG, value="masterpiece")
        rule = self._rule(cond)
        assert evaluate(rule, "blue_eyes", "eyes", 1.0) is False

    def test_category_condition(self):
        cond = RuleCondition(op=ConditionOp.CATEGORY, value="quality")
        rule = self._rule(cond)
        assert evaluate(rule, "masterpiece", "quality", 1.0) is True
        assert evaluate(rule, "blue_eyes",   "eyes",    1.0) is False

    def test_weight_lt_condition(self):
        cond = RuleCondition(op=ConditionOp.WEIGHT_LT, value=1.0)
        rule = self._rule(cond)
        assert evaluate(rule, "tag", "cat", 0.8) is True
        assert evaluate(rule, "tag", "cat", 1.0) is False
        assert evaluate(rule, "tag", "cat", 1.2) is False

    def test_weight_gt_condition(self):
        cond = RuleCondition(op=ConditionOp.WEIGHT_GT, value=1.0)
        rule = self._rule(cond)
        assert evaluate(rule, "tag", "cat", 1.2) is True
        assert evaluate(rule, "tag", "cat", 1.0) is False

    def test_and_conditions_all_must_match(self):
        rule = self._rule(
            RuleCondition(op=ConditionOp.CATEGORY, value="quality"),
            RuleCondition(op=ConditionOp.WEIGHT_LT, value=0.9),
        )
        assert evaluate(rule, "low_quality", "quality", 0.8) is True
        assert evaluate(rule, "masterpiece", "quality", 1.2) is False
        assert evaluate(rule, "low_quality", "eyes",    0.8) is False

    def test_tag_normalization(self):
        cond = RuleCondition(op=ConditionOp.TAG, value="Blue Eyes")
        rule = self._rule(cond)
        assert evaluate(rule, "blue_eyes", "eyes", 1.0) is True


# ══════════════════════════════════════════════════════════════════
# engine
# ══════════════════════════════════════════════════════════════════

class TestEngine:
    def test_weight_action(self):
        rule = make_rule(
            action_type=ActionType.WEIGHT,
            action_value=1.5,
            conditions=[RuleCondition(op=ConditionOp.TAG, value="masterpiece")],
        )
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.2}]
        result, results = apply_rules(tags, [rule])
        assert result[0]["weight"] == 1.5
        assert results[0].applied is True

    def test_remove_action(self):
        rule = make_rule(
            action_type=ActionType.REMOVE,
            conditions=[
                RuleCondition(op=ConditionOp.CATEGORY, value="quality"),
                RuleCondition(op=ConditionOp.WEIGHT_LT, value=0.9),
            ],
        )
        tags = [
            {"tag": "masterpiece", "category": "quality", "weight": 1.2},
            {"tag": "low_quality", "category": "quality", "weight": 0.8},
        ]
        result, results = apply_rules(tags, [rule])
        assert len(result) == 1
        assert result[0]["tag"] == "masterpiece"
        assert results[0].action == ActionType.REMOVE

    def test_add_action(self):
        rule = make_rule(
            action_type=ActionType.ADD,
            action_value="high_quality",
            conditions=[RuleCondition(op=ConditionOp.TAG, value="masterpiece")],
        )
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result, results = apply_rules(tags, [rule])
        tags_names = [t["tag"] for t in result]
        assert "high_quality" in tags_names
        assert results[0].action == ActionType.ADD

    def test_add_no_duplicate(self):
        rule = make_rule(
            action_type=ActionType.ADD,
            action_value="masterpiece",
            conditions=[RuleCondition(op=ConditionOp.TAG, value="masterpiece")],
        )
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result, _ = apply_rules(tags, [rule])
        assert sum(1 for t in result if t["tag"] == "masterpiece") == 1

    def test_replace_action(self):
        rule = make_rule(
            action_type=ActionType.REPLACE,
            action_value="quality_high",
            conditions=[RuleCondition(op=ConditionOp.TAG, value="masterpiece")],
        )
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result, results = apply_rules(tags, [rule])
        assert result[0]["tag"] == "quality_high"
        assert results[0].action == ActionType.REPLACE

    def test_keep_category_action(self):
        rule = make_rule(
            action_type=ActionType.KEEP_CATEGORY,
            action_value="quality",
        )
        tags = [
            {"tag": "masterpiece", "category": "quality", "weight": 1.0},
            {"tag": "blue_eyes",   "category": "eyes",    "weight": 1.0},
        ]
        result, results = apply_rules(tags, [rule])
        assert len(result) == 1
        assert result[0]["tag"] == "masterpiece"

    def test_priority_order(self):
        """priority が高いルールが先に適用される"""
        r_low = make_rule("r_low",  ActionType.WEIGHT, 0.5, priority=1,
                          conditions=[RuleCondition(op=ConditionOp.TAG, value="masterpiece")])
        r_high = make_rule("r_high", ActionType.WEIGHT, 2.0, priority=10,
                           conditions=[RuleCondition(op=ConditionOp.TAG, value="masterpiece")])
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result, _ = apply_rules(tags, [r_low, r_high])
        # priority=10 が先に 2.0 にセット → priority=1 が 0.5 に上書き
        assert result[0]["weight"] == 0.5

    def test_disabled_rule_skipped(self):
        rule = make_rule(
            action_type=ActionType.REMOVE,
            enabled=False,
        )
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result, results = apply_rules(tags, [rule])
        assert len(result) == 1   # 削除されない
        assert len(results) == 0

    def test_empty_tags(self):
        rule = make_rule(action_type=ActionType.WEIGHT, action_value=1.5)
        result, results = apply_rules([], [rule])
        assert result == []

    def test_empty_rules(self):
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result, results = apply_rules(tags, [])
        assert result == tags
        assert results == []


# ══════════════════════════════════════════════════════════════════
# loader
# ══════════════════════════════════════════════════════════════════

class TestLoader:
    def test_load_json(self, rule_file_path: Path):
        rf = load_rule_file(rule_file_path)
        assert rf.version == "1.0"
        assert len(rf.rules) == 4

    def test_load_nonexistent_raises(self, tmp_path: Path):
        with pytest.raises(RuleLoadError):
            load_rule_file(tmp_path / "ghost.json")

    def test_load_invalid_json_raises(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("{invalid}", encoding="utf-8")
        with pytest.raises(RuleLoadError):
            load_rule_file(p)

    def test_load_missing_id_raises(self, tmp_path: Path):
        data = {"version": "1.0", "rules": [{"action": {"type": "REMOVE"}}]}
        p = tmp_path / "r.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(RuleLoadError):
            load_rule_file(p)

    def test_load_dir(self, rule_dir: Path):
        files = load_rule_dir(rule_dir)
        assert len(files) == 1
        assert len(files[0].rules) == 4

    def test_load_dir_nonexistent(self, tmp_path: Path):
        files = load_rule_dir(tmp_path / "ghost")
        assert files == []

    def test_priority_parsed(self, rule_file_path: Path):
        rf = load_rule_file(rule_file_path)
        r = next(r for r in rf.rules if r.id == "r_weight")
        assert r.priority == 10

    def test_disabled_rule_parsed(self, rule_file_path: Path):
        rf = load_rule_file(rule_file_path)
        r = next(r for r in rf.rules if r.id == "r_disabled")
        assert r.enabled is False


# ══════════════════════════════════════════════════════════════════
# RuleManager
# ══════════════════════════════════════════════════════════════════

class TestRuleManager:
    def test_load_success(self, rm: RuleManager):
        stats = rm.statistics()
        assert stats["total_rules"] == 4
        assert stats["enabled_rules"] == 3

    def test_load_no_dir(self):
        manager = RuleManager()
        manager.load()
        assert manager.statistics()["total_rules"] == 0

    def test_reload_safe(self, rm: RuleManager):
        rm.reload()
        assert rm.statistics()["total_rules"] == 4

    def test_apply_weight(self, rm: RuleManager):
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result, results = rm.apply(tags)
        assert result[0]["weight"] == 1.5

    def test_apply_remove_low_quality(self, rm: RuleManager):
        tags = [
            {"tag": "masterpiece", "category": "quality", "weight": 1.2},
            {"tag": "low_quality", "category": "quality", "weight": 0.8},
        ]
        result, _ = rm.apply(tags)
        assert all(t["tag"] != "low_quality" for t in result)

    def test_apply_add(self, rm: RuleManager):
        tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        result, _ = rm.apply(tags)
        assert any(t["tag"] == "high_quality" for t in result)

    def test_add_rule_dynamic(self, rm: RuleManager):
        rule = make_rule(
            "r_dynamic",
            ActionType.WEIGHT,
            2.0,
            conditions=[RuleCondition(op=ConditionOp.TAG, value="blue_eyes")],
        )
        rm.add_rule(rule)
        tags = [{"tag": "blue_eyes", "category": "eyes", "weight": 1.0}]
        result, _ = rm.apply(tags)
        assert result[0]["weight"] == 2.0

    def test_remove_rule_dynamic(self, rm: RuleManager):
        rule = make_rule("r_temp", ActionType.WEIGHT, 2.0)
        rm.add_rule(rule)
        assert rm.get_rule("r_temp") is not None
        removed = rm.remove_rule("r_temp")
        assert removed is True
        assert rm.get_rule("r_temp") is None

    def test_disable_enable_rule(self, rm: RuleManager):
        rm.disable("r_weight")
        rule = rm.get_rule("r_weight")
        assert rule is not None
        assert rule.enabled is False

        rm.enable("r_weight")
        rule = rm.get_rule("r_weight")
        assert rule is not None
        assert rule.enabled is True

    def test_rules_sorted_by_priority(self, rm: RuleManager):
        rules = rm.rules()
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_validate_clean(self, rm: RuleManager):
        errors = rm.validate()
        assert errors == []

    def test_validate_detects_duplicate_id(self, rm: RuleManager):
        rule = make_rule("r_weight")   # 既存の id と重複
        rm.add_rule(rule)
        errors = rm.validate()
        assert any("重複" in e for e in errors)

    def test_statistics_by_action(self, rm: RuleManager):
        stats = rm.statistics()
        assert "WEIGHT" in stats["by_action"]
        assert "REMOVE" in stats["by_action"]
        assert "ADD"    in stats["by_action"]

    def test_load_file(self, rm: RuleManager, tmp_path: Path):
        extra = {
            "version": "1.0",
            "rules": [
                {"id": "r_extra", "conditions": [],
                 "action": {"type": "WEIGHT", "value": 1.0}}
            ],
        }
        p = tmp_path / "extra.json"
        p.write_text(json.dumps(extra), encoding="utf-8")
        before = rm.statistics()["total_rules"]
        rm.load_file(p)
        assert rm.statistics()["total_rules"] == before + 1

    def test_repr(self, rm: RuleManager):
        assert "RuleManager" in repr(rm)
