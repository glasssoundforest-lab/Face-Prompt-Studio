"""
fps-core/events/models.py — Event データモデル
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    # パイプライン全体
    PIPELINE_BEFORE_COMPILE = "pipeline.before_compile"
    PIPELINE_AFTER_COMPILE = "pipeline.after_compile"
    PIPELINE_ERROR = "pipeline.error"
    PIPELINE_CACHE_HIT = "pipeline.cache_hit"

    # ステージ単位
    STAGE_BEFORE_RUN = "stage.before_run"
    STAGE_AFTER_RUN = "stage.after_run"
    STAGE_ERROR = "stage.error"

    # 辞書
    DICTIONARY_LOADED = "dictionary.loaded"
    DICTIONARY_RELOADED = "dictionary.reloaded"
    DICTIONARY_LOOKUP_MISS = "dictionary.lookup_miss"
    DICTIONARY_BEFORE_SAVE = "dictionary.before_save"
    DICTIONARY_AFTER_SAVE = "dictionary.after_save"

    # ルール
    RULE_APPLIED = "rule.applied"
    RULE_BEFORE_SAVE = "rule.before_save"
    RULE_AFTER_SAVE = "rule.after_save"

    # プリセット
    PRESET_BEFORE_SAVE = "preset.before_save"
    PRESET_AFTER_SAVE = "preset.after_save"

    # バックアップ
    BACKUP_CREATED = "backup.created"
    BACKUP_RESTORED = "backup.restored"
    BACKUP_FAILED = "backup.failed"

    # プラグイン
    PLUGIN_REGISTERED = "plugin.registered"
    PLUGIN_SETUP_FAILED = "plugin.setup_failed"

    # 汎用（ユーザー独自イベント用）
    CUSTOM = "custom"


@dataclass(slots=True)
class Event:
    """発火されるイベント 1件"""

    type: EventType | str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass(slots=True)
class HandlerRegistration:
    """登録済みハンドラーの情報（管理・デバッグ用）"""

    event_type: str
    handler_name: str
    priority: int = 0
    once: bool = False
