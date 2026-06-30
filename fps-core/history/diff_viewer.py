"""
fps-core/history/diff_viewer.py — Diff Viewer

2つの履歴エントリ（またはプロンプト文字列）間の差分を計算・表示する。
"""

from __future__ import annotations

from .models import DiffEntry, HistoryEntry


def _extract_tags(prompt: str) -> set[str]:
    """プロンプト文字列からタグ名の集合を抽出する（簡易パース、重み記法を除去）"""
    tags: set[str] = set()
    for part in prompt.split(","):
        part = part.strip()
        if not part:
            continue
        # (tag:weight) 形式から tag 部分のみ抽出
        if part.startswith("(") and part.endswith(")"):
            inner = part[1:-1]
            tag = inner.rsplit(":", 1)[0] if ":" in inner else inner
        else:
            tag = part
        tags.add(tag.strip())
    return tags


def diff_prompts(before: str, after: str) -> DiffEntry:
    """
    2つのプロンプト文字列を比較して差分を返す。

    Args:
        before: 比較元プロンプト
        after:  比較先プロンプト

    Returns:
        DiffEntry
    """
    before_tags = _extract_tags(before)
    after_tags = _extract_tags(after)

    added = sorted(after_tags - before_tags)
    removed = sorted(before_tags - after_tags)
    unchanged = sorted(before_tags & after_tags)

    return DiffEntry(
        added_tags=added,
        removed_tags=removed,
        unchanged_tags=unchanged,
    )


def diff_entries(before: HistoryEntry, after: HistoryEntry) -> DiffEntry:
    """
    2つの履歴エントリを比較して差分を返す（スコア差分も含む）。

    Args:
        before: 比較元エントリ
        after:  比較先エントリ

    Returns:
        DiffEntry
    """
    diff = diff_prompts(before.output_prompt, after.output_prompt)
    diff.score_delta = round(after.overall_score - before.overall_score, 2)
    return diff


def format_diff_report(
    diff: DiffEntry, before_label: str = "Before", after_label: str = "After"
) -> str:
    """
    DiffEntry を人間が読みやすいテキストレポートに整形する。
    """
    lines = [f"=== Diff: {before_label} → {after_label} ==="]

    if diff.added_tags:
        lines.append(f"+ Added   ({len(diff.added_tags)}): {', '.join(diff.added_tags)}")
    if diff.removed_tags:
        lines.append(f"- Removed ({len(diff.removed_tags)}): {', '.join(diff.removed_tags)}")
    if diff.unchanged_tags:
        lines.append(f"= Unchanged ({len(diff.unchanged_tags)}): {', '.join(diff.unchanged_tags)}")

    if not diff.has_changes:
        lines.append("(no tag changes)")

    if diff.score_delta != 0:
        sign = "+" if diff.score_delta > 0 else ""
        lines.append(f"Score change: {sign}{diff.score_delta}")

    return "\n".join(lines)
