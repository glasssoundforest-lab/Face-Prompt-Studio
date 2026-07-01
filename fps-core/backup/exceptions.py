"""fps-core/backup/exceptions.py — バックアップ例外"""


class BackupError(Exception):
    """バックアップ操作の基底例外"""


class BackupNotFoundError(BackupError):
    """指定 ID のバックアップが存在しない"""


class BackupRestoreError(BackupError):
    """リストア中にエラーが発生した"""
