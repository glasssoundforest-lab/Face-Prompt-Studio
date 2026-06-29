"""
fps-core/preset/merger.py — Preset Merger

複数プリセットをマージして新しいプリセットを生成する。

マージルール:
  - 同一タグが複数プリセットに存在する場合、後から指定したプリセットが優先
  - 重みは後勝ち（上書き）
  - negative_tags も同様にマージ
"""

from __future__ import annotations

import copy

from .models import MergeResult, Preset, PresetSource, PresetTag


def merge_presets(
    presets: list[Preset],
    result_id: str = "merged",
    result_name: str = "Merged Preset",
) -> MergeResult:
    """
    複数プリセットをマージして新しいプリセットを返す。

    Args:
        presets:     マージするプリセットリスト（後ろが優先）
        result_id:   マージ結果のプリセット ID
        result_name: マージ結果のプリセット名

    Returns:
        MergeResult
    """
    if not presets:
        empty = Preset(id=result_id, name=result_name)
        return MergeResult(preset=empty, merged_from=[], tag_count=0)

    tag_index: dict[str, PresetTag] = {}
    neg_index: dict[str, PresetTag] = {}
    conflicts: list[str] = []
    merged_from = [p.id for p in presets]

    for preset in presets:
        for tag in preset.tags:
            key = tag.tag.strip().lower()
            if key in tag_index and tag_index[key].weight != tag.weight:
                conflicts.append(
                    f"'{key}' weight {tag_index[key].weight} → {tag.weight} "
                    f"(from '{preset.id}')"
                )
            tag_index[key] = copy.copy(tag)

        for tag in preset.negative_tags:
            key = tag.tag.strip().lower()
            neg_index[key] = copy.copy(tag)

    merged_preset = Preset(
        id=result_id,
        name=result_name,
        tags=list(tag_index.values()),
        negative_tags=list(neg_index.values()),
        source=PresetSource.USER,
        description=f"Merged from: {', '.join(merged_from)}",
    )

    return MergeResult(
        preset=merged_preset,
        merged_from=merged_from,
        tag_count=len(tag_index),
        conflicts=conflicts,
    )


def diff_presets(base: Preset, other: Preset) -> dict[str, list[str]]:
    """
    2つのプリセットの差分を返す（デバッグ用）。

    Returns:
        {"added": [...], "removed": [...], "changed": [...]}
    """
    base_tags = {t.tag.lower(): t for t in base.tags}
    other_tags = {t.tag.lower(): t for t in other.tags}

    added = sorted(set(other_tags) - set(base_tags))
    removed = sorted(set(base_tags) - set(other_tags))
    changed = sorted(
        k for k in set(base_tags) & set(other_tags) if base_tags[k].weight != other_tags[k].weight
    )

    return {"added": added, "removed": removed, "changed": changed}
