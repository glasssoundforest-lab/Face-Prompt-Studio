"""
fps-adapters/comfyui/nodes/face_prompt_compiler.py
ノード: 🎭 Face Prompt Compiler

v2.1 更新:
  - apply_profile BOOLEAN 追加 → UserProfile の除外・追加タグを pos に反映
  - negative_profile BOOLEAN 追加 → always_exclude を neg に追加
  - profile_info STRING 出力追加（除外・追加タグの JSON）

入力:
  prompt           STRING   DSL プロンプト
  negative         STRING   ネガティブプロンプト（省略可）
  preset_id        STRING   プリセット ID（省略可）
  api_version      ENUM     v1 / v2
  max_weight       FLOAT    最大重み
  apply_profile    BOOLEAN  プロファイル適用（★v2.1）
  negative_profile BOOLEAN  exclude を neg に追加（★v2.1）

出力:
  prompt_out    STRING   変換後ポジティブプロンプト
  negative_out  STRING   変換後ネガティブプロンプト
  json_out      STRING   ComfyUI JSON
  tag_count     INT      出力タグ数
  profile_info  STRING   適用結果 JSON（★v2.1）
"""

from __future__ import annotations

import json
from typing import Any

from .node_base import (
    FPSNodeBase,
    _get_pipeline_manager,
    _get_preset_manager,
    _get_upm,
)


class FacePromptCompilerNode(FPSNodeBase):
    """Face Prompt Compiler ノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING", "INT", "STRING")
    RETURN_NAMES  = ("prompt_out", "negative_out", "json_out", "tag_count", "profile_info")
    FUNCTION      = "compile_prompt"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "DSL プロンプト",
                }),
            },
            "optional": {
                "negative": ("STRING", {"multiline": True, "default": ""}),
                "preset_id": ("STRING", {
                    "default": "",
                    "placeholder": "プリセット ID（例: anime_portrait）",
                }),
                "api_version": (["v1", "v2"], {"default": "v1"}),
                "max_weight":  ("FLOAT", {"default": 2.0, "min": 0.5, "max": 3.0, "step": 0.1}),
                "apply_profile":    ("BOOLEAN", {"default": False,
                    "label_on": "Profile ON", "label_off": "Profile OFF"}),
                "negative_profile": ("BOOLEAN", {"default": False,
                    "label_on": "Neg+Exclude ON", "label_off": "Neg+Exclude OFF"}),
            },
        }

    def compile_prompt(
        self,
        prompt: str,
        negative: str = "",
        preset_id: str = "",
        api_version: str = "v1",
        max_weight: float = 2.0,
        apply_profile: bool = False,
        negative_profile: bool = False,
    ) -> tuple[str, str, str, int, str]:
        """
        プロンプトをコンパイルして返す。

        Returns:
            (prompt_out, negative_out, json_out, tag_count, profile_info)
        """
        profile_result: dict[str, Any] = {
            "applied": False, "added_tags": [], "excluded_tags": [],
            "neg_added": [],
        }

        # ── ★v2.1 プロファイル前処理 ────────────────────────
        if apply_profile:
            upm = _get_upm()
            if upm:
                try:
                    original = [t.strip() for t in prompt.split(",") if t.strip()]
                    applied  = upm.apply_profile(original)
                    profile_result["excluded_tags"] = [t for t in original if t not in applied]
                    profile_result["added_tags"]    = [t for t in applied  if t not in original]
                    profile_result["applied"] = True
                    prompt = ", ".join(applied)
                except Exception:
                    pass

        # ── プリセット適用 ───────────────────────────────────
        if preset_id.strip():
            try:
                pm = _get_preset_manager()
                if pm and pm.exists(preset_id.strip()):
                    applied_preset = pm.apply(preset_id.strip())
                    tag_parts = [
                        f"({t['tag']}:{t['weight']:.1f})" if t["weight"] != 1.0 else t["tag"]
                        for t in applied_preset["tags"]
                    ]
                    preset_str = ", ".join(tag_parts)
                    prompt = f"{preset_str}, {prompt}" if prompt.strip() else preset_str
            except Exception:
                pass

        # ── パイプライン実行 ─────────────────────────────────
        pipeline = _get_pipeline_manager(max_weight=max_weight)
        if pipeline is None:
            return prompt, negative, "{}", 0, json.dumps(profile_result)

        result = pipeline.compile(prompt)
        final_negative = negative or result.negative

        # ── ★v2.1 always_exclude を neg に追加 ──────────────
        if negative_profile and apply_profile:
            upm = _get_upm()
            if upm:
                try:
                    p = upm.get_profile()
                    neg_adds: list[str] = []
                    for rule in p.style_rules:
                        if rule.enabled:
                            neg_adds.extend(rule.always_exclude)
                    if neg_adds:
                        existing = {t.strip() for t in final_negative.split(",") if t.strip()}
                        new_neg  = [t for t in neg_adds if t not in existing]
                        if new_neg:
                            sep = ", " if final_negative.strip() else ""
                            final_negative = final_negative.rstrip(", ") + sep + ", ".join(new_neg)
                        profile_result["neg_added"] = neg_adds
                except Exception:
                    pass

        # ── ComfyUI Adapter 変換 ─────────────────────────────
        try:
            from comfyui.adapter import ComfyUIAdapter  # type: ignore[import]
            adapter = ComfyUIAdapter(api_version=api_version)
            output  = adapter.convert(result)
            json_out    = json.dumps(output, ensure_ascii=False, indent=2)
            prompt_out  = output.get("prompt", result.prompt)
        except Exception as e:
            prompt_out = result.prompt
            json_out   = json.dumps(
                {"prompt": result.prompt, "negative_prompt": final_negative, "error": str(e)},
                ensure_ascii=False, indent=2,
            )

        return (
            prompt_out,
            final_negative,
            json_out,
            result.tag_count,
            json.dumps(profile_result, ensure_ascii=False),
        )
