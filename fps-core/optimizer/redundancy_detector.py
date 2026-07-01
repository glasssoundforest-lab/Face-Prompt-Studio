"""
fps-core/optimizer/redundancy_detector.py — Redundancy Detector

意味的に重複するタグの組み合わせを検出する。

例: smile + grin           → 両方「笑顔」系で冗長
    masterpiece + high_quality → 両方「高品質」系で冗長
"""

from __future__ import annotations

from typing import Any

from .models import IssueSeverity, IssueType, OptimizationIssue

# 意味的に重複しがちな resolved 値のグループ
# （EXCLUSIVE_GROUPS とは異なり、こちらは「両方使うと冗長」だが
#   矛盾ではない＝同時に存在しても破綻はしないが無駄が多いケース）
REDUNDANT_GROUPS: dict[str, set[str]] = {
    "smile_family": {
        "Expression.Smile",
        "Expression.Grin",
        "Expression.Smirk",
    },
    "quality_boost": {
        "Quality.High",
    },
    "lips_full": {
        "Mouth.FullLips",
        "Mouth.CupidBow",
    },
    "makeup_red_lip": {
        "Makeup.RedLipstick",
        "Makeup.Lipstick",
    },
    "hair_tied": {
        "Hair.Ponytail",
        "Hair.SidePonytail",
        "Hair.Bun",
        "Hair.Twintails",
    },
}


def detect_redundancy(tags: list[dict[str, Any]]) -> list[OptimizationIssue]:
    """
    タグリストから意味的重複を検出する。

    Args:
        tags: [{"tag": str, "category": str, "weight": float, "meta": {...}}, ...]

    Returns:
        検出された冗長性の OptimizationIssue リスト
    """
    issues: list[OptimizationIssue] = []

    resolved_values: list[tuple[str, str]] = []
    for t in tags:
        resolved = t.get("meta", {}).get("resolved") or t.get("resolved") or t.get("tag", "")
        resolved_values.append((resolved, t.get("tag", "")))

    for group_name, group_values in REDUNDANT_GROUPS.items():
        matched = [(resolved, tag) for resolved, tag in resolved_values if resolved in group_values]
        unique_resolved = {r for r, _ in matched}

        if len(unique_resolved) > 1:
            tag_names = [t for _, t in matched]
            issues.append(
                OptimizationIssue(
                    type=IssueType.REDUNDANT,
                    severity=IssueSeverity.INFO,
                    message=(
                        f"意味的に重複するタグが含まれています ({group_name}): "
                        f"{', '.join(sorted(unique_resolved))}"
                    ),
                    tags=tag_names,
                    category=group_name,
                    suggestion="重複タグを1つにまとめると簡潔になります。",
                )
            )

    # 完全な重複タグ（同一 resolved が複数 — 通常は DuplicateCleanerStage で
    # 除去されるはずだが、念のため検出）
    seen: dict[str, list[str]] = {}
    for resolved, tag in resolved_values:
        seen.setdefault(resolved, []).append(tag)

    for resolved, tag_list in seen.items():
        if len(tag_list) > 1:
            issues.append(
                OptimizationIssue(
                    type=IssueType.REDUNDANT,
                    severity=IssueSeverity.WARNING,
                    message=f"同一概念のタグが重複しています: {', '.join(tag_list)} → {resolved}",
                    tags=tag_list,
                    category="exact_duplicate",
                    suggestion="1つに統合してください。",
                )
            )

    return issues


# ── M6-1 ネガティブプロンプト専用 冗長グループ ────────────────────

NEGATIVE_REDUNDANT_GROUPS: dict[str, set[str]] = {
    "neg_low_quality": {
        "Quality.Low",
        "Quality.Worst",
        "Quality.Bad",
    },
    "neg_body_distortion": {
        "Body.BadHands",
        "Body.ExtraFingers",
        "Body.MissingFingers",
        "Body.BadAnatomy",
    },
    "neg_blur": {
        "Style.Blur",
        "Style.Blurry",
        "Style.OutOfFocus",
    },
    "neg_text": {
        "Style.Watermark",
        "Style.Text",
        "Style.Signature",
    },
    "neg_face_defect": {
        "FaceShape.BadFace",
        "Eyes.CrossEyed",
        "Eyes.Asymmetric",
    },
}


def detect_negative_redundancy(tags: list[dict]) -> list:
    """ネガティブプロンプト専用の冗長検出。

    意味的に近いネガティブタグが複数指定されている場合に警告する。

    Args:
        tags: ネガティブプロンプトのタグリスト

    Returns:
        冗長性の OptimizationIssue リスト
    """
    from .models import IssueSeverity, IssueType, OptimizationIssue  # noqa: PLC0415

    issues = []
    resolved_values = [
        (t.get("meta", {}).get("resolved") or t.get("resolved") or t.get("tag", ""),
         t.get("tag", ""))
        for t in tags
    ]

    for group_name, group_values in NEGATIVE_REDUNDANT_GROUPS.items():
        matched = [(r, t) for r, t in resolved_values if r in group_values]
        if len({r for r, _ in matched}) > 1:
            issues.append(
                OptimizationIssue(
                    type=IssueType.REDUNDANT,
                    severity=IssueSeverity.INFO,
                    message=(
                        f"ネガティブプロンプトに意味的に近いタグが複数あります ({group_name}): "
                        f"{', '.join(sorted({r for r, _ in matched}))}"
                    ),
                    tags=[t for _, t in matched],
                    category=f"neg_{group_name}",
                    suggestion="ネガティブタグを1つに絞ると簡潔になります。",
                )
            )

    return issues
