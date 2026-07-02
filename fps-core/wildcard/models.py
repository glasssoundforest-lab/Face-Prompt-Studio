"""fps-core/wildcard/models.py — Wildcard データモデル ★v2.6"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WildcardEntry:
    """Wildcard ファイル内の 1エントリ"""
    value:    str
    weight:   float = 1.0   # ランダム選択時の重み
    tags:     list[str] = field(default_factory=list)
    comment:  str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "weight": self.weight,
                "tags": self.tags, "comment": self.comment}


@dataclass
class WildcardFile:
    """Wildcard ファイル（1つのキーに対応するリスト）"""
    name:        str          # キー名（例: "style", "character"）
    entries:     list[WildcardEntry] = field(default_factory=list)
    description: str = ""
    category:    str = ""
    created_at:  str = ""
    updated_at:  str = ""

    @property
    def values(self) -> list[str]:
        return [e.value for e in self.entries]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name":        self.name,
            "description": self.description,
            "category":    self.category,
            "entry_count": len(self.entries),
            "entries":     [e.to_dict() for e in self.entries],
            "created_at":  self.created_at,
            "updated_at":  self.updated_at,
        }
