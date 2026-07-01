"""
fps-core/dictionary/validator.py — Dictionary Validator

DictFile / DictEntry の整合性を検証する。
"""

from __future__ import annotations

import re

from .exceptions import DictValidationError
from .models import DictEntry, DictFile

# resolved の形式: "Category.Value" または "Category.Sub.Value"
_RESOLVED_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]+(\.[A-Z][A-Za-z0-9]+)+$")
# ★M6-2: 日本語（ひらがな・カタカナ・漢字）を含む Unicode キーも許可
_KEY_PATTERN = re.compile(r"^[a-z0-9_\u3000-\u9fff\uff00-\uffef\u3040-\u30ff]+$")


def validate_dict_file(df: DictFile) -> None:
    """
    DictFile 全体を検証する。

    Raises:
        DictValidationError: 1件以上のエラーがある場合
    """
    errors: list[str] = []

    if not df.version:
        errors.append("version が空です")

    if not df.category:
        errors.append("category が空です")

    if not df.entries:
        errors.append("entries が空です（少なくとも1件必要）")

    seen_keys: set[str] = set()
    for i, entry in enumerate(df.entries):
        entry_errors = _validate_entry(entry, i)
        errors.extend(entry_errors)

        # キー重複チェック
        if entry.key in seen_keys:
            errors.append(f"entries[{i}]: キー '{entry.key}' が重複しています")
        seen_keys.add(entry.key)

        # エイリアス重複チェック
        for alias in entry.aliases:
            norm = alias.strip().lower().replace(" ", "_")
            if norm in seen_keys:
                errors.append(f"entries[{i}]: エイリアス '{alias}' が他のキーと重複しています")
            seen_keys.add(norm)

    if errors:
        raise DictValidationError(
            f"辞書ファイルのバリデーションエラー (category={df.category})", errors
        )


def validate_entry(entry: DictEntry) -> None:
    """
    単一エントリを検証する。

    Raises:
        DictValidationError: エラーがある場合
    """
    errors = _validate_entry(entry, -1)
    if errors:
        raise DictValidationError(f"エントリ '{entry.key}' のバリデーションエラー", errors)


# ── Private ──────────────────────────────────────────────────────────


def _validate_entry(entry: DictEntry, index: int) -> list[str]:
    """エントリを検証してエラーリストを返す（例外は投げない）"""
    errors: list[str] = []
    prefix = f"entries[{index}]" if index >= 0 else f"entry '{entry.key}'"

    # key 形式チェック
    if not entry.key:
        errors.append(f"{prefix}: key が空です")
    elif not _KEY_PATTERN.match(entry.key):
        errors.append(f"{prefix}: key '{entry.key}' は小文字英数字とアンダースコアのみ使用可能です")

    # resolved 形式チェック（Category.Value 形式）
    if not entry.resolved:
        errors.append(f"{prefix}: resolved が空です")
    elif not _RESOLVED_PATTERN.match(entry.resolved):
        errors.append(
            f"{prefix}: resolved '{entry.resolved}' は 'Category.Value' 形式である必要があります"
        )

    # weight 範囲チェック
    if not (0.0 < entry.weight <= 3.0):
        errors.append(f"{prefix}: weight {entry.weight} は 0.0〜3.0 の範囲である必要があります")

    # category 空チェック
    if not entry.category:
        errors.append(f"{prefix}: category が空です")

    return errors
