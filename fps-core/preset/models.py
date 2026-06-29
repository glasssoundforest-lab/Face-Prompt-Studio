"""
fps-core/preset/models.py — Preset データモデル
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PresetSource(StrEnum):
    SYSTEM = "system"
    USER = "user"


@dataclass(slots=True)
class PresetTag:
    """プリセット内のタグエントリ 1件"""

    tag: str
    category: str = ""
    weight: float = 1.0


@dataclass(slots=True)
class Preset:
    """
    プリセット 1件。

    例:
        Preset(
            id="anime_portrait",
            name="アニメポートレート",
            tags=[PresetTag("masterpiece", "quality", 1.5)],
            negative_tags=[PresetTag("bad hands", "negative")],
            source=PresetSource.SYSTEM,
        )
    """

    id: str
    name: str
    tags: list[PresetTag] = field(default_factory=list)
    negative_tags: list[PresetTag] = field(default_factory=list)
    source: PresetSource = PresetSource.SYSTEM
    description: str = ""
    version: str = "1.0"
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def tag_count(self) -> int:
        return len(self.tags)

    @property
    def negative_tag_count(self) -> int:
        return len(self.negative_tags)


@dataclass(slots=True)
class PresetFile:
    """プリセットファイル 1つ分"""

    version: str
    source: PresetSource
    presets: list[Preset] = field(default_factory=list)

    @property
    def preset_count(self) -> int:
        return len(self.presets)


@dataclass(slots=True)
class MergeResult:
    """merge() の結果"""

    preset: Preset
    merged_from: list[str]  # マージ元プリセット ID リスト
    tag_count: int
    conflicts: list[str] = field(default_factory=list)
