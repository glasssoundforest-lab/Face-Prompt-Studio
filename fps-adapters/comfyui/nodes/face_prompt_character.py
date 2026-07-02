"""
fps-adapters/comfyui/nodes/face_prompt_character.py
ノード: 🎭 Face Prompt Character  ★v2.7 新設

キャラクターシートから pos / neg プロンプトを生成する。
キャラクターの一貫性を保ちながら複数枚生成する際に使用。

入力:
  character_id  STRING  キャラクター ID（fps-data/characters/ に保存されたもの）
  extra_tags    STRING  追加タグ（カンマ区切り）
  extra_neg     STRING  追加ネガティブ（カンマ区切り）
  apply_wildcard BOOL   追加タグの Wildcard 構文を展開するか

出力:
  pos_prompt    STRING  キャラクター特徴 + extra_tags
  neg_prompt    STRING  キャラクターの neg + extra_neg
  character_info STRING キャラクター情報（JSON）
  feature_count INT     特徴タグ数
"""
from __future__ import annotations
import json
from typing import Any
from .node_base import FPSNodeBase, _get_context


class FacePromptCharacterNode(FPSNodeBase):
    """キャラクターシート → pos/neg プロンプト生成ノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES  = ("pos_prompt", "neg_prompt", "character_info", "feature_count")
    FUNCTION      = "build_prompt"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "character_id": ("STRING", {
                    "default": "",
                    "placeholder": "キャラクター ID（例: alice）",
                }),
            },
            "optional": {
                "extra_tags": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "追加タグ（カンマ区切り or Wildcard 構文）",
                }),
                "extra_neg": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "追加ネガティブ（カンマ区切り）",
                }),
                "apply_wildcard": ("BOOLEAN", {
                    "default": False,
                    "label_on": "Wildcard展開ON",
                    "label_off": "Wildcard展開OFF",
                }),
            },
        }

    def build_prompt(
        self,
        character_id: str,
        extra_tags:   str = "",
        extra_neg:    str = "",
        apply_wildcard: bool = False,
    ) -> tuple[str, str, str, int]:
        ctx = _get_context()
        if ctx is None:
            return (extra_tags, extra_neg, '{"error":"Context unavailable"}', 0)

        cid = character_id.strip()
        if not cid:
            return (extra_tags, extra_neg, '{"error":"character_id が空です"}', 0)

        try:
            cm   = ctx.character_manager
            char = cm.get(cid)
        except Exception as e:
            return (extra_tags, extra_neg, json.dumps({"error": str(e)}), 0)

        if char is None:
            return (
                extra_tags, extra_neg,
                json.dumps({"error": f"キャラクター '{cid}' が見つかりません"}),
                0,
            )

        # pos プロンプト構築
        char_pos = char.to_pos_prompt()
        extra    = extra_tags.strip()

        # Wildcard 展開
        if apply_wildcard and extra:
            try:
                from wildcard.engine import WildcardEngine  # type: ignore
                engine = WildcardEngine(wildcard_manager=ctx.wildcard_manager)
                extra  = engine.expand(extra)
            except Exception:
                pass

        pos_parts = [p for p in [char_pos, extra] if p]
        pos_prompt = ", ".join(pos_parts)

        # neg プロンプト構築
        char_neg = char.to_neg_prompt()
        neg_extra = extra_neg.strip()
        neg_parts = [p for p in [char_neg, neg_extra] if p]
        neg_prompt = ", ".join(neg_parts)

        info = json.dumps({
            "id":          char.id,
            "name":        char.name,
            "description": char.description,
            "feature_count": len(char.features),
            "tag_count":   len(char.tags),
        }, ensure_ascii=False, indent=2)

        return (pos_prompt, neg_prompt, info, len(char.features))
