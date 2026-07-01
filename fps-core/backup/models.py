"""
fps-core/backup/models.py — バックアップデータモデル
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class BackupTarget(StrEnum):
    """バックアップ対象の種別"""

    CONFIG = "config"
    DICTIONARY = "dictionary"
    RULES = "rules"
    PRESETS = "presets"
    ALL = "all"


@dataclass
class BackupEntry:
    """バックアップエントリ 1 件"""

    id: str
    target: BackupTarget
    source_path: Path
    backup_path: Path
    created_at: datetime
    size_bytes: int = 0

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024

    @property
    def created_at_str(self) -> str:
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class BackupResult:
    """バックアップ操作の結果"""

    success: bool
    entries: list[BackupEntry] = field(default_factory=list)
    error: str = ""

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def total_bytes(self) -> int:
        return sum(e.size_bytes for e in self.entries)

    @property
    def errors(self) -> list[str]:
        """後方互換: ComfyUI ノードが参照するエラーリスト"""
        return [self.error] if self.error else []


@dataclass
class RestoreResult:
    """リストア操作の結果"""

    success: bool
    restored_files: list[Path] = field(default_factory=list)
    error: str = ""
