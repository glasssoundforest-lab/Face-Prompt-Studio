"""
fps-core/backup/manager.py — BackupManager

辞書・ルール・プリセット・設定ファイルを ZIP でバックアップし、
世代管理・リストアを行う。

Public API:
  - setup()                      バックアップディレクトリ初期化
  - backup(target)               指定ターゲットをバックアップ
  - restore(entry_id)            バックアップからリストア
  - list_backups(target=None)    バックアップ一覧（新しい順）
  - get_or_none(entry_id)        ID でエントリを取得（なければ None）
  - delete(entry_id)             バックアップを削除
  - cleanup()                    max_count を超えた古いバックアップを削除
"""

from __future__ import annotations

import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .exceptions import BackupNotFoundError, BackupRestoreError
from .models import BackupEntry, BackupResult, BackupTarget, RestoreResult


class BackupManager:
    """
    ファイルシステムバックアップ管理クラス。

    使い方:
        bm = BackupManager(
            backup_dir  = Path("./backup"),
            max_count   = 10,
            source_dirs = {
                BackupTarget.RULES:      Path("./fps-data/rules"),
                BackupTarget.DICTIONARY: Path("./fps-data/dictionaries"),
            },
        )
        bm.setup()
        result = bm.backup(BackupTarget.RULES)
        bm.restore(result.entries[0].id)
    """

    def __init__(
        self,
        backup_dir: Path,
        max_count: int = 10,
        source_dirs: dict[BackupTarget, Path] | None = None,
    ) -> None:
        self._backup_dir = Path(backup_dir)
        self._max_count = max_count
        self._source_dirs: dict[BackupTarget, Path] = source_dirs or {}
        self._entries: list[BackupEntry] = []
        self._lock = threading.RLock()
        self._loaded = False

    # ── 初期化 ────────────────────────────────────────────────────

    def setup(self) -> None:
        """バックアップディレクトリを作成し、既存バックアップを読み込む。"""
        with self._lock:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            self._loaded = True

    # ── バックアップ ──────────────────────────────────────────────

    def backup(self, target: BackupTarget = BackupTarget.ALL) -> BackupResult:
        """指定ターゲット（または全ターゲット）をバックアップする。"""
        with self._lock:
            targets = (
                [t for t in BackupTarget if t != BackupTarget.ALL]
                if target == BackupTarget.ALL
                else [target]
            )

            entries: list[BackupEntry] = []
            for t in targets:
                src = self._source_dirs.get(t)
                if src is None or not src.exists():
                    continue
                new_entries = self._backup_target(t, src)
                entries.extend(new_entries)
                self._entries[:0] = new_entries  # 先頭に追加

            self.cleanup()
            return BackupResult(success=True, entries=entries)

    def _backup_target(self, target: BackupTarget, source: Path) -> list[BackupEntry]:
        """1ターゲットのファイルを1件ずつコピーしてバックアップする。"""
        files = list(source.rglob("*")) if source.is_dir() else [source]
        files = [f for f in files if f.is_file()]

        entries: list[BackupEntry] = []
        for file in files:
            try:
                short_id = str(uuid.uuid4())[:8]
                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                # ファイル名を entry.id として使用（ノードのレポートから検索可能にする）
                filename = f"{target}_{ts}_{short_id}{file.suffix}"
                dest_path = self._backup_dir / filename

                shutil.copy2(file, dest_path)
                size = dest_path.stat().st_size

                entries.append(BackupEntry(
                    id=filename,          # ← ファイル名を ID として使用
                    target=target,
                    source_path=file,
                    backup_path=dest_path,
                    created_at=datetime.now(),
                    size_bytes=size,
                ))
            except Exception:
                continue
        return entries

    # ── リストア ──────────────────────────────────────────────────

    def restore(self, entry_id: str, target_dir: Path | None = None) -> RestoreResult:
        """バックアップ ID からファイルをリストアする。"""
        with self._lock:
            entry = self.get_or_none(entry_id)
            if entry is None:
                raise BackupNotFoundError(f"Backup '{entry_id}' not found")

            restore_to = target_dir or entry.source_path
            try:
                dest = restore_to if restore_to is not None else entry.source_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry.backup_path, dest)
                return RestoreResult(success=True, restored_files=[dest])
            except Exception as exc:
                raise BackupRestoreError(f"Restore failed: {exc}") from exc

    # ── 一覧・取得・削除 ─────────────────────────────────────────

    def list_backups(self, target: BackupTarget | None = None) -> list[BackupEntry]:
        """バックアップ一覧を新しい順で返す。"""
        with self._lock:
            entries = list(self._entries)
        if target and target != BackupTarget.ALL:
            entries = [e for e in entries if e.target == target]
        return sorted(entries, key=lambda e: e.created_at, reverse=True)

    def get(self, entry_id: str) -> BackupEntry:
        """ID でエントリを取得する。存在しない場合は BackupNotFoundError を raise。"""
        entry = self.get_or_none(entry_id)
        if entry is None:
            raise BackupNotFoundError(f"Backup '{entry_id}' not found")
        return entry

    def get_or_none(self, entry_id: str) -> BackupEntry | None:
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    return e
            return None

    def delete(self, entry_id: str) -> bool:
        with self._lock:
            entry = self.get_or_none(entry_id)
            if entry is None:
                return False
            if entry.backup_path.exists():
                entry.backup_path.unlink()
            self._entries = [e for e in self._entries if e.id != entry_id]
            return True

    def statistics(self) -> dict:
        """バックアップ統計情報を返す。"""
        with self._lock:
            entries = list(self._entries)
        by_target: dict[str, int] = {}
        total_bytes = 0
        for e in entries:
            by_target[str(e.target)] = by_target.get(str(e.target), 0) + 1
            total_bytes += e.size_bytes
        return {
            "total_backups": len(entries),
            "total_bytes": total_bytes,
            "total_kb": round(total_bytes / 1024, 2),
            "max_count": self._max_count,
            "backup_dir": str(self._backup_dir),
            "by_target": by_target,
        }

    # ── クリーンアップ ────────────────────────────────────────────
    def cleanup(self) -> int:
        """max_count を超えた古いバックアップを削除する。"""
        with self._lock:
            if len(self._entries) <= self._max_count:
                return 0
            sorted_entries = sorted(self._entries, key=lambda e: e.created_at, reverse=True)
            to_delete = sorted_entries[self._max_count:]
            for entry in to_delete:
                if entry.backup_path.exists():
                    entry.backup_path.unlink(missing_ok=True)
            self._entries = sorted_entries[: self._max_count]
            return len(to_delete)

    def __repr__(self) -> str:
        return (
            f"BackupManager(dir={self._backup_dir}, "
            f"count={len(self._entries)}, max={self._max_count})"
        )
