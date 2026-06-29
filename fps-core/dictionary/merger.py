"""
fps-core/dictionary/merger.py — Dictionary Merger

system 辞書と user 辞書をマージする。

ルール:
  - user エントリが同一キーを持つ場合、常に user が優先される
  - system エントリはユーザーが上書きしていないキーのみ残る
  - マージ結果は新しい辞書として返す（元の辞書は変更しない）
"""

from __future__ import annotations

import copy

from .models import DictEntry, DictFile, DictSource


def merge(
    system: list[DictFile],
    user: list[DictFile],
) -> dict[str, DictEntry]:
    """
    system 辞書リストと user 辞書リストをマージして
    キー→エントリの統合辞書を返す。

    user エントリが system エントリを常に上書きする。
    マージ後の DictSource は元のソースを維持する。

    Args:
        system: システム辞書ファイルリスト
        user:   ユーザー辞書ファイルリスト

    Returns:
        {正規化キー: DictEntry} の辞書
    """
    merged: dict[str, DictEntry] = {}

    # 1. system を先に展開（低優先）
    for df in system:
        for entry in df.entries:
            merged[entry.key] = copy.copy(entry)
            # エイリアスも登録
            for alias_key in _alias_keys(entry):
                if alias_key not in merged:
                    merged[alias_key] = copy.copy(entry)

    # 2. user で上書き（高優先）
    for df in user:
        for entry in df.entries:
            # エントリ自体を上書き
            merged[entry.key] = copy.copy(entry)
            # エイリアスも上書き
            for alias_key in _alias_keys(entry):
                merged[alias_key] = copy.copy(entry)

    return merged


def merge_entries(
    base: list[DictEntry],
    override: list[DictEntry],
) -> list[DictEntry]:
    """
    2つのエントリリストをマージして新しいリストを返す。
    override のエントリが base を上書きする。
    """
    index: dict[str, DictEntry] = {}

    for entry in base:
        index[entry.key] = copy.copy(entry)

    for entry in override:
        if entry.key in index and entry.source == DictSource.USER:
            index[entry.key] = copy.copy(entry)
        elif entry.key not in index:
            index[entry.key] = copy.copy(entry)

    return list(index.values())


def diff(
    before: dict[str, DictEntry],
    after: dict[str, DictEntry],
) -> dict[str, list[str]]:
    """
    マージ前後の差分を返す（デバッグ・ロギング用）。

    Returns:
        {"added": [...], "removed": [...], "changed": [...]}
    """
    before_keys = set(before.keys())
    after_keys = set(after.keys())

    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    changed = sorted(
        k
        for k in before_keys & after_keys
        if before[k].resolved != after[k].resolved or before[k].weight != after[k].weight
    )

    return {"added": added, "removed": removed, "changed": changed}


# ── Private ──────────────────────────────────────────────────────────


def _alias_keys(entry: DictEntry) -> list[str]:
    """エントリのエイリアスを正規化キーリストで返す"""
    from .models import _normalize_key

    return [_normalize_key(a) for a in entry.aliases]
