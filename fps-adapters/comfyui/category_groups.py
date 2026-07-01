"""
fps-adapters/comfyui/category_groups.py — カテゴリグループ定義

17の顔特化カテゴリを4つの意味的グループに整理する。
ComfyUI ノードの UI 上でのビジュアルグルーピングおよび
一括ON/OFF切り替えに使用する。
"""

from __future__ import annotations

# グループ名 → 所属カテゴリのマッピング
CATEGORY_GROUPS: dict[str, list[str]] = {
    "quality_style": ["quality", "style"],
    "face_parts": [
        "eyes",
        "eyebrows",
        "eyelashes",
        "face_shape",
        "nose",
        "mouth",
        "teeth",
        "skin",
        "expression",
    ],
    "hair": ["hair"],
    "accessories": ["accessories", "glasses", "piercing", "makeup"],
    "fantasy": ["fantasy_parts"],
}

# 表示用ラベル（日本語）
GROUP_LABELS: dict[str, str] = {
    "quality_style": "品質・画風",
    "face_parts": "顔パーツ",
    "hair": "髪",
    "accessories": "アクセサリー・メイク",
    "fantasy": "ファンタジー",
}

# 全カテゴリ（フラット化、FacePromptCleanerNode 等と共有）
ALL_CATEGORIES: list[str] = [cat for cats in CATEGORY_GROUPS.values() for cat in cats]


def get_group_for_category(category: str) -> str | None:
    """カテゴリ名から所属グループ名を返す（見つからなければ None）"""
    for group, cats in CATEGORY_GROUPS.items():
        if category in cats:
            return group
    return None


def expand_group_to_categories(group_names: list[str]) -> set[str]:
    """グループ名リストから所属する全カテゴリの集合を返す"""
    result: set[str] = set()
    for group in group_names:
        result.update(CATEGORY_GROUPS.get(group, []))
    return result
