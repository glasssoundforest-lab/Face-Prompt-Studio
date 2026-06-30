"""
fps-adapters/comfyui/nodes/face_prompt_category_filter.py
ノード: 🎭 Face Prompt Category Filter

機能:
  - プロンプトを解析し、指定カテゴリのタグのみを抽出する
  - 複数カテゴリの選択（カンマ区切り）に対応
  - 抽出/除外の両モードに対応

入力:
  prompt          STRING        入力プロンプト
  categories      STRING        対象カテゴリ（カンマ区切り、例: "eyes,hair"）
  mode            STRING(選択式) "keep_only"（指定カテゴリのみ残す）/
                                 "exclude"（指定カテゴリを除外する）

出力:
  filtered_prompt STRING  フィルタ後プロンプト
  matched_count   INT     マッチしたタグ数
  category_report STRING  カテゴリ別内訳レポート
"""

from __future__ import annotations

from typing import Any

from .node_base import FPSNodeBase, _get_pipeline_manager


class FacePromptCategoryFilterNode(FPSNodeBase):
    """Face Prompt Category Filter ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("filtered_prompt", "matched_count", "category_report")
    FUNCTION = "filter_category"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "フィルタ対象プロンプト",
                    },
                ),
                "categories": (
                    "STRING",
                    {
                        "default": "eyes,hair",
                        "placeholder": "対象カテゴリ（カンマ区切り）",
                    },
                ),
                "mode": (["keep_only", "exclude"], {"default": "keep_only"}),
            },
        }

    def filter_category(
        self,
        prompt: str,
        categories: str = "",
        mode: str = "keep_only",
    ) -> tuple[str, int, str]:
        """
        プロンプトをカテゴリでフィルタリングする。

        Returns:
            (filtered_prompt, matched_count, category_report)
        """
        target_categories = {c.strip().lower() for c in categories.split(",") if c.strip()}

        pm = _get_pipeline_manager()
        if pm is None:
            return "", 0, "[ERROR] PipelineManager の初期化に失敗しました。"

        result = pm.compile(prompt)

        if mode == "keep_only":
            filtered = [t for t in result.tags if t.category.lower() in target_categories]
        else:  # exclude
            filtered = [t for t in result.tags if t.category.lower() not in target_categories]

        parts = []
        for t in filtered:
            resolved = t.meta.get("resolved") or t.tag
            if t.weight != 1.0:
                parts.append(f"({resolved}:{t.weight:.2f})")
            else:
                parts.append(resolved)

        filtered_prompt = ", ".join(parts)
        matched_count = len(filtered)

        # ── カテゴリ別内訳レポート ────────────────────────
        report_lines = [
            "=== Category Filter Report ===",
            f"Mode       : {mode}",
            f"Categories : {', '.join(sorted(target_categories)) or '(none specified)'}",
            f"Input tags : {len(result.tags)}",
            f"Matched    : {matched_count}",
            "",
            "--- All Categories in Input ---",
        ]

        all_cats: dict[str, int] = {}
        for t in result.tags:
            c = t.category or "uncategorized"
            all_cats[c] = all_cats.get(c, 0) + 1

        for c in sorted(all_cats.keys()):
            marker = "✓" if c.lower() in target_categories else " "
            report_lines.append(f"  [{marker}] {c:<16} {all_cats[c]} tags")

        category_report = "\n".join(report_lines)

        return filtered_prompt, matched_count, category_report
