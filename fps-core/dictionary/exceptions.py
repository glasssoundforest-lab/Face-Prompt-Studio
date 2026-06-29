"""
fps-core/dictionary/exceptions.py — Dictionary 例外定義
"""

from __future__ import annotations


class DictionaryError(Exception):
    """辞書操作の基底例外"""


class DictLoadError(DictionaryError):
    """辞書ファイルの読み込み失敗"""


class DictValidationError(DictionaryError):
    """辞書ファイルのバリデーション失敗"""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or []

    def __str__(self) -> str:
        if self.errors:
            detail = "\n  - ".join(self.errors)
            return f"{super().__str__()}\n  - {detail}"
        return super().__str__()


class DictMergeError(DictionaryError):
    """辞書マージの失敗"""


class DictNotFoundError(DictionaryError):
    """指定キーが辞書に存在しない"""
