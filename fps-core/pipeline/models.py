"""
fps-core/pipeline/models.py — Pipeline データモデル
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(slots=True)
class TagEntry:
    """パイプライン内を流れるタグ 1件"""

    tag: str
    category: str = ""
    weight: float = 1.0
    negative: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "category": self.category,
            "weight": self.weight,
            "negative": self.negative,
        }


@dataclass(slots=True)
class StageResult:
    """各ステージの実行結果"""

    stage: str
    status: StageStatus
    tags_in: int = 0
    tags_out: int = 0
    detail: str = ""
    error: str = ""


@dataclass(slots=True)
class PipelineResult:
    """パイプライン全体の実行結果"""

    success: bool
    prompt: str = ""
    negative: str = ""
    tags: list[TagEntry] = field(default_factory=list)
    negative_tags: list[TagEntry] = field(default_factory=list)
    stage_results: list[StageResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def tag_count(self) -> int:
        return len(self.tags)

    @property
    def stage_count(self) -> int:
        return len(self.stage_results)
