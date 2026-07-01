"""
fps-core/user/models.py — パーソナライゼーション データモデル
★ v2.0 新設
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TagWeight:
    """ユーザーが設定したタグの重み調整"""
    tag: str
    weight: float = 1.0        # 0.0 = 除外, 1.0 = デフォルト, >1.0 = 強調
    reason: str = ""           # "frequent" | "manual" | "excluded"
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "weight": self.weight,
            "reason": self.reason,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class StyleRule:
    """ユーザー独自のスタイルルール（コンパイル時に自動適用）"""
    id: str
    name: str
    always_include: list[str] = field(default_factory=list)   # 常に追加するタグ
    always_exclude: list[str] = field(default_factory=list)   # 常に除外するタグ
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "always_include": self.always_include,
            "always_exclude": self.always_exclude,
            "enabled": self.enabled,
        }


@dataclass
class TagFrequencyEntry:
    """タグ使用頻度エントリ"""
    tag: str
    count: int = 0
    total_weight: float = 0.0
    last_used: datetime = field(default_factory=datetime.now)

    @property
    def avg_weight(self) -> float:
        return self.total_weight / self.count if self.count > 0 else 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "count": self.count,
            "avg_weight": round(self.avg_weight, 3),
            "last_used": self.last_used.isoformat(),
        }


@dataclass
class ScoreTrendEntry:
    """スコア傾向エントリ（時系列グラフ用）"""
    date: str                  # "YYYY-MM-DD"
    avg_score: float
    entry_count: int
    top_tag: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "avg_score": round(self.avg_score, 1),
            "entry_count": self.entry_count,
            "top_tag": self.top_tag,
        }


@dataclass
class UserProfile:
    """
    ユーザープロファイル — パーソナライゼーション設定の全体。

    fps-data/user/profile.json に保存される。
    """
    tag_weights: dict[str, TagWeight] = field(default_factory=dict)
    style_rules: list[StyleRule] = field(default_factory=list)
    tag_frequencies: dict[str, TagFrequencyEntry] = field(default_factory=dict)
    score_trends: list[ScoreTrendEntry] = field(default_factory=list)
    last_learned: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def top_tags(self, n: int = 20) -> list[TagFrequencyEntry]:
        return sorted(self.tag_frequencies.values(),
                      key=lambda e: e.count, reverse=True)[:n]

    def excluded_tags(self) -> list[str]:
        return [t for t, w in self.tag_weights.items() if w.weight == 0.0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag_weights": {t: w.to_dict() for t, w in self.tag_weights.items()},
            "style_rules": [r.to_dict() for r in self.style_rules],
            "tag_frequencies": {t: e.to_dict() for t, e in self.tag_frequencies.items()},
            "score_trends": [s.to_dict() for s in self.score_trends],
            "last_learned": self.last_learned.isoformat() if self.last_learned else None,
            "created_at": self.created_at.isoformat(),
        }
