"""
fps-tools/tests/unit/test_category_groups.py

category_groups.py のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_category_groups.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from comfyui.category_groups import (
    ALL_CATEGORIES,
    CATEGORY_GROUPS,
    GROUP_LABELS,
    expand_group_to_categories,
    get_group_for_category,
)


class TestCategoryGroups:
    def test_five_groups_defined(self):
        assert len(CATEGORY_GROUPS) == 5

    def test_all_categories_have_labels(self):
        for group in CATEGORY_GROUPS:
            assert group in GROUP_LABELS

    def test_no_duplicate_categories_across_groups(self):
        seen = set()
        for cats in CATEGORY_GROUPS.values():
            for c in cats:
                assert c not in seen, f"カテゴリ '{c}' が複数グループに重複しています"
                seen.add(c)

    def test_all_categories_total_seventeen(self):
        assert len(ALL_CATEGORIES) == 17

    def test_face_parts_group_has_nine_categories(self):
        assert len(CATEGORY_GROUPS["face_parts"]) == 9

    def test_hair_group_is_standalone(self):
        assert CATEGORY_GROUPS["hair"] == ["hair"]


class TestGetGroupForCategory:
    def test_eyes_belongs_to_face_parts(self):
        assert get_group_for_category("eyes") == "face_parts"

    def test_hair_belongs_to_hair_group(self):
        assert get_group_for_category("hair") == "hair"

    def test_fantasy_parts_belongs_to_fantasy(self):
        assert get_group_for_category("fantasy_parts") == "fantasy"

    def test_unknown_category_returns_none(self):
        assert get_group_for_category("nonexistent_category") is None


class TestExpandGroupToCategories:
    def test_single_group_expansion(self):
        result = expand_group_to_categories(["hair"])
        assert result == {"hair"}

    def test_multiple_groups_expansion(self):
        result = expand_group_to_categories(["hair", "fantasy"])
        assert result == {"hair", "fantasy_parts"}

    def test_unknown_group_ignored(self):
        result = expand_group_to_categories(["nonexistent_group"])
        assert result == set()

    def test_empty_list_returns_empty_set(self):
        assert expand_group_to_categories([]) == set()
