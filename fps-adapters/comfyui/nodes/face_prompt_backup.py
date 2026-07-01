"""
fps-adapters/comfyui/nodes/face_prompt_backup.py
ノード: 🎭 Face Prompt Backup

機能:
  - 辞書・ルール・プリセットの手動バックアップ作成
  - バックアップ一覧・統計表示
  - 指定IDからのリストア

入力:
  action      STRING(選択式)  実行するアクション
  restore_id  STRING          リストアするバックアップID（action=restoreの場合）

出力:
  report      STRING  実行結果・バックアップ一覧レポート
"""

from __future__ import annotations

from typing import Any

from .node_base import _ROOT, FPSNodeBase

_backup_manager = None


def _get_backup_manager():
    """BackupManager をシングルトンで返す"""
    global _backup_manager
    if _backup_manager is None:
        from backup.manager import BackupManager
        from backup.models import BackupTarget

        data_root = _ROOT / "fps-data"
        _backup_manager = BackupManager(
            backup_dir=_ROOT / "backup",
            max_count=10,
            source_dirs={
                BackupTarget.DICTIONARY: data_root / "dictionaries",
                BackupTarget.RULES: data_root / "rules",
                BackupTarget.PRESETS: data_root / "presets",
            },
        )
        _backup_manager.setup()
    return _backup_manager


class FacePromptBackupNode(FPSNodeBase):
    """Face Prompt Backup ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("report",)
    FUNCTION = "manage_backup"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "action": (
                    [
                        "list",
                        "backup_all",
                        "backup_dictionary",
                        "backup_rules",
                        "backup_presets",
                        "restore",
                    ],
                    {"default": "list"},
                ),
            },
            "optional": {
                "restore_id": (
                    "STRING",
                    {"default": "", "placeholder": "リストアするバックアップID"},
                ),
            },
        }

    def manage_backup(self, action: str = "list", restore_id: str = "") -> tuple[str]:
        """
        バックアップ操作を実行してレポートを返す。

        Returns:
            (report,)
        """
        from backup.models import BackupTarget

        try:
            bm = _get_backup_manager()
        except Exception as e:
            return (f"[ERROR] BackupManager の初期化に失敗しました: {e}",)

        lines = ["=== Face Prompt Backup ===", ""]

        target_map = {
            "backup_all": BackupTarget.ALL,
            "backup_dictionary": BackupTarget.DICTIONARY,
            "backup_rules": BackupTarget.RULES,
            "backup_presets": BackupTarget.PRESETS,
        }

        if action in target_map:
            result = bm.backup(target_map[action])
            status = "OK" if result.success else "FAILED"
            lines += [
                f"[{status}] backup({action})",
                f"  entries  : {result.entry_count}",
                f"  size     : {result.total_bytes} bytes",
            ]
            if result.errors:
                lines.append("  errors:")
                lines.extend(f"    - {e}" for e in result.errors)

        elif action == "restore":
            if not restore_id.strip():
                lines.append("[ERROR] restore_id が指定されていません。")
            else:
                try:
                    r = bm.restore(restore_id.strip())
                    status = "OK" if r.success else "FAILED"
                    lines += [
                        f"[{status}] restore({restore_id})",
                        f"  restored files: {[str(p) for p in r.restored_files]}",
                    ]
                    if r.errors:
                        lines.extend(f"    - {e}" for e in r.errors)
                except Exception as e:
                    lines.append(f"[ERROR] {e}")

        stats = bm.statistics()
        lines += [
            "",
            "--- Statistics ---",
            f"  total_backups : {stats['total_backups']}",
            f"  total_size    : {stats['total_kb']} KB",
            f"  max_count     : {stats['max_count']}",
            f"  by_target     : {stats['by_target']}",
            "",
            "--- Recent Backups (newest first, max 10) ---",
        ]

        entries = bm.list_backups()[:10]
        for entry in entries:
            lines.append(
                f"  {entry.id}  [{entry.target}]  {entry.created_at_str}  ({entry.size_kb:.1f}KB)"
            )
        if not entries:
            lines.append("  (no backups yet)")

        return ("\n".join(lines),)
