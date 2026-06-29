"""
fps-core/rules/loader.py — Rule Loader

JSON / YAML ルールファイルを RuleFile オブジェクトに変換する。

ファイル形式（JSON）:
{
  "version": "1.0",
  "description": "基本ルールセット",
  "rules": [
    {
      "id": "rule_001",
      "description": "masterpiece の重みを強化",
      "priority": 10,
      "enabled": true,
      "conditions": [
        {"op": "tag", "value": "masterpiece"}
      ],
      "action": {"type": "WEIGHT", "value": 1.5}
    }
  ]
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exceptions import RuleLoadError
from .models import ActionType, ConditionOp, Rule, RuleAction, RuleCondition, RuleFile

try:
    import yaml  # noqa: F401

    _YAML_OK = True
except ImportError:
    _YAML_OK = False


def load_rule_file(path: Path) -> RuleFile:
    """
    ルールファイル（JSON / YAML）を読み込んで RuleFile を返す。

    Raises:
        RuleLoadError: ファイルが存在しない / 形式不正
    """
    if not path.exists():
        raise RuleLoadError(f"ルールファイルが見つかりません: {path}")
    raw = _read_raw(path)
    return _parse(raw, path)


def load_rule_dir(directory: Path) -> list[RuleFile]:
    """ディレクトリ内の全ルールファイルを読み込む"""
    if not directory.exists():
        return []
    files: list[RuleFile] = []
    for pattern in ("*.json", "*.yaml", "*.yml"):
        for p in sorted(directory.glob(pattern)):
            if p.name.startswith("."):
                continue
            files.append(load_rule_file(p))
    return files


# ── Private ──────────────────────────────────────────────────────────


def _read_raw(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise RuleLoadError(f"JSON パースエラー: {path}\n{e}") from e

    if suffix in (".yaml", ".yml"):
        if not _YAML_OK:
            raise RuleLoadError("PyYAML がインストールされていません。pip install pyyaml")
        try:
            import yaml  # noqa: F401

            data = yaml.safe_load(text)
            return data or {}
        except Exception as e:
            raise RuleLoadError(f"YAML パースエラー: {path}\n{e}") from e

    raise RuleLoadError(f"非対応の拡張子: {path.suffix}")


def _parse(raw: dict[str, Any], path: Path) -> RuleFile:
    version = str(raw.get("version", "1.0"))
    description = str(raw.get("description", ""))
    raw_rules: list[dict[str, Any]] = raw.get("rules", [])

    if not isinstance(raw_rules, list):
        raise RuleLoadError(f"'rules' はリストである必要があります: {path}")

    rules: list[Rule] = []
    for i, item in enumerate(raw_rules):
        if not isinstance(item, dict):
            raise RuleLoadError(f"rules[{i}] が辞書型ではありません: {path}")
        if "id" not in item:
            raise RuleLoadError(f"rules[{i}] に 'id' がありません: {path}")
        if "action" not in item:
            raise RuleLoadError(f"rules[{i}] に 'action' がありません: {path}")

        # conditions パース
        conditions: list[RuleCondition] = []
        for c in item.get("conditions", []):
            try:
                op = ConditionOp(c["op"])
            except (KeyError, ValueError) as e:
                raise RuleLoadError(f"rules[{i}].conditions: 不正な op: {c}") from e
            conditions.append(RuleCondition(op=op, value=c["value"]))

        # action パース
        act = item["action"]
        try:
            action_type = ActionType(act["type"])
        except (KeyError, ValueError) as e:
            raise RuleLoadError(f"rules[{i}].action: 不正な type: {act}") from e

        action = RuleAction(type=action_type, value=act.get("value"))

        rules.append(
            Rule(
                id=str(item["id"]),
                action=action,
                conditions=conditions,
                description=str(item.get("description", "")),
                priority=int(item.get("priority", 0)),
                enabled=bool(item.get("enabled", True)),
            )
        )

    return RuleFile(version=version, rules=rules, description=description)
