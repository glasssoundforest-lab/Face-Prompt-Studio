"""
fps-adapters/comfyui/nodes/face_prompt_batch.py
ノード: 🎭 Face Prompt Batch  ★v2.4 新設

複数プロンプトを一括コンパイルして JSON 結果を返す。
カンマ区切り複数プロンプトを受け取り、各々をコンパイルする。

入力:
  prompts_text   STRING  プロンプトリスト（1行1プロンプト）
  apply_profile  BOOLEAN プロファイル適用
  max_items      INT     最大処理件数（1〜50）

出力:
  results_json   STRING  BatchResult JSON（全件）
  best_prompt    STRING  最高スコアのポジティブ
  best_negative  STRING  最高スコアのネガティブ
  summary        STRING  処理結果サマリー
"""
from __future__ import annotations

import json
from typing import Any

from .node_base import FPSNodeBase, _get_context, _get_upm


class FacePromptBatchNode(FPSNodeBase):
    """複数プロンプトを一括コンパイルするバッチノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES  = ("results_json", "best_prompt", "best_negative", "summary")
    FUNCTION      = "batch_compile"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "prompts_text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "1行に1プロンプト
プロンプト1
プロンプト2
...",
                }),
            },
            "optional": {
                "apply_profile": ("BOOLEAN", {
                    "default": False,
                    "label_on": "Profile ON",
                    "label_off": "Profile OFF",
                }),
                "max_items": ("INT", {
                    "default": 10, "min": 1, "max": 50, "step": 1,
                }),
            },
        }

    def batch_compile(
        self,
        prompts_text: str,
        apply_profile: bool = False,
        max_items: int = 10,
    ) -> tuple[str, str, str, str]:
        """
        プロンプトリストを一括コンパイルする。

        Returns:
            (results_json, best_prompt, best_negative, summary)
        """
        # プロンプトリスト解析（1行1プロンプト）
        prompts = [
            p.strip() for p in prompts_text.split("
")
            if p.strip()
        ][:max_items]

        if not prompts:
            return (
                json.dumps({"error": "プロンプトが空です"}, ensure_ascii=False),
                "", "", "エラー: プロンプトが空です"
            )

        ctx = _get_context()
        if ctx is None:
            return (
                json.dumps({"error": "Context unavailable"}, ensure_ascii=False),
                prompts[0], "", "エラー: Context 初期化失敗"
            )

        # プロファイル適用関数
        apply_fn = None
        if apply_profile:
            upm = _get_upm()
            if upm:
                apply_fn = upm.apply_profile

        try:
            bm = ctx.batch_manager
            result = bm.compile_batch(prompts, apply_profile_fn=apply_fn)
        except Exception as e:
            return (
                json.dumps({"error": str(e)}, ensure_ascii=False),
                prompts[0], "", f"エラー: {e}"
            )

        # 最高スコアのアイテムを選択（スコアがない場合は最初のitem）
        best = max(result.items, key=lambda i: i.score if i.success else -1,
                   default=None)
        best_prompt   = best.prompt_out  if best and best.success else ""
        best_negative = best.negative_out if best and best.success else ""

        summary = (
            f"処理: {result.total}件 "
            f"成功: {result.succeeded}件 "
            f"失敗: {result.failed}件 "
            f"平均スコア: {result.avg_score:.1f}点 "
            f"処理時間: {result.total_elapsed_ms:.0f}ms"
        )

        return (
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            best_prompt,
            best_negative,
            summary,
        )
