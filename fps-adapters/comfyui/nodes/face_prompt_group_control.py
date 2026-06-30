"""
fps-adapters/comfyui/nodes/face_prompt_group_control.py
ノード: 🎭 Face Prompt Group Control

機能:
  - 17カテゴリを5グループ（品質・画風／顔パーツ／髪／
    アクセサリー・メイク／ファンタジー）に整理し、
    グループ単位でON/OFF・重み調整を行う
  - FacePromptCleanerNode の17個のBOOLEAN入力を、
    5個のグループスイッチ + 5個の重みスライダーに集約することで
    ノードの視覚的な複雑さを大幅に削減する

出力:
  cleaned_prompt  STRING  クリーニング後プロンプト
  negative        STRING  ネガティブプロンプト
  tag_count       INT     出力タグ数
  group_report    STRING  グループ別の適用状況レポート
"""

from __future__ import annotations

from typing import Any

from ..category_groups import CATEGORY_GROUPS, GROUP_LABELS
from .node_base import FPSNodeBase, _get_pipeline_manager


class FacePromptGroupControlNode(FPSNodeBase):
    """Face Prompt Group Control ノード（5グループ集約版）"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("cleaned_prompt", "negative", "tag_count", "group_report")
    FUNCTION = "clean_by_group"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        group_switches: dict[str, Any] = {}
        weight_inputs: dict[str, Any] = {}

        for group in CATEGORY_GROUPS:
            group_switches[f"group_{group}"] = ("BOOLEAN", {"default": True})
            weight_inputs[f"weight_{group}"] = (
                "FLOAT",
                {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05},
            )

        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "入力プロンプト（DSL または通常テキスト）",
                    },
                ),
            },
            "optional": {
                **group_switches,
                **weight_inputs,
                "max_weight": (
                    "FLOAT",
                    {"default": 2.0, "min": 0.5, "max": 3.0, "step": 0.1},
                ),
            },
        }

    def clean_by_group(
        self,
        prompt: str,
        max_weight: float = 2.0,
        **kwargs: Any,
    ) -> tuple[str, str, int, str]:
        """
        グループ単位でカテゴリスイッチ・重みを適用してクリーニングする。

        Returns:
            (cleaned_prompt, negative, tag_count, group_report)
        """
        group_enabled: dict[str, bool] = {}
        group_weights: dict[str, float] = {}
        for group in CATEGORY_GROUPS:
            group_enabled[group] = kwargs.get(f"group_{group}", True)
            group_weights[group] = kwargs.get(f"weight_{group}", 1.0)

        category_enabled: dict[str, bool] = {}
        category_weight: dict[str, float] = {}
        for group, categories in CATEGORY_GROUPS.items():
            for cat in categories:
                category_enabled[cat] = group_enabled[group]
                category_weight[cat] = group_weights[group]

        pm = _get_pipeline_manager(max_weight=max_weight)
        if pm is None:
            return prompt, "", 0, "[ERROR] PipelineManager の初期化に失敗しました。"

        result = pm.compile(prompt)

        filtered_tags = []
        skipped_tags = []
        for tag in result.tags:
            cat = tag.category.lower() if tag.category else ""
            if cat in category_enabled and not category_enabled[cat]:
                skipped_tags.append(tag)
                continue
            if cat in category_weight:
                tag.weight = round(tag.weight * category_weight[cat], 3)
            filtered_tags.append(tag)

        parts: list[str] = []
        for t in filtered_tags:
            resolved = t.meta.get("resolved") or t.tag
            if t.weight != 1.0:
                parts.append(f"({resolved}:{t.weight:.2f})")
            else:
                parts.append(resolved)

        cleaned_prompt = ", ".join(parts)
        negative = ", ".join(t.tag for t in result.negative_tags)
        tag_count = len(filtered_tags)

        report_lines = ["=== Face Prompt Group Control Report ===", ""]
        for group, categories in CATEGORY_GROUPS.items():
            label = GROUP_LABELS.get(group, group)
            status = "ON " if group_enabled[group] else "OFF"
            weight = group_weights[group]
            cat_tags = [t for t in filtered_tags if t.category in categories]
            report_lines.append(
                f"  [{status}] {label:<14} (weight x{weight:.2f})  "
                f"categories={','.join(categories)}  tags={len(cat_tags)}"
            )

        if skipped_tags:
            report_lines += ["", "--- Skipped (group OFF) ---"]
            for t in skipped_tags:
                report_lines.append(f"  [{t.category}] {t.tag}")

        group_report = "\n".join(report_lines)

        return cleaned_prompt, negative, tag_count, group_report
