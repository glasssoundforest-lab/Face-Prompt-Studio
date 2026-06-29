"""
fps-core/dictionary/models.py — Dictionary データモデル

すべての辞書エントリと辞書ファイルの構造を定義する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DictSource(StrEnum):
    """辞書のソース種別"""

    SYSTEM = "system"  # システム辞書（更新で上書きされる）
    USER = "user"  # ユーザー辞書（絶対に上書きしない）


@dataclass(slots=True)
class DictEntry:
    """
    辞書エントリ 1件。

    例:
        DictEntry(
            key="masterpiece",
            resolved="Quality.High",
            category="quality",
            aliases=["best quality"],
            weight=1.0,
            source=DictSource.SYSTEM,
        )
    """

    key: str  # 正規化済みキー（小文字・アンダースコア）
    resolved: str  # 変換後の表現  例: "Quality.High"
    category: str  # カテゴリ       例: "quality"
    aliases: list[str] = field(default_factory=list)  # 別名リスト
    weight: float = 1.0  # デフォルト重み
    source: DictSource = DictSource.SYSTEM  # ソース種別
    tags: list[str] = field(default_factory=list)  # 任意タグ
    meta: dict[str, Any] = field(default_factory=dict)  # 拡張メタデータ

    def __post_init__(self) -> None:
        self.key = _normalize_key(self.key)

    @property
    def all_keys(self) -> list[str]:
        """キー + エイリアス全て（検索用）"""
        return [self.key] + [_normalize_key(a) for a in self.aliases]


@dataclass(slots=True)
class DictFile:
    """
    辞書ファイル 1つ分のデータ。

    JSON / YAML ファイルをこの構造にマッピングする。
    """

    version: str
    category: str
    source: DictSource
    entries: list[DictEntry] = field(default_factory=list)
    description: str = ""

    @property
    def entry_count(self) -> int:
        return len(self.entries)


@dataclass(slots=True)
class LookupResult:
    """lookup() の戻り値"""

    found: bool
    key: str
    entry: DictEntry | None = None
    matched_alias: str | None = None  # エイリアスでヒットした場合

    @property
    def resolved(self) -> str | None:
        return self.entry.resolved if self.entry else None

    @property
    def category(self) -> str | None:
        return self.entry.category if self.entry else None

    @property
    def weight(self) -> float:
        return self.entry.weight if self.entry else 1.0


def _normalize_key(key: str) -> str:
    """キーを正規化する（小文字・空白→アンダースコア）"""
    return key.strip().lower().replace(" ", "_").replace("-", "_")
