"""
fps-adapters/comfyui/nodes/face_prompt_tagger.py
ノード: 🎭 Face Prompt AI Tagger  ★v2.5 新設

WD14-tagger / JoyCaption / Florence2 で画像をタグ付けし、
FPS 辞書と照合して最終的なプロンプトを生成する。

外部タガーが起動していない場合は辞書ベースの提案を返す。

入力:
  image_url     STRING  タグ付けする画像の URL
  current_tags  STRING  既存タグ（補完対象）
  model         ENUM    使用するタガーモデル
  threshold     FLOAT   スコア閾値（0.0〜1.0）
  top_n         INT     出力タグ数

出力:
  suggested_tags   STRING  提案タグ（カンマ区切り）
  merged_prompt    STRING  current_tags + suggested_tags
  tags_json        STRING  タグ + スコアの JSON
  source           STRING  "ai" | "dictionary" | "fallback"
"""
from __future__ import annotations

import json
from typing import Any
from .node_base import FPSNodeBase, _get_context


class FacePromptAITaggerNode(FPSNodeBase):
    """AI タガー連携ノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES  = ("suggested_tags", "merged_prompt", "tags_json", "source")
    FUNCTION      = "run_tagger"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "model": (["dictionary", "wd14", "joycaption", "florence2"], {
                    "default": "dictionary",
                }),
            },
            "optional": {
                "image_url": ("STRING", {
                    "default": "",
                    "placeholder": "http://... または file:///path/to/image.jpg",
                }),
                "current_tags": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "既存タグ（補完対象）",
                }),
                "threshold": ("FLOAT", {
                    "default": 0.35, "min": 0.0, "max": 1.0, "step": 0.05,
                }),
                "top_n": ("INT", {
                    "default": 20, "min": 1, "max": 50, "step": 1,
                }),
            },
        }

    def run_tagger(
        self,
        model: str = "dictionary",
        image_url: str = "",
        current_tags: str = "",
        threshold: float = 0.35,
        top_n: int = 20,
    ) -> tuple[str, str, str, str]:
        ctx = _get_context()
        if ctx is None:
            return ("", current_tags, '{"error":"Context unavailable"}', "error")

        try:
            from ai.tagger_bridge import TaggerModel  # type: ignore
            tagger = ctx.ai_manager["tagger"]
            try:
                m = TaggerModel(model)
            except ValueError:
                m = TaggerModel.DICTIONARY

            current = [t.strip() for t in current_tags.split(",") if t.strip()]

            if image_url.strip():
                result = tagger.tag_image(image_url.strip(), model=m,
                                          threshold=threshold)
            else:
                result = tagger.suggest_from_context(current, n=top_n)

            top_tags = result.top_tags(n=top_n, threshold=threshold)
            suggested = ", ".join(top_tags)

            # current_tags と merge（重複除去）
            merged_list = list(dict.fromkeys(current + top_tags))
            merged = ", ".join(merged_list)

            tags_json = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
            return (suggested, merged, tags_json, result.source)

        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            return ("", current_tags, err, "error")
