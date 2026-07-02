"""fps-core/character/models.py — キャラクターデータモデル ★v2.7"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CharacterFeature:
    """キャラクターの1特徴（タグ + 重み）"""
    tag:      str
    weight:   float = 1.0
    category: str   = ""
    note:     str   = ""

    def to_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "weight": self.weight,
                "category": self.category, "note": self.note}


@dataclass
class CharacterProfile:
    """
    キャラクターシート — 1キャラクターの顔・体型・スタイルの定義。

    compile 時に pos プロンプトのベースとして使用する。
    """
    id:          str
    name:        str
    description: str                       = ""
    features:    list[CharacterFeature]    = field(default_factory=list)
    neg_features: list[CharacterFeature]   = field(default_factory=list)  # neg 専用タグ
    tags:        list[str]                 = field(default_factory=list)   # 簡易リスト
    meta:        dict[str, Any]            = field(default_factory=dict)
    created_at:  str                       = ""
    updated_at:  str                       = ""

    def to_pos_prompt(self) -> str:
        """キャラクターの特徴を pos プロンプト文字列に変換する"""
        parts: list[str] = []
        for f in self.features:
            if f.weight == 1.0:
                parts.append(f.tag)
            elif f.weight > 1.0:
                parts.append(f"({f.tag}:{f.weight:.1f})")
            # weight=0.0 は除外
        # 簡易タグも追加
        parts.extend(t for t in self.tags if t not in [f.tag for f in self.features])
        return ", ".join(parts)

    def to_neg_prompt(self) -> str:
        """ネガティブ専用タグを neg プロンプト文字列に変換する"""
        return ", ".join(f.tag for f in self.neg_features)

    def feature_by_category(self, category: str) -> list[CharacterFeature]:
        return [f for f in self.features if f.category == category]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":          self.id,
            "name":        self.name,
            "description": self.description,
            "features":    [f.to_dict() for f in self.features],
            "neg_features": [f.to_dict() for f in self.neg_features],
            "tags":        self.tags,
            "meta":        self.meta,
            "created_at":  self.created_at,
            "updated_at":  self.updated_at,
        }
