"""
fps-core/rules/manager.py — RuleManager

Public API:
  - load()        ルールファイルを読み込む
  - reload()      再読み込み
  - apply()       タグリストにルールを適用する
  - rules()       ルール一覧
  - validate()    バリデーション
  - add_rule()    ルールを動的追加
  - disable()     ルールを無効化
  - enable()      ルールを有効化
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from .engine import TagEntry, apply_rules
from .loader import load_rule_dir, load_rule_file
from .models import ApplyResult, Rule, RuleFile

logger = logging.getLogger(__name__)


class RuleManager:
    """
    FPS ルール管理クラス。

    使い方:
        rm = RuleManager(rule_dir="fps-data/rules")
        rm.load()
        tags = [
            {"tag": "masterpiece", "category": "quality", "weight": 1.2},
            {"tag": "blue_eyes",   "category": "eyes",    "weight": 1.0},
        ]
        result_tags, results = rm.apply(tags)
    """

    def __init__(self, rule_dir: str | Path | None = None) -> None:
        self._rule_dir: Path | None = Path(rule_dir) if rule_dir else None
        self._rule_files: list[RuleFile] = []
        self._extra_rules: list[Rule] = []  # 動的追加ルール
        self._lock = threading.RLock()
        self._loaded = False

    # ══════════════════════════════════════════════════════════════
    # Load / Reload
    # ══════════════════════════════════════════════════════════════

    def load(self) -> RuleManager:
        """ルールディレクトリからファイルを読み込む"""
        with self._lock:
            if self._rule_dir:
                self._rule_files = load_rule_dir(self._rule_dir)
            else:
                self._rule_files = []
            self._loaded = True
            total = sum(len(f.rules) for f in self._rule_files)
            logger.info(
                "RuleManager loaded: files=%d rules=%d extra=%d",
                len(self._rule_files),
                total,
                len(self._extra_rules),
            )
        return self

    def load_file(self, path: str | Path) -> RuleManager:
        """単一ルールファイルを追加読み込みする"""
        with self._lock:
            rf = load_rule_file(Path(path))
            self._rule_files.append(rf)
            logger.info("RuleManager: loaded file %s (%d rules)", path, len(rf.rules))
        return self

    def reload(self) -> None:
        """ルールを再読み込みする"""
        with self._lock:
            self.load()
            logger.info("RuleManager reloaded.")

    # ══════════════════════════════════════════════════════════════
    # Apply
    # ══════════════════════════════════════════════════════════════

    def apply(
        self,
        tags: list[TagEntry],
    ) -> tuple[list[TagEntry], list[ApplyResult]]:
        """
        全ルールをタグリストに適用する。

        Args:
            tags: [{"tag": str, "category": str, "weight": float}, ...]

        Returns:
            (変換後タグリスト, ApplyResult リスト)
        """
        with self._lock:
            all_rules = self._all_rules()

        return apply_rules(tags, all_rules)

    # ══════════════════════════════════════════════════════════════
    # Rule Management
    # ══════════════════════════════════════════════════════════════

    def rules(self) -> list[Rule]:
        """全ルール一覧を返す（priority 降順）"""
        with self._lock:
            return sorted(self._all_rules(), key=lambda r: r.priority, reverse=True)

    def add_rule(self, rule: Rule) -> None:
        """ルールを動的追加する（ファイルは更新しない）"""
        with self._lock:
            self._extra_rules.append(rule)
            logger.debug("RuleManager: added rule %s", rule.id)

    def remove_rule(self, rule_id: str) -> bool:
        """動的追加したルールを削除する"""
        with self._lock:
            before = len(self._extra_rules)
            self._extra_rules = [r for r in self._extra_rules if r.id != rule_id]
            removed = len(self._extra_rules) < before
            if removed:
                logger.debug("RuleManager: removed rule %s", rule_id)
            return removed

    def enable(self, rule_id: str) -> bool:
        """ルールを有効化する"""
        return self._set_enabled(rule_id, True)

    def disable(self, rule_id: str) -> bool:
        """ルールを無効化する"""
        return self._set_enabled(rule_id, False)

    def get_rule(self, rule_id: str) -> Rule | None:
        """ID でルールを取得する"""
        with self._lock:
            for r in self._all_rules():
                if r.id == rule_id:
                    return r
        return None

    # ══════════════════════════════════════════════════════════════
    # Validate
    # ══════════════════════════════════════════════════════════════

    def validate(self) -> list[str]:
        """全ルールをバリデーションしてエラーリストを返す"""
        errors: list[str] = []
        with self._lock:
            seen_ids: set[str] = set()
            for rule in self._all_rules():
                if not rule.id:
                    errors.append("id が空のルールがあります")
                if rule.id in seen_ids:
                    errors.append(f"ルール id '{rule.id}' が重複しています")
                seen_ids.add(rule.id)

                if rule.action.type.value not in (
                    "ADD",
                    "REMOVE",
                    "WEIGHT",
                    "KEEP_CATEGORY",
                    "REPLACE",
                ):
                    errors.append(f"rule '{rule.id}': 不正な action type")

                if rule.action.type.value == "WEIGHT":
                    try:
                        v = float(rule.action.value)
                        if not (0.0 < v <= 3.0):
                            errors.append(f"rule '{rule.id}': WEIGHT value {v} は 0〜3.0 の範囲外")
                    except (TypeError, ValueError):
                        errors.append(f"rule '{rule.id}': WEIGHT value が数値ではありません")

        return errors

    # ══════════════════════════════════════════════════════════════
    # Statistics
    # ══════════════════════════════════════════════════════════════

    def statistics(self) -> dict[str, Any]:
        """ルールの統計情報を返す"""
        with self._lock:
            all_rules = self._all_rules()
            by_action: dict[str, int] = {}
            for r in all_rules:
                k = r.action.type.value
                by_action[k] = by_action.get(k, 0) + 1
            return {
                "total_rules": len(all_rules),
                "enabled_rules": sum(1 for r in all_rules if r.enabled),
                "disabled_rules": sum(1 for r in all_rules if not r.enabled),
                "by_action": by_action,
                "rule_files": len(self._rule_files),
                "extra_rules": len(self._extra_rules),
            }

    # ══════════════════════════════════════════════════════════════
    # Private
    # ══════════════════════════════════════════════════════════════

    def _all_rules(self) -> list[Rule]:
        """全ルール（ファイル由来 + 動的追加）を返す"""
        rules: list[Rule] = []
        for rf in self._rule_files:
            rules.extend(rf.rules)
        rules.extend(self._extra_rules)
        return rules

    def _set_enabled(self, rule_id: str, enabled: bool) -> bool:
        with self._lock:
            for rule in self._all_rules():
                if rule.id == rule_id:
                    object.__setattr__(rule, "enabled", enabled)
                    return True
        return False

    def __repr__(self) -> str:
        return (
            f"RuleManager("
            f"rule_dir={self._rule_dir}, "
            f"rules={len(self._all_rules())}, "
            f"loaded={self._loaded})"
        )
