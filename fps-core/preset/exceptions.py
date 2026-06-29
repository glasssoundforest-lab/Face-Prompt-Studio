"""
fps-core/preset/exceptions.py — Preset 例外定義
"""

from __future__ import annotations


class PresetError(Exception):
    """プリセット操作の基底例外"""


class PresetLoadError(PresetError):
    """プリセットファイル読み込み失敗"""


class PresetNotFoundError(PresetError):
    """指定 ID のプリセットが存在しない"""


class PresetValidationError(PresetError):
    """プリセットバリデーション失敗"""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or []

    def __str__(self) -> str:
        if self.errors:
            detail = "\n  - ".join(self.errors)
            return f"{super().__str__()}\n  - {detail}"
        return super().__str__()


class PresetSaveError(PresetError):
    """プリセット保存失敗"""
