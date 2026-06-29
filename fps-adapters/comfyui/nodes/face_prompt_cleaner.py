"""
fps-adapters/comfyui/nodes/face_prompt_cleaner.py
ノード: 🎭 Face Prompt Cleaner

機能:
  - テキストプロンプトのクリーニング（重複除去・ブラックリスト・正規化）
  - 顔特化 15 カテゴリのオン/オフスイッチ
  - カテゴリ別の重み調整
  - ネガティブプロンプトのパススルー
  - デバッグ情報出力

出力:
  cleaned_prompt  STRING  クリーニング後プロンプト
  negative        STRING  ネガティブプロンプト（パススルー）
  tag_count       INT     出力タグ数
  debug_text      STRING  デバッグ情報
"""

from __future__ import annotations

from typing import Any

from .node_base import FPSNodeBase, _get_pipeline_manager

# 顔特化 15 カテゴリ
FACE_CATEGORIES = [
    "quality", "eyes", "eyebrows", "eyelashes", "face_shape",
    "nose", "mouth", "teeth", "skin", "expression",
    "accessories", "glasses", "piercing", "makeup", "fantasy_parts",
    "hair", "style",
]


class FacePromptCleanerNode(FPSNodeBase):
    """Face Prompt Cleaner ノード（15カテゴリ対応）"""

    CATEGORY     = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("cleaned_prompt", "negative", "tag_count", "debug_text")
    FUNCTION     = "clean"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        # カテゴリスイッチを動的に生成
        cat_switches: dict[str, Any] = {}
        for cat in FACE_CATEGORIES:
            cat_switches[f"keep_{cat}"] = ("BOOLEAN", {"default": True})

        # 重み調整（主要カテゴリのみ）
        weight_inputs: dict[str, Any] = {}
        for cat in ["quality", "eyes", "hair", "expression", "skin", "makeup"]:
            weight_inputs[f"weight_{cat}"] = ("FLOAT", {
                "default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05,
            })

        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default":   "",
                    "placeholder": "入力プロンプト（DSL または通常テキスト）",
                }),
            },
            "optional": {
                "negative": ("STRING", {
                    "multiline": True,
                    "default":   "",
                    "placeholder": "ネガティブプロンプト（パススルー）",
                }),
                **cat_switches,
                **weight_inputs,
                "blacklist_extra": ("STRING", {
                    "default":     "",
                    "placeholder": "追加ブラックリスト（カンマ区切り）",
                }),
                "max_weight": ("FLOAT", {
                    "default": 2.0, "min": 0.5, "max": 3.0, "step": 0.1,
                }),
            },
        }

    def clean(
        self,
        prompt:           str,
        negative:         str   = "",
        # カテゴリスイッチ（全15カテゴリ + hair + style）
        keep_quality:     bool  = True,
        keep_eyes:        bool  = True,
        keep_eyebrows:    bool  = True,
        keep_eyelashes:   bool  = True,
        keep_face_shape:  bool  = True,
        keep_nose:        bool  = True,
        keep_mouth:       bool  = True,
        keep_teeth:       bool  = True,
        keep_skin:        bool  = True,
        keep_expression:  bool  = True,
        keep_accessories: bool  = True,
        keep_glasses:     bool  = True,
        keep_piercing:    bool  = True,
        keep_makeup:      bool  = True,
        keep_fantasy_parts: bool = True,
        keep_hair:        bool  = True,
        keep_style:       bool  = True,
        # カテゴリ別重みスケール
        weight_quality:   float = 1.0,
        weight_eyes:      float = 1.0,
        weight_hair:      float = 1.0,
        weight_expression: float = 1.0,
        weight_skin:      float = 1.0,
        weight_makeup:    float = 1.0,
        # その他
        blacklist_extra:  str   = "",
        max_weight:       float = 2.0,
    ) -> tuple[str, str, int, str]:
        """
        プロンプトをクリーニングして返す。

        Returns:
            (cleaned_prompt, negative, tag_count, debug_text)
        """
        # ── カテゴリスイッチマップ ────────────────────────────
        category_switches = {
            "quality":      keep_quality,
            "eyes":         keep_eyes,
            "eyebrows":     keep_eyebrows,
            "eyelashes":    keep_eyelashes,
            "face_shape":   keep_face_shape,
            "nose":         keep_nose,
            "mouth":        keep_mouth,
            "teeth":        keep_teeth,
            "skin":         keep_skin,
            "expression":   keep_expression,
            "accessories":  keep_accessories,
            "glasses":      keep_glasses,
            "piercing":     keep_piercing,
            "makeup":       keep_makeup,
            "fantasy_parts":keep_fantasy_parts,
            "hair":         keep_hair,
            "style":        keep_style,
        }

        # ── カテゴリ重みスケールマップ ────────────────────────
        category_weights = {
            "quality":    weight_quality,
            "eyes":       weight_eyes,
            "hair":       weight_hair,
            "expression": weight_expression,
            "skin":       weight_skin,
            "makeup":     weight_makeup,
        }

        # ── 追加ブラックリスト構築 ────────────────────────────
        blacklist: set[str] = set()
        if blacklist_extra.strip():
            blacklist.update(
                t.strip().lower().replace(" ", "_")
                for t in blacklist_extra.split(",")
                if t.strip()
            )

        # ── パイプライン実行 ──────────────────────────────────
        pm = _get_pipeline_manager(
            blacklist  = blacklist or None,
            max_weight = max_weight,
        )

        if pm is None:
            debug = "[ERROR] PipelineManager の初期化に失敗しました。"
            return prompt, negative, 0, debug

        result = pm.compile(prompt)

        # ── カテゴリスイッチ・重みスケール適用 ────────────────
        filtered_tags = []
        skipped_tags  = []
        for tag in result.tags:
            cat = tag.category.lower() if tag.category else ""
            if cat in category_switches and not category_switches[cat]:
                skipped_tags.append(tag)
                continue
            if cat in category_weights:
                tag.weight = round(tag.weight * category_weights[cat], 3)
            filtered_tags.append(tag)

        # ── 出力プロンプト生成 ────────────────────────────────
        parts: list[str] = []
        for t in filtered_tags:
            resolved = t.meta.get("resolved") or t.tag
            if t.weight != 1.0:
                parts.append(f"({resolved}:{t.weight:.2f})")
            else:
                parts.append(resolved)

        cleaned_prompt = ", ".join(parts)
        tag_count      = len(filtered_tags)

        # ── デバッグ情報 ──────────────────────────────────────
        debug_lines = [
            "=== Face Prompt Cleaner Debug ===",
            f"Input    : {prompt[:60]}{'...' if len(prompt)>60 else ''}",
            f"Output   : {cleaned_prompt[:60]}{'...' if len(cleaned_prompt)>60 else ''}",
            f"Tags In  : {len(result.tags) + len(result.negative_tags)}",
            f"Tags Out : {tag_count}",
            f"Skipped  : {len(skipped_tags)} (category switch OFF)",
            f"Negative : {len(result.negative_tags)}",
            "",
            "--- Stage Results ---",
        ]
        for sr in result.stage_results:
            status = str(sr.status).upper().replace("STAGESTATUS.", "")
            debug_lines.append(
                f"  {sr.stage:<22} {status:<8} {sr.tags_in:>3} → {sr.tags_out:>3}"
            )

        debug_lines += ["", "--- Output Tags ---"]
        for t in filtered_tags:
            resolved = t.meta.get("resolved") or t.tag
            debug_lines.append(
                f"  [{t.category or 'unknown':<14}] {resolved}  (w={t.weight:.2f})"
            )

        if skipped_tags:
            debug_lines += ["", "--- Skipped Tags (category OFF) ---"]
            for t in skipped_tags:
                debug_lines.append(f"  [{t.category:<14}] {t.tag}")

        if result.errors:
            debug_lines += ["", "--- Errors ---"]
            debug_lines.extend(f"  {e}" for e in result.errors)

        debug_text = "\n".join(debug_lines)
        return cleaned_prompt, negative, tag_count, debug_text
