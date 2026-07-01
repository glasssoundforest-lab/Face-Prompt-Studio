"""
fps-core/template/models.py — Template データモデル

プロンプトテンプレートの構造を定義する。
テンプレートは {variable} 形式の変数プレースホルダを持つ。

例:
    "{quality}, {eye_color} eyes, {hair_color} {hair_length} hair, {expression}"
    → {"quality": "masterpiece", "eye_color": "blue", ...} で展開
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TemplateVariable:
    """テンプレート変数の定義"""

    name: str                  # 変数名（例: "eye_color"）
    description: str = ""      # 人間向け説明（例: "目の色"）
    default: str = ""          # デフォルト値（例: "blue_eyes"）
    examples: list[str] = field(default_factory=list)  # 入力例
    required: bool = True      # 必須かどうか


@dataclass(slots=True)
class Template:
    """プロンプトテンプレート 1件"""

    id: str                    # 一意ID（例: "face_basic"）
    name: str                  # 表示名（例: "基本顔プロンプト"）
    body: str                  # テンプレート本文（例: "{quality}, {eye_color} eyes"）
    description: str = ""      # 説明文
    variables: list[TemplateVariable] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)  # 検索用タグ
    category: str = "general"  # テンプレートカテゴリ

    @property
    def variable_names(self) -> list[str]:
        """テンプレート本文から変数名リストを抽出する"""
        import re
        return list(dict.fromkeys(re.findall(r"\{(\w+)\}", self.body)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "body": self.body,
            "description": self.description,
            "variables": [
                {
                    "name": v.name,
                    "description": v.description,
                    "default": v.default,
                    "examples": v.examples,
                    "required": v.required,
                }
                for v in self.variables
            ],
            "tags": self.tags,
            "category": self.category,
        }


@dataclass(slots=True)
class RenderResult:
    """テンプレート展開結果"""

    template_id: str
    rendered: str              # 変数置換後のプロンプト
    variables_used: dict[str, str] = field(default_factory=dict)
    missing_variables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.missing_variables) == 0
