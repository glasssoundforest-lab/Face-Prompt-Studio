"""
fps-adapters/comfyui/nodes/face_prompt_compiler.py
ノード: 🎭 Face Prompt Compiler

機能:
  - DSL 形式プロンプトをフルコンパイル
  - ComfyUI v1 / v2 形式で出力
  - プリセットの適用
  - 辞書・ルール・パイプライン全段階を経由した完全変換

入力:
  prompt         STRING  DSL プロンプト
  negative       STRING  ネガティブプロンプト
  preset_id      STRING  適用するプリセット ID（省略可）
  api_version    STRING  ComfyUI API バージョン（v1 / v2）
  max_weight     FLOAT   最大重み

出力:
  prompt_out     STRING  変換後プロンプト
  negative_out   STRING  変換後ネガティブプロンプト
  json_out       STRING  ComfyUI JSON 文字列
  tag_count      INT     出力タグ数
"""

from __future__ import annotations

import sys
from typing import Any

from .node_base import _ROOT, FPSNodeBase, _get_pipeline_manager

# fps-adapters を追加
_ADAPTERS = _ROOT / "fps-adapters"
if str(_ADAPTERS) not in sys.path:
    sys.path.insert(0, str(_ADAPTERS))


class FacePromptCompilerNode(FPSNodeBase):
    """Face Prompt Compiler ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("prompt_out", "negative_out", "json_out", "tag_count")
    FUNCTION = "compile_prompt"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "DSL プロンプト",
                    },
                ),
            },
            "optional": {
                "negative": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                    },
                ),
                "preset_id": (
                    "STRING",
                    {
                        "default": "",
                        "placeholder": "プリセット ID（例: anime_portrait）",
                    },
                ),
                "api_version": (["v1", "v2"], {"default": "v1"}),
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

    def compile_prompt(
        self,
        prompt: str,
        negative: str = "",
        preset_id: str = "",
        api_version: str = "v1",
        max_weight: float = 2.0,
    ) -> tuple[str, str, str, int]:
        """
        プロンプトをコンパイルして返す。

        Returns:
            (prompt_out, negative_out, json_out, tag_count)
        """
        import json

        # ── プリセット適用 ─────────────────────────────────
        base_prompt = prompt
        if preset_id.strip():
            try:
                from preset.manager import PresetManager

                data_root = _ROOT / "fps-data" / "presets"
                pm = PresetManager(
                    system_dir=data_root / "system",
                    user_dir=data_root / "user",
                )
                pm.load()
                if pm.exists(preset_id.strip()):
                    applied = pm.apply(preset_id.strip())
                    tag_parts = [
                        f"({t['tag']}:{t['weight']:.1f})" if t["weight"] != 1.0 else t["tag"]
                        for t in applied["tags"]
                    ]
                    preset_str = ", ".join(tag_parts)
                    base_prompt = f"{preset_str}, {prompt}" if prompt.strip() else preset_str
            except Exception:
                pass  # プリセット失敗時はそのまま続行

        # ── パイプライン実行 ───────────────────────────────
        pipeline = _get_pipeline_manager(max_weight=max_weight)
        if pipeline is None:
            return prompt, negative, "{}", 0

        result = pipeline.compile(base_prompt)

        # ── ComfyUI Adapter 変換 ──────────────────────────
        try:
            from comfyui.adapter import ComfyUIAdapter

            adapter = ComfyUIAdapter(api_version=api_version)
            output = adapter.convert(result)
            json_out = json.dumps(output, ensure_ascii=False, indent=2)
            prompt_out = output.get("prompt", result.prompt)
            negative_out = negative or result.negative
        except Exception as e:
            prompt_out = result.prompt
            negative_out = negative or result.negative
            json_out = json.dumps(
                {
                    "prompt": result.prompt,
                    "negative_prompt": negative_out,
                    "error": str(e),
                },
                ensure_ascii=False,
                indent=2,
            )

        return prompt_out, negative_out, json_out, result.tag_count
