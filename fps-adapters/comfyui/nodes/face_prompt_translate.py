"""
fps-adapters/comfyui/nodes/face_prompt_translate.py
ノード: 🎭 Face Prompt Translate  ★v2.9 新設

日本語テキストを英語タグリストに変換する。
辞書ベースで動作するため外部APIは不要。

入力:
  japanese_text  STRING  日本語テキスト（例: "青い目の金髪の少女、笑顔"）
  append_to      STRING  変換後に追加する既存プロンプト
  max_tags       INT     最大タグ数

出力:
  translated_tags  STRING  変換されたタグ（カンマ区切り）
  merged_prompt    STRING  append_to + translated_tags
  unmapped         STRING  変換できなかった単語
  confidence       FLOAT   変換率（0.0〜1.0）
"""
from __future__ import annotations
from typing import Any
from .node_base import FPSNodeBase, _get_context


class FacePromptTranslateNode(FPSNodeBase):
    """日本語→タグ翻訳ノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING", "FLOAT")
    RETURN_NAMES  = ("translated_tags", "merged_prompt", "unmapped", "confidence")
    FUNCTION      = "translate"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "japanese_text": ("STRING", {
                    "multiline": True,
                    "default":   "青い目の金髪の少女、笑顔、アニメ風",
                    "placeholder": "日本語テキストを入力...",
                }),
            },
            "optional": {
                "append_to": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "追加先のプロンプト（省略可）",
                }),
                "max_tags": ("INT", {
                    "default": 20, "min": 1, "max": 50, "step": 1,
                }),
            },
        }

    def translate(
        self,
        japanese_text: str,
        append_to:     str = "",
        max_tags:      int = 20,
    ) -> tuple[str, str, str, float]:
        ctx = _get_context()
        if ctx is None:
            return (japanese_text, japanese_text, "", 0.0)
        try:
            engine = ctx.translate_engine
            result = engine.translate(japanese_text, max_tags=max_tags)
            translated = result.to_prompt()
            # append_to と結合（重複除去）
            if append_to.strip():
                existing = {t.strip().lower()
                            for t in append_to.split(",") if t.strip()}
                new_tags = [t for t in result.tags
                            if t.lower() not in existing]
                merged   = append_to.rstrip(", ") + (", " if new_tags else "")                            + ", ".join(new_tags)
            else:
                merged = translated
            unmapped_str = ", ".join(result.unmapped) if result.unmapped else ""
            return (translated, merged, unmapped_str, result.confidence)
        except Exception as e:
            return (f"Error: {e}", japanese_text, "", 0.0)
