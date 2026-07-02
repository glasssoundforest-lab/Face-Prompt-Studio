"""
fps-adapters/comfyui/nodes/face_prompt_export.py
ノード: 🎭 Face Prompt Export  ★v2.8 新設

pos/neg プロンプトを複数形式でエクスポートする。
A1111/NovelAI/JSON/YAML/CSV に変換して文字列で返す。

入力:
  pos_prompt  STRING  ポジティブプロンプト
  neg_prompt  STRING  ネガティブプロンプト
  format      ENUM    出力形式
  label       STRING  エクスポートラベル（ファイル名のベース）
  steps       INT     ステップ数（A1111）
  cfg         FLOAT   CFG スケール（A1111）

出力:
  exported    STRING  変換後コンテンツ
  filename    STRING  推奨ファイル名
  mime_type   STRING  MIME タイプ
"""
from __future__ import annotations
from typing import Any
from .node_base import FPSNodeBase, _get_context


class FacePromptExportNode(FPSNodeBase):
    """マルチフォーマット エクスポートノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING")
    RETURN_NAMES  = ("exported", "filename", "mime_type")
    FUNCTION      = "export_prompt"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "pos_prompt": ("STRING", {"multiline": True, "default": ""}),
                "format": (["a1111", "novelai", "json", "yaml"], {"default": "a1111"}),
            },
            "optional": {
                "neg_prompt": ("STRING", {"multiline": True, "default": ""}),
                "label":  ("STRING", {"default": "export"}),
                "steps":  ("INT",   {"default": 20, "min": 1, "max": 150}),
                "cfg":    ("FLOAT", {"default": 7.0, "min": 1.0, "max": 30.0, "step": 0.5}),
                "width":  ("INT",   {"default": 512, "min": 64, "max": 4096, "step": 64}),
                "height": ("INT",   {"default": 512, "min": 64, "max": 4096, "step": 64}),
                "seed":   ("INT",   {"default": -1, "min": -1, "max": 2**31-1}),
            },
        }

    def export_prompt(
        self,
        pos_prompt: str,
        format:     str   = "a1111",
        neg_prompt: str   = "",
        label:      str   = "export",
        steps:      int   = 20,
        cfg:        float = 7.0,
        width:      int   = 512,
        height:     int   = 512,
        seed:       int   = -1,
    ) -> tuple[str, str, str]:
        try:
            from export.exporters import (  # type: ignore
                A1111Exporter, NovelAIExporter, get_exporter
            )
            import json as _json

            if format == "a1111":
                exporter = A1111Exporter(
                    steps=steps, cfg=cfg, width=width, height=height, seed=seed
                )
            elif format == "novelai":
                exporter = NovelAIExporter()
            elif format == "json":
                content = _json.dumps({
                    "pos": pos_prompt, "neg": neg_prompt,
                    "label": label, "format": "fps_native",
                }, ensure_ascii=False, indent=2)
                return (content, f"{label}.json", "application/json")
            elif format == "yaml":
                lines = [
                    f"# FacePromptStudio — {label}",
                    f"label: {label}",
                    "positive: |",
                    *[f"  {l}" for l in pos_prompt.split("
")],
                    "negative: |",
                    *[f"  {l}" for l in neg_prompt.split("
")],
                ]
                return ("
".join(lines), f"{label}.yaml", "text/yaml")
            else:
                return (pos_prompt, "prompt.txt", "text/plain")

            result = exporter.export(pos_prompt, neg_prompt)
            return (result.content, result.filename, result.mime_type)
        except Exception as e:
            return (f"Error: {e}", "error.txt", "text/plain")
