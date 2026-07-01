"""
fps-core/optimizer/conflict_detector.py — Conflict Detector

同一カテゴリ内で排他的な属性（色など）が複数指定されている矛盾を検出する。

例: blue_eyes (Eyes.Blue) + brown_eyes (Eyes.Brown) → 矛盾
    blue_eyes (Eyes.Blue) + sparkling_eyes (Eyes.Sparkling) → 矛盾でない
    （前者は色、後者は効果なので排他グループが異なる）
"""

from __future__ import annotations

from typing import Any

from .models import IssueSeverity, IssueType, OptimizationIssue

# 排他グループ定義: resolved の prefix（Category.SubPrefix）が同じものは
# 同一カテゴリの「値違い」として扱う。
# 例: "Eyes.Blue" と "Eyes.Brown" は両方 "Eyes" prefix なので
#     色グループとして同時指定は矛盾とみなす。
#
# ただし全ての同一カテゴリが矛盾という訳ではない
# （例: Eyes.Large と Eyes.Blue は形状と色で別概念）ため、
# 「排他的サブグループ」を明示的に定義する。
EXCLUSIVE_GROUPS: dict[str, set[str]] = {
    "eyes_color": {
        "Eyes.Blue",
        "Eyes.Green",
        "Eyes.Brown",
        "Eyes.Red",
        "Eyes.Golden",
        "Eyes.Purple",
        "Eyes.Silver",
        "Eyes.Black",
    },
    "hair_color": {
        "Hair.Blonde",
        "Hair.Black",
        "Hair.Silver",
        "Hair.Brown",
        "Hair.Red",
        "Hair.Pink",
        "Hair.Purple",
        "Hair.Blue",
        "Hair.Green",
    },
    "hair_length": {
        "Hair.Long",
        "Hair.Short",
        "Hair.Medium",
        "Hair.VeryLong",
    },
    "skin_tone": {
        "Skin.Fair",
        "Skin.Tan",
        "Skin.Dark",
        "Skin.Olive",
        "Skin.Pale",
    },
    "face_shape": {
        "FaceShape.Oval",
        "FaceShape.Round",
        "FaceShape.Square",
        "FaceShape.Heart",
        "FaceShape.Long",
    },
    "mouth_state": {
        "Mouth.Open",
        "Mouth.Closed",
        "Mouth.Parted",
    },
    "eyes_shape_lid": {
        "Eyes.HalfClosed",
        "Eyes.Large",
    },
    "quality_level": {
        "Quality.High",
        "Quality.Medium",
        "Quality.Low",
    },
    "makeup_intensity": {
        "Makeup.Heavy",
        "Makeup.Light",
    },
}


def detect_conflicts(tags: list[dict[str, Any]]) -> list[OptimizationIssue]:
    """
    タグリストから矛盾を検出する。

    Args:
        tags: [{"tag": str, "category": str, "weight": float, "meta": {...}}, ...]
              meta に "resolved" キーがあれば利用、なければ tag をそのまま使う

    Returns:
        検出された矛盾の OptimizationIssue リスト
    """
    issues: list[OptimizationIssue] = []

    resolved_values: list[tuple[str, str]] = []  # (resolved, original_tag)
    for t in tags:
        resolved = t.get("meta", {}).get("resolved") or t.get("resolved") or t.get("tag", "")
        resolved_values.append((resolved, t.get("tag", "")))

    for group_name, group_values in EXCLUSIVE_GROUPS.items():
        matched = [(resolved, tag) for resolved, tag in resolved_values if resolved in group_values]
        unique_resolved = {r for r, _ in matched}

        if len(unique_resolved) > 1:
            tag_names = [t for _, t in matched]
            issues.append(
                OptimizationIssue(
                    type=IssueType.CONFLICT,
                    severity=IssueSeverity.WARNING,
                    message=(
                        f"排他的な属性が複数指定されています ({group_name}): "
                        f"{', '.join(sorted(unique_resolved))}"
                    ),
                    tags=tag_names,
                    category=group_name,
                    suggestion=f"{group_name} はいずれか1つに絞ることを推奨します。",
                )
            )

    return issues


# ── M6-1 ネガティブプロンプト クロスチェック ──────────────────────

# ポジティブとネガティブで同時指定すると意味が打ち消し合う resolved グループ
CROSS_CONFLICT_GROUPS: dict[str, set[str]] = {
    "quality_level": {"Quality.High", "Quality.Medium", "Quality.Low"},
    "eyes_color": {
        "Eyes.Blue", "Eyes.Green", "Eyes.Brown", "Eyes.Red",
        "Eyes.Golden", "Eyes.Purple", "Eyes.Silver", "Eyes.Black",
    },
    "hair_color": {
        "Hair.Blonde", "Hair.Black", "Hair.Silver", "Hair.Brown",
        "Hair.Red", "Hair.Pink", "Hair.Purple", "Hair.Blue", "Hair.Green",
    },
    "expression_smile": {"Expression.Smile", "Expression.Grin", "Expression.Smirk"},
    "skin_tone": {"Skin.Fair", "Skin.Tan", "Skin.Dark", "Skin.Olive", "Skin.Pale"},
}


def detect_cross_conflicts(
    positive_tags: list[dict],
    negative_tags: list[dict],
) -> list[OptimizationIssue]:
    """ポジティブ/ネガティブプロンプト間の矛盾を検出する。

    同一排他グループの値がポジティブとネガティブの両方に存在する場合、
    プロンプトが打ち消し合う危険性を警告する。

    Args:
        positive_tags: ポジティブプロンプトのタグリスト
        negative_tags: ネガティブプロンプトのタグリスト

    Returns:
        検出された CROSS_CONFLICT 問題リスト
    """
    from .models import IssueSeverity, IssueType, OptimizationIssue  # noqa: PLC0415

    issues: list[OptimizationIssue] = []

    def resolved_set(tags: list[dict]) -> set[str]:
        return {
            t.get("meta", {}).get("resolved") or t.get("resolved") or t.get("tag", "")
            for t in tags
        }

    pos_resolved = resolved_set(positive_tags)
    neg_resolved = resolved_set(negative_tags)

    for group_name, group_values in CROSS_CONFLICT_GROUPS.items():
        pos_match = pos_resolved & group_values
        neg_match = neg_resolved & group_values
        overlap = pos_match & neg_match

        if overlap:
            issues.append(
                OptimizationIssue(
                    type=IssueType.CROSS_CONFLICT,
                    severity=IssueSeverity.WARNING,
                    message=(
                        f"ポジティブとネガティブが同じ属性を指定しています ({group_name}): "
                        f"{', '.join(sorted(overlap))}"
                    ),
                    tags=sorted(overlap),
                    category=group_name,
                    suggestion=(
                        "ポジティブとネガティブで同一属性を指定すると "
                        "プロンプトの効果が打ち消し合います。"
                    ),
                )
            )
        elif pos_match and neg_match:
            # 同グループ内の別属性がポジティブ/ネガティブに存在する場合も警告
            issues.append(
                OptimizationIssue(
                    type=IssueType.CROSS_CONFLICT,
                    severity=IssueSeverity.INFO,
                    message=(
                        f"ポジティブとネガティブが同一グループ内の異なる属性を指定しています "
                        f"({group_name}): +"
                        f"{', '.join(sorted(pos_match))} / −"
                        f"{', '.join(sorted(neg_match))}"
                    ),
                    tags=sorted(pos_match | neg_match),
                    category=group_name,
                    suggestion="意図した表現かどうか確認してください。",
                )
            )

    return issues
