"""
fps-adapters/comfyui/nodes/face_prompt_wildcard.py
ノード: 🎭 Face Prompt Wildcard  ★v2.6 新設

Wildcard 構文を展開してプロンプトを生成する。
毎回異なるバリエーションを生成することで多様な画像生成が可能。

入力:
  prompt_template STRING  Wildcard 構文を含むプロンプト
  seed            INT     シード（-1 でランダム）
  expand_n        INT     展開バリエーション数（1〜10）
  variables_json  STRING  変数辞書 JSON（例: {"quality":"best_quality"}）

出力:
  expanded_prompt STRING  展開済みプロンプト（expand_n=1 時）
  all_variants    STRING  全バリエーション（改行区切り）
  wildcards_used  STRING  使用された Wildcard キー一覧
  variant_count   INT     生成されたバリエーション数

構文例:
  __style__                    → wildcards/style.json からランダム選択
  [[anime|photorealistic]]     → インラインランダム選択
  [[A|B|C]]:2                  → 2件をランダム選択
  {{quality:masterpiece}}      → 変数展開（デフォルト: masterpiece）
  {soft light|hard light}      → A1111 互換ランダム
"""
from __future__ import annotations

import json
import random
from typing import Any
from .node_base import FPSNodeBase, _get_context


class FacePromptWildcardNode(FPSNodeBase):
    """Wildcard 展開ノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES  = ("expanded_prompt", "all_variants",
                     "wildcards_used", "variant_count")
    FUNCTION      = "expand_wildcards"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "prompt_template": ("STRING", {
                    "multiline": True,
                    "default": "__style__, [[detailed|simple]] background, {{quality:masterpiece}}",
                    "placeholder": "Wildcard 構文を含むプロンプト",
                }),
            },
            "optional": {
                "seed": ("INT", {
                    "default": -1, "min": -1, "max": 2**31 - 1, "step": 1,
                }),
                "expand_n": ("INT", {
                    "default": 1, "min": 1, "max": 10, "step": 1,
                }),
                "variables_json": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "placeholder": '{"quality": "best_quality"}',
                }),
            },
        }

    def expand_wildcards(
        self,
        prompt_template: str,
        seed: int = -1,
        expand_n: int = 1,
        variables_json: str = "",
    ) -> tuple[str, str, str, int]:
        ctx = _get_context()
        if ctx is None:
            return (prompt_template, prompt_template, "", 0)

        # 変数辞書の解析
        variables: dict[str, str] = {}
        if variables_json.strip():
            try:
                variables = json.loads(variables_json)
            except json.JSONDecodeError:
                pass

        # シード決定（-1 = ランダム）
        actual_seed = seed if seed >= 0 else random.randint(0, 2**31 - 1)

        try:
            from wildcard.engine import WildcardEngine  # type: ignore
            wm = ctx.wildcard_manager
            engine = WildcardEngine(wildcard_manager=wm, seed=actual_seed)

            # Wildcard キー一覧を先に収集
            wildcards_used = engine.extract_wildcards(prompt_template)

            # n バリエーション生成
            variants = engine.preview_expand(
                prompt_template, n=expand_n, seed=actual_seed
            )
            if variables:
                from wildcard.engine import WildcardEngine as _WE  # type: ignore
                expanded_variants = []
                for i, v in enumerate(variants):
                    e2 = _WE(wildcard_manager=wm, seed=actual_seed + i)
                    expanded_variants.append(e2.expand(v, variables=variables))
                variants = expanded_variants

            first = variants[0] if variants else prompt_template
            all_v = "
".join(variants)
            wc_str = ", ".join(wildcards_used)

            return (first, all_v, wc_str, len(variants))

        except Exception as e:
            return (prompt_template, prompt_template, f"Error: {e}", 0)
