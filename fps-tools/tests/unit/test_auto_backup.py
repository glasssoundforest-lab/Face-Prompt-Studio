"""
fps-tools/tests/unit/test_auto_backup.py

AutoBackupHandler（Gap 2 対応）のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_auto_backup.py -v
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from backup.manager import BackupManager
from backup.models import BackupTarget
from events.event_bus import EventBus
from events.handlers import AutoBackupHandler
from events.models import Event, EventType


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    d = tmp_path / "rules"
    d.mkdir()
    (d / "base_rules.json").write_text(
        json.dumps({"version": "1.0", "rules": []}), encoding="utf-8"
    )
    return d


@pytest.fixture
def backup_manager(tmp_path: Path, source_dir: Path) -> BackupManager:
    bm = BackupManager(
        backup_dir=tmp_path / "backup",
        max_count=5,
        source_dirs={BackupTarget.RULES: source_dir},
    )
    bm.setup()
    return bm


class TestAutoBackupHandlerBasic:
    def test_handler_creates_backup_on_call(self, backup_manager: BackupManager):
        handler = AutoBackupHandler(backup_manager, target=BackupTarget.RULES, min_interval_sec=0)
        event = Event(type=EventType.RULE_BEFORE_SAVE)
        handler(event)
        stats = handler.statistics()
        assert stats["backup_count"] == 1
        assert stats["error_count"] == 0

    def test_handler_backup_appears_in_manager(self, backup_manager: BackupManager):
        handler = AutoBackupHandler(backup_manager, target=BackupTarget.RULES, min_interval_sec=0)
        handler(Event(type=EventType.RULE_BEFORE_SAVE))
        entries = backup_manager.list_backups()
        assert len(entries) >= 1

    def test_handler_statistics_empty_initially(self, backup_manager: BackupManager):
        handler = AutoBackupHandler(backup_manager, target=BackupTarget.RULES)
        stats = handler.statistics()
        assert stats["backup_count"] == 0


class TestAutoBackupHandlerThrottling:
    def test_min_interval_blocks_rapid_calls(self, backup_manager: BackupManager):
        handler = AutoBackupHandler(
            backup_manager, target=BackupTarget.RULES, min_interval_sec=10.0
        )
        event = Event(type=EventType.RULE_BEFORE_SAVE)
        handler(event)
        handler(event)
        handler(event)
        stats = handler.statistics()
        assert stats["backup_count"] == 1

    def test_zero_interval_allows_every_call(self, backup_manager: BackupManager):
        handler = AutoBackupHandler(backup_manager, target=BackupTarget.RULES, min_interval_sec=0)
        event = Event(type=EventType.RULE_BEFORE_SAVE)
        handler(event)
        handler(event)
        stats = handler.statistics()
        assert stats["backup_count"] == 2

    def test_interval_allows_after_wait(self, backup_manager: BackupManager):
        handler = AutoBackupHandler(
            backup_manager, target=BackupTarget.RULES, min_interval_sec=0.05
        )
        event = Event(type=EventType.RULE_BEFORE_SAVE)
        handler(event)
        time.sleep(0.1)
        handler(event)
        stats = handler.statistics()
        assert stats["backup_count"] == 2


class TestEventBusIntegration:
    def test_handler_registered_via_event_bus(self, backup_manager: BackupManager):
        bus = EventBus()
        handler = AutoBackupHandler(backup_manager, target=BackupTarget.RULES, min_interval_sec=0)
        bus.on(EventType.RULE_BEFORE_SAVE, handler)
        bus.emit(EventType.RULE_BEFORE_SAVE, {"reason": "user_edit"})
        stats = handler.statistics()
        assert stats["backup_count"] == 1

    def test_multiple_save_events_create_multiple_backups(self, backup_manager: BackupManager):
        bus = EventBus()
        handler = AutoBackupHandler(backup_manager, target=BackupTarget.RULES, min_interval_sec=0)
        bus.on(EventType.RULE_BEFORE_SAVE, handler)
        bus.on(EventType.DICTIONARY_BEFORE_SAVE, handler)
        bus.emit(EventType.RULE_BEFORE_SAVE)
        bus.emit(EventType.DICTIONARY_BEFORE_SAVE)
        stats = handler.statistics()
        assert stats["backup_count"] == 2

    def test_other_handlers_unaffected(self, backup_manager: BackupManager):
        bus = EventBus()
        calls = []
        bus.on("custom.event", lambda e: calls.append(1))
        handler = AutoBackupHandler(backup_manager, target=BackupTarget.RULES, min_interval_sec=0)
        bus.on(EventType.RULE_BEFORE_SAVE, handler)
        bus.emit("custom.event")
        bus.emit(EventType.RULE_BEFORE_SAVE)
        assert calls == [1]
        assert handler.statistics()["backup_count"] == 1


class TestAutoBackupErrorHandling:
    def test_invalid_source_dir_does_not_crash(self, tmp_path: Path):
        bm = BackupManager(
            backup_dir=tmp_path / "backup",
            source_dirs={BackupTarget.RULES: tmp_path / "nonexistent"},
        )
        bm.setup()
        handler = AutoBackupHandler(bm, target=BackupTarget.RULES, min_interval_sec=0)
        handler(Event(type=EventType.RULE_BEFORE_SAVE))
        stats = handler.statistics()
        assert stats["error_count"] == 0

    def test_handler_does_not_raise_on_bad_manager(self):
        class BrokenBackupManager:
            def backup(self, target):
                raise RuntimeError("intentional failure")

        handler = AutoBackupHandler(
            BrokenBackupManager(), target=BackupTarget.RULES, min_interval_sec=0
        )
        handler(Event(type=EventType.RULE_BEFORE_SAVE))
        stats = handler.statistics()
        assert stats["error_count"] == 1
        assert "intentional failure" in stats["last_error"]
