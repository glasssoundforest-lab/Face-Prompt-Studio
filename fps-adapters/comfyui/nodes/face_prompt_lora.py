"""
fps-adapters/comfyui/nodes/face_prompt_lora.py
ノード: 🎭 Face Prompt LoRA Analyzer  ★v2.5 新設

SafeTensors ファイルを分析してトリガーワード・学習タグを抽出し、
プロンプトに挿入できる文字列として出力する。

入力:
  lora_path     STRING  .safetensors ファイルのフルパス
  metadata_json STRING  CivitAI 等のメタデータ JSON 文字列（ファイル不要）
  top_triggers  INT     出力するトリガーワード数
  include_training BOOL 学習タグも含めるか

出力:
  trigger_tags  STRING  トリガーワード（カンマ区切り）
  all_tags      STRING  全タグ候補（カンマ区切り）
  model_info    STRING  モデル情報（JSON）
  tag_count     INT     タグ候補数
"""
from __future__ import annotations

import json
from typing import Any
from .node_base import FPSNodeBase, _get_context


class FacePromptLoraNode(FPSNodeBase):
    """LoRA ファイルからタグ候補を抽出するノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES  = ("trigger_tags", "all_tags", "model_info", "tag_count")
    FUNCTION      = "analyze_lora"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "lora_path": ("STRING", {
                    "default": "",
                    "placeholder": "/path/to/your_lora.safetensors",
                }),
            },
            "optional": {
                "metadata_json": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "CivitAI メタデータ JSON（ファイル不要）",
                }),
                "top_triggers": ("INT", {
                    "default": 5, "min": 1, "max": 20, "step": 1,
                }),
                "include_training": ("BOOLEAN", {
                    "default": False,
                    "label_on": "学習タグ含む",
                    "label_off": "トリガーのみ",
                }),
            },
        }

    def analyze_lora(
        self,
        lora_path: str,
        metadata_json: str = "",
        top_triggers: int = 5,
        include_training: bool = False,
    ) -> tuple[str, str, str, int]:
        ctx = _get_context()
        if ctx is None:
            return ("", "", '{"error": "Context unavailable"}', 0)

        try:
            analyzer = ctx.ai_manager["lora"]
        except Exception as e:
            return ("", "", json.dumps({"error": str(e)}), 0)

        # 分析実行
        if metadata_json.strip():
            try:
                meta = json.loads(metadata_json)
                info = analyzer.analyze_from_metadata(meta,
                            lora_path.split("/")[-1] or "unknown.safetensors")
            except json.JSONDecodeError as e:
                return ("", "", json.dumps({"error": f"JSON parse error: {e}"}), 0)
        else:
            info = analyzer.analyze(lora_path)

        if not info.success:
            return ("", "", json.dumps({"error": info.error}), 0)

        # トリガーワード
        trigger_str = ", ".join(info.trigger_words[:top_triggers])

        # 全タグ候補
        all_tag_list = info.trigger_words[:top_triggers]
        if include_training:
            all_tag_list += info.training_tags[:20]
        all_str = ", ".join(list(dict.fromkeys(all_tag_list)))

        model_info = json.dumps({
            "file_name":  info.file_name,
            "model_name": info.model_name,
            "base_model": info.base_model,
            "total_tags": info.total_tags,
            "triggers":   info.trigger_words,
        }, ensure_ascii=False, indent=2)

        return (trigger_str, all_str, model_info, info.total_tags)
