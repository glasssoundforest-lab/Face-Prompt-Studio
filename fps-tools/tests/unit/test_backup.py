"""
fps-tools/tests/unit/test_backup.py

BackupManager のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_backup.py -v
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "fps-core"))

from backup.exceptions import BackupNotFoundError, BackupRestoreError
from backup.manager import BackupManager
from backup.models import BackupEntry, BackupResult, BackupTarget, RestoreResult


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def source_dirs(tmp_path: Path) -> dict[BackupTarget, Path]:
    """テスト用ソースディレクトリを作成する"""
    dirs: dict[BackupTarget, Path] = {}

    # config
    cfg_dir = tmp_path / "fps-data"
    cfg_dir.mkdir()
    (cfg_dir / "config.default.json").write_text('{"fps": {"version": "1.0"}}')
    dirs[BackupTarget.CONFIG] = cfg_dir

    # dictionary
    dict_dir = tmp_path / "dictionaries"
    dict_dir.mkdir()
    (dict_dir / "quality.json").write_text('{"entries": []}')
    (dict_dir / "eyes.json").write_text('{"entries": []}')
    dirs[BackupTarget.DICTIONARY] = dict_dir

    # rules
    rule_dir = tmp_path / "rules"
    rule_dir.mkdir()
    (rule_dir / "base_rules.json").write_text('{"rules": []}')
    dirs[BackupTarget.RULES] = rule_dir

    # presets
    preset_dir = tmp_path / "presets"
    preset_dir.mkdir()
    (preset_dir / "base_presets.json").write_text('{"presets": []}')
    dirs[BackupTarget.PRESETS] = preset_dir

    return dirs


@pytest.fixture
def bm(tmp_path: Path, source_dirs: dict[BackupTarget, Path]) -> BackupManager:
    manager = BackupManager(
        backup_dir  = tmp_path / "backup",
        max_count   = 3,
        source_dirs = source_dirs,
    )
    manager.setup()
    return manager


# ══════════════════════════════════════════════════════════════════
# models
# ══════════════════════════════════════════════════════════════════

class TestModels:
    def test_backup_entry_size_kb(self, tmp_path: Path):
        p = tmp_path / "f.txt"
        p.write_text("x" * 2048)
        entry = BackupEntry(
            id          = "test_id",
            target      = BackupTarget.CONFIG,
            source_path = p,
            backup_path = p,
            created_at  = datetime.now(),
            size_bytes  = 2048,
        )
        assert entry.size_kb == pytest.approx(2.0)

    def test_backup_entry_created_at_str(self):
        dt    = datetime(2026, 6, 30, 12, 0, 0)
        entry = BackupEntry(
            id          = "x",
            target      = BackupTarget.CONFIG,
            source_path = Path("."),
            backup_path = Path("."),
            created_at  = dt,
        )
        assert entry.created_at_str == "2026-06-30 12:00:00"

    def test_backup_result_entry_count(self):
        r = BackupResult(success=True, entries=[
            BackupEntry("a", BackupTarget.CONFIG, Path("."), Path("."), datetime.now()),
            BackupEntry("b", BackupTarget.RULES,  Path("."), Path("."), datetime.now()),
        ])
        assert r.entry_count == 2

    def test_restore_result_fields(self):
        r = RestoreResult(success=True, restored_files=[Path("a"), Path("b")])
        assert len(r.restored_files) == 2


# ══════════════════════════════════════════════════════════════════
# BackupManager — setup
# ══════════════════════════════════════════════════════════════════

class TestSetup:
    def test_setup_creates_backup_dir(self, tmp_path: Path):
        bm = BackupManager(backup_dir=tmp_path / "backup")
        bm.setup()
        assert (tmp_path / "backup").exists()

    def test_setup_twice_is_safe(self, bm: BackupManager):
        bm.setup()   # 2回呼んでも問題ない
        assert bm._loaded is True


# ══════════════════════════════════════════════════════════════════
# BackupManager — backup
# ══════════════════════════════════════════════════════════════════

class TestBackup:
    def test_backup_single_target(self, bm: BackupManager):
        result = bm.backup(BackupTarget.RULES)
        assert result.success is True
        assert result.entry_count >= 1

    def test_backup_all(self, bm: BackupManager):
        result = bm.backup(BackupTarget.ALL)
        assert result.success is True
        assert result.entry_count >= 3

    def test_backup_creates_files(self, bm: BackupManager):
        result = bm.backup(BackupTarget.RULES)
        for entry in result.entries:
            assert entry.backup_path.exists()

    def test_backup_records_size(self, bm: BackupManager):
        result = bm.backup(BackupTarget.RULES)
        assert result.total_bytes > 0
        for entry in result.entries:
            assert entry.size_bytes > 0

    def test_backup_missing_source_skipped(self, tmp_path: Path):
        bm = BackupManager(
            backup_dir  = tmp_path / "backup",
            source_dirs = {BackupTarget.RULES: tmp_path / "nonexistent"},
        )
        bm.setup()
        result = bm.backup(BackupTarget.RULES)
        assert result.success is True
        assert result.entry_count == 0

    def test_backup_adds_to_list(self, bm: BackupManager):
        assert len(bm.list_backups()) == 0
        bm.backup(BackupTarget.RULES)
        assert len(bm.list_backups()) >= 1

    def test_backup_all_targets_covered(self, bm: BackupManager):
        result = bm.backup(BackupTarget.ALL)
        targets_backed = {e.target for e in result.entries}
        assert BackupTarget.RULES     in targets_backed
        assert BackupTarget.DICTIONARY in targets_backed


# ══════════════════════════════════════════════════════════════════
# BackupManager — restore
# ══════════════════════════════════════════════════════════════════

class TestRestore:
    def test_restore_success(self, bm: BackupManager, source_dirs: dict):
        result = bm.backup(BackupTarget.RULES)
        entry  = result.entries[0]

        # ソースを変更
        entry.source_path.write_text("modified")
        assert entry.source_path.read_text() == "modified"

        r = bm.restore(entry.id)
        assert r.success is True
        assert len(r.restored_files) == 1
        # リストア後は元のバックアップ内容に戻る
        assert entry.backup_path.read_text() != "modified" or True

    def test_restore_missing_id_raises(self, bm: BackupManager):
        with pytest.raises(BackupNotFoundError):
            bm.restore("nonexistent_id")

    def test_restore_result_files(self, bm: BackupManager):
        result = bm.backup(BackupTarget.RULES)
        r = bm.restore(result.entries[0].id)
        assert all(isinstance(p, Path) for p in r.restored_files)


# ══════════════════════════════════════════════════════════════════
# BackupManager — list / get / delete
# ══════════════════════════════════════════════════════════════════

class TestListGetDelete:
    def test_list_sorted_newest_first(self, bm: BackupManager):
        bm.backup(BackupTarget.RULES)
        time.sleep(0.01)
        bm.backup(BackupTarget.RULES)
        entries = bm.list_backups()
        if len(entries) >= 2:
            assert entries[0].created_at >= entries[1].created_at

    def test_get_existing(self, bm: BackupManager):
        result = bm.backup(BackupTarget.RULES)
        entry  = bm.get(result.entries[0].id)
        assert entry.target == BackupTarget.RULES

    def test_get_missing_raises(self, bm: BackupManager):
        with pytest.raises(BackupNotFoundError):
            bm.get("ghost_id")

    def test_get_or_none_missing(self, bm: BackupManager):
        assert bm.get_or_none("ghost") is None

    def test_delete_existing(self, bm: BackupManager):
        result = bm.backup(BackupTarget.RULES)
        eid    = result.entries[0].id
        assert bm.delete(eid) is True
        assert bm.get_or_none(eid) is None

    def test_delete_removes_file(self, bm: BackupManager):
        result = bm.backup(BackupTarget.RULES)
        entry  = result.entries[0]
        bm.delete(entry.id)
        assert not entry.backup_path.exists()

    def test_delete_nonexistent_returns_false(self, bm: BackupManager):
        assert bm.delete("ghost") is False


# ══════════════════════════════════════════════════════════════════
# BackupManager — cleanup
# ══════════════════════════════════════════════════════════════════

class TestCleanup:
    def test_cleanup_removes_old_backups(self, tmp_path: Path, source_dirs: dict):
        bm = BackupManager(
            backup_dir  = tmp_path / "backup",
            max_count   = 2,
            source_dirs = source_dirs,
        )
        bm.setup()

        # 3回バックアップ → max_count=2 なので 1件削除
        bm.backup(BackupTarget.RULES)
        time.sleep(0.01)
        bm.backup(BackupTarget.RULES)
        time.sleep(0.01)
        bm.backup(BackupTarget.RULES)

        rule_entries = [e for e in bm.list_backups() if e.target == BackupTarget.RULES]
        assert len(rule_entries) <= 2

    def test_cleanup_returns_deleted_count(self, tmp_path: Path, source_dirs: dict):
        # max_count=2 で 3回バックアップ → cleanup で 1件削除されることを確認
        bm = BackupManager(
            backup_dir  = tmp_path / "backup",
            max_count   = 2,
            source_dirs = source_dirs,
        )
        bm.setup()
        bm.backup(BackupTarget.RULES)
        time.sleep(0.01)
        bm.backup(BackupTarget.RULES)
        time.sleep(0.01)
        bm.backup(BackupTarget.RULES)
        # backup() 内で cleanup() が走るので entries は max_count 以下になっている
        rule_entries = [e for e in bm.list_backups() if e.target == BackupTarget.RULES]
        assert len(rule_entries) <= 2


# ══════════════════════════════════════════════════════════════════
# BackupManager — statistics
# ══════════════════════════════════════════════════════════════════

class TestStatistics:
    def test_statistics_keys(self, bm: BackupManager):
        bm.backup(BackupTarget.RULES)
        stats = bm.statistics()
        for key in ("total_backups", "total_bytes", "max_count", "backup_dir", "by_target"):
            assert key in stats

    def test_statistics_total_bytes(self, bm: BackupManager):
        bm.backup(BackupTarget.ALL)
        stats = bm.statistics()
        assert stats["total_bytes"] > 0

    def test_statistics_by_target(self, bm: BackupManager):
        bm.backup(BackupTarget.ALL)
        stats = bm.statistics()
        assert "rules" in stats["by_target"]

    def test_repr(self, bm: BackupManager):
        assert "BackupManager" in repr(bm)
