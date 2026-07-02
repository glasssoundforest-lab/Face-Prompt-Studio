"""fps-core/marketplace/models.py — マーケットプレイス データモデル ★v3.0"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginType(str, Enum):
    DICTIONARY = "dictionary"   # タグ辞書
    RULE       = "rule"         # コンパイルルール
    TEMPLATE   = "template"     # プロンプトテンプレート
    WILDCARD   = "wildcard"     # Wildcard データ
    CHARACTER  = "character"    # キャラクタープリセット
    PRESET     = "preset"       # プリセット集
    FULL       = "full"         # 複合パッケージ


class PluginSource(str, Enum):
    REGISTRY   = "registry"     # FPS 公式レジストリ
    GITHUB     = "github"       # GitHub リポジトリ
    URL        = "url"          # 任意 URL
    LOCAL      = "local"        # ローカルファイル


@dataclass
class PluginManifest:
    """プラグインメタデータ"""
    id:           str
    name:         str
    version:      str            = "1.0.0"
    description:  str            = ""
    author:       str            = ""
    type:         PluginType     = PluginType.DICTIONARY
    source:       PluginSource   = PluginSource.REGISTRY
    source_url:   str            = ""
    tags:         list[str]      = field(default_factory=list)
    fps_min_version: str         = "2.0.0"
    installed:    bool           = False
    installed_at: str            = ""
    checksum:     str            = ""
    size_kb:      float          = 0.0
    download_count: int          = 0
    rating:       float          = 0.0
    homepage:     str            = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":            self.id,
            "name":          self.name,
            "version":       self.version,
            "description":   self.description,
            "author":        self.author,
            "type":          self.type,
            "source":        self.source,
            "source_url":    self.source_url,
            "tags":          self.tags,
            "fps_min_version": self.fps_min_version,
            "installed":     self.installed,
            "installed_at":  self.installed_at,
            "size_kb":       self.size_kb,
            "download_count": self.download_count,
            "rating":        round(self.rating, 1),
            "homepage":      self.homepage,
        }
