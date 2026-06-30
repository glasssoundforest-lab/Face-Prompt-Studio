"""
fps-core/pipeline/category_weights.py — CategoryWeightTable

カテゴリ別デフォルト重みテーブルの読み込み・適用を行う。
WeightEngineStage から利用される。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CategoryWeightTable:
    """
    カテゴリ別重みテーブル管理クラス。

    使い方:
        table = CategoryWeightTable.load("fps-data/rules/category_weights.json")
        scale = table.get_weight("quality")          # → 1.3
        scale = table.get_weight("eyes", preset="quality_focused")  # → 1.0
    """

    def __init__(
        self,
        category_weights: dict[str, float] | None = None,
        presets: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._category_weights: dict[str, float] = category_weights or {}
        self._presets: dict[str, dict[str, Any]] = presets or {}

    # ── Factory ──────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path) -> CategoryWeightTable:
        """JSON ファイルからカテゴリ重みテーブルを読み込む"""
        p = Path(path)
        if not p.exists():
            logger.warning("CategoryWeightTable: file not found: %s", p)
            return cls()

        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return cls(
                category_weights=data.get("category_weights", {}),
                presets=data.get("presets", {}),
            )
        except Exception as e:
            logger.error("CategoryWeightTable: load failed: %s", e)
            return cls()

    @classmethod
    def empty(cls) -> CategoryWeightTable:
        """空のテーブルを生成する（重み倍率は常に 1.0）"""
        return cls()

    # ── Get Weight ───────────────────────────────────────────────

    def get_weight(self, category: str, preset: str | None = None) -> float:
        """
        カテゴリの重み倍率を返す。

        Args:
            category: カテゴリ名（例: "quality"）
            preset:   プリセット名（例: "quality_focused"）。
                      指定があれば overrides で上書きされた値を返す。

        Returns:
            重み倍率（デフォルト 1.0）
        """
        base = self._category_weights.get(category.lower(), 1.0)

        if preset and preset in self._presets:
            preset_data = self._presets[preset]
            overrides = preset_data.get("overrides", {})
            if category.lower() in overrides:
                return float(overrides[category.lower()])
            multiplier = preset_data.get("multiplier", 1.0)
            return round(base * float(multiplier), 3)

        return base

    def apply_to_tags(
        self,
        tags: list[dict[str, Any]],
        preset: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        タグリストにカテゴリ別重みを適用する。

        Args:
            tags:   [{"tag": str, "category": str, "weight": float}, ...]
            preset: 使用するプリセット名

        Returns:
            重み適用後のタグリスト（新しいリストを返す。元は変更しない）
        """
        result = []
        for t in tags:
            new_t = dict(t)
            cat = new_t.get("category", "")
            if cat:
                scale = self.get_weight(cat, preset=preset)
                new_t["weight"] = round(new_t.get("weight", 1.0) * scale, 3)
            result.append(new_t)
        return result

    # ── Metadata ─────────────────────────────────────────────────

    def categories(self) -> list[str]:
        """登録されているカテゴリ一覧を返す"""
        return sorted(self._category_weights.keys())

    def preset_names(self) -> list[str]:
        """登録されているプリセット名一覧を返す"""
        return sorted(self._presets.keys())

    def get_preset_info(self, preset: str) -> dict[str, Any] | None:
        """プリセット情報を返す"""
        return self._presets.get(preset)

    def __repr__(self) -> str:
        return (
            f"CategoryWeightTable("
            f"categories={len(self._category_weights)}, "
            f"presets={list(self._presets.keys())})"
        )
