"""
fps-core/history/models.py — History データモデル
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class HistoryEntry:
    """プロンプト変換履歴 1件"""

    id: str  # エントリID（タイムスタンプベース）
    input_prompt: str
    output_prompt: str
    output_negative: str = ""
    tag_count: int = 0
    overall_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    label: str = ""  # ユーザー任意のラベル（お気に入り名など）
    favorite: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def created_at_str(self) -> str:
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "input_prompt": self.input_prompt,
            "output_prompt": self.output_prompt,
            "output_negative": self.output_negative,
            "tag_count": self.tag_count,
            "overall_score": self.overall_score,
            "created_at": self.created_at.isoformat(),
            "label": self.label,
            "favorite": self.favorite,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryEntry:
        created_at = data.get("created_at")
        dt = datetime.fromisoformat(created_at) if created_at else datetime.now()
        return cls(
            id=data["id"],
            input_prompt=data.get("input_prompt", ""),
            output_prompt=data.get("output_prompt", ""),
            output_negative=data.get("output_negative", ""),
            tag_count=data.get("tag_count", 0),
            overall_score=data.get("overall_score", 0.0),
            created_at=dt,
            label=data.get("label", ""),
            favorite=data.get("favorite", False),
            meta=data.get("meta", {}),
        )


@dataclass(slots=True)
class DiffEntry:
    """2つの履歴エントリ間の差分"""

    added_tags: list[str] = field(default_factory=list)
    removed_tags: list[str] = field(default_factory=list)
    unchanged_tags: list[str] = field(default_factory=list)
    score_delta: float = 0.0

    @property
    def has_changes(self) -> bool:
        return bool(self.added_tags or self.removed_tags)
