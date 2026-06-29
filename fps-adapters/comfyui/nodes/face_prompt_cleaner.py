"""
fps-adapters/comfyui/nodes/face_prompt_cleaner.py
ノード: 🎭 Face Prompt Cleaner

機能:
  - テキストプロンプトをクリーニング（重複除去・ブラックリスト・正規化）
  - カテゴリ別のオン/オフスイッチ
  - カテゴリ別の重み調整
  - ネガティブプロンプトのパススルー

入力:
  prompt          STRING  クリーニング対象プロンプト
  negative        STRING  ネガティブプロンプト（パススルー）
  keep_quality    BOOLEAN quality タグを保持するか
  keep_eyes       BOOLEAN eyes タグを保持するか
  keep_hair       BOOLEAN hair タグを保持するか
  keep_style      BOOLEAN style タグを保持するか
  weight_quality  FLOAT   quality カテゴリの重みスケール
  weight_eyes     FLOAT   eyes カテゴリの重みスケール
  weight_hair     FLOAT   hair カテゴリの重みスケール
  blacklist_extra STRING  追加ブラックリスト（カンマ区切り）

出力:
  cleaned_prompt  STRING  クリーニング後プロンプト
  negative        STRING  ネガティブプロンプト（パススルー）
  tag_count       INT     出力タグ数
  debug_text      STRING  デバッグ情報
"""

from __future__ import annotations

from typing import Any

from .node_base import FPSNodeBase, _get_pipeline_manager


class FacePromptCleanerNode(FPSNodeBase):
    """Face Prompt Cleaner ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("cleaned_prompt", "negative", "tag_count", "debug_text")
    FUNCTION = "clean"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "入力プロンプト（DSL 形式または通常テキスト）",
                    },
                ),
            },
            "optional": {
                "negative": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "ネガティブプロンプト（パススルー）",
                    },
                ),
                # ── カテゴリスイッチ ──────────────────────────
                "keep_quality": ("BOOLEAN", {"default": True}),
                "keep_eyes": ("BOOLEAN", {"default": True}),
                "keep_hair": ("BOOLEAN", {"default": True}),
                "keep_style": ("BOOLEAN", {"default": True}),
                # ── カテゴリ重みスケール ──────────────────────
                "weight_quality": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 3.0,
                        "step": 0.05,
                    },
                ),
                "weight_eyes": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 3.0,
                        "step": 0.05,
                    },
                ),
                "weight_hair": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 3.0,
                        "step": 0.05,
                    },
                ),
                "weight_style": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 3.0,
                        "step": 0.05,
                    },
                ),
                # ── 追加設定 ─────────────────────────────────
                "blacklist_extra": (
                    "STRING",
                    {
                        "default": "",
                        "placeholder": "追加ブラックリスト（カンマ区切り）",
                    },
                ),
                "max_weight": (
                    "FLOAT",
                    {
                        "default": 2.0,
                        "min": 0.5,
                        "max": 3.0,
                        "step": 0.1,
                    },
                ),
            },
        }

    def clean(
        self,
        prompt: str,
        negative: str = "",
        keep_quality: bool = True,
        keep_eyes: bool = True,
        keep_hair: bool = True,
        keep_style: bool = True,
        weight_quality: float = 1.0,
        weight_eyes: float = 1.0,
        weight_hair: float = 1.0,
        weight_style: float = 1.0,
        blacklist_extra: str = "",
        max_weight: float = 2.0,
    ) -> tuple[str, str, int, str]:
        """
        プロンプトをクリーニングして返す。

        Returns:
            (cleaned_prompt, negative, tag_count, debug_text)
        """
        # ── ブラックリスト構築 ─────────────────────────────
        blacklist: set[str] = set()

        # カテゴリスイッチ OFF のカテゴリをブラックリスト化（後段 categorizer 後に除去）
        # ここでは Pipeline の blacklist stage に渡す追加タグを処理する
        if blacklist_extra.strip():
            blacklist.update(
                t.strip().lower().replace(" ", "_") for t in blacklist_extra.split(",") if t.strip()
            )

        # ── パイプライン実行 ───────────────────────────────
        pm = _get_pipeline_manager(
            blacklist=blacklist or None,
            max_weight=max_weight,
        )

        if pm is None:
            debug = "[ERROR] PipelineManager の初期化に失敗しました。"
            return prompt, negative, 0, debug

        result = pm.compile(prompt)

        # ── カテゴリスイッチ・重みスケール適用 ────────────
        category_switches = {
            "quality": keep_quality,
            "eyes": keep_eyes,
            "hair": keep_hair,
            "style": keep_style,
        }
        category_weights = {
            "quality": weight_quality,
            "eyes": weight_eyes,
            "hair": weight_hair,
            "style": weight_style,
        }

        filtered_tags = []
        for tag in result.tags:
            cat = tag.category.lower() if tag.category else ""
            # カテゴリスイッチ OFF なら除外
            if cat in category_switches and not category_switches[cat]:
                continue
            # 重みスケール適用
            if cat in category_weights:
                tag.weight = round(tag.weight * category_weights[cat], 3)
            filtered_tags.append(tag)

        # ── 出力プロンプト生成 ─────────────────────────────
        parts: list[str] = []
        for t in filtered_tags:
            resolved = t.meta.get("resolved") or t.tag
            if t.weight != 1.0:
                parts.append(f"({resolved}:{t.weight:.2f})")
            else:
                parts.append(resolved)

        cleaned_prompt = ", ".join(parts)
        tag_count = len(filtered_tags)

        # ── デバッグ情報 ──────────────────────────────────
        debug_lines = [
            "=== Face Prompt Cleaner Debug ===",
            f"Input tags  : {len(result.tags) + len(result.negative_tags)}",
            f"Output tags : {tag_count}",
            f"Negative    : {len(result.negative_tags)}",
            "",
            "--- Stage Results ---",
        ]
        for sr in result.stage_results:
            status = sr.status.upper() if hasattr(sr.status, "upper") else str(sr.status)
            debug_lines.append(
                f"  {sr.stage:<20} {status:<8} " f"{sr.tags_in:>3} → {sr.tags_out:>3} tags"
            )

        debug_lines += [
            "",
            "--- Output Tags ---",
        ]
        for t in filtered_tags:
            resolved = t.meta.get("resolved") or t.tag
            debug_lines.append(f"  [{t.category:<12}] {resolved} (weight={t.weight:.2f})")

        if result.errors:
            debug_lines += ["", "--- Errors ---"]
            debug_lines.extend(f"  {e}" for e in result.errors)

        debug_text = "\n".join(debug_lines)

        return cleaned_prompt, negative, tag_count, debug_text
