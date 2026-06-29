"""
fps-core/rules/exceptions.py — Rule 例外定義
"""

from __future__ import annotations


class RuleError(Exception):
    """ルール操作の基底例外"""


class RuleLoadError(RuleError):
    """ルールファイル読み込み失敗"""


class RuleValidationError(RuleError):
    """ルールバリデーション失敗"""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or []

    def __str__(self) -> str:
        if self.errors:
            detail = "\n  - ".join(self.errors)
            return f"{super().__str__()}\n  - {detail}"
        return super().__str__()


class RuleEvalError(RuleError):
    """ルール評価中のエラー"""
