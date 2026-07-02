"""
fps-adapters/comfyui/nodes/face_prompt_consistency.py
ノード: 🎭 Face Prompt Consistency Checker  ★v2.5 新設

複数のプロンプトのスタイル一貫性を分析する。
同一キャラで複数枚生成する際、目の色・髪色・スタイルの
矛盾を検出してスコアと改善提案を返す。

入力:
  prompts_text   STRING  プロンプトリスト（1行1件）
  min_score      FLOAT   警告を発する最低スコア閾値

出力:
  overall_score  FLOAT   一貫性スコア（0〜100）
  inconsistencies STRING 矛盾タグリスト（カンマ区切り）
  recommendations STRING 改善提案（改行区切り）
  result_json    STRING  詳細結果 JSON
  passed         BOOL    min_score 以上かどうか
"""
from __future__ import annotations

import json
from typing import Any
from .node_base import FPSNodeBase, _get_context


class FacePromptConsistencyNode(FPSNodeBase):
    """プロンプト一貫性チェッカーノード"""

    RETURN_TYPES  = ("FLOAT", "STRING", "STRING", "STRING", "BOOLEAN")
    RETURN_NAMES  = ("overall_score", "inconsistencies",
                     "recommendations", "result_json", "passed")
    FUNCTION      = "check_consistency"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "prompts_text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "1行に1プロンプト:
masterpiece, blue_eyes, blonde_hair
masterpiece, blue_eyes, blonde_hair, kimono",
                }),
            },
            "optional": {
                "min_score": ("FLOAT", {
                    "default": 70.0, "min": 0.0, "max": 100.0, "step": 5.0,
                }),
            },
        }

    def check_consistency(
        self,
        prompts_text: str,
        min_score: float = 70.0,
    ) -> tuple[float, str, str, str, bool]:
        prompts = [p.strip() for p in prompts_text.split("
") if p.strip()]

        if len(prompts) < 2:
            return (
                100.0, "", "プロンプトを2件以上入力してください",
                '{"error": "prompts < 2"}', True
            )

        ctx = _get_context()
        if ctx is None:
            return (0.0, "", "Context unavailable",
                    '{"error":"Context unavailable"}', False)

        try:
            checker = ctx.ai_manager["consistency"]
            result = checker.check(prompts)

            inconsistencies = ", ".join(result.inconsistent_tags)
            recommendations = "
".join(result.recommendations)
            result_json = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
            passed = result.overall_score >= min_score

            return (
                result.overall_score,
                inconsistencies,
                recommendations,
                result_json,
                passed,
            )
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            return (0.0, "", f"エラー: {e}", err, False)
