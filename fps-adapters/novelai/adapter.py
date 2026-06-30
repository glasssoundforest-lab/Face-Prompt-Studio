"""
fps-adapters/novelai/adapter.py — NovelAI Adapter

fps-core から完全独立。core は novelai を一切 import しない。

NovelAI の重み記法（{}[]ベース）:
  {tag}     weight 1.05 相当（波括弧1つ）
  {{tag}}   weight 1.1025 相当（波括弧2つ = 1.05^2）
  [tag]     weight 0.95 相当（角括弧1つ）
  [[tag]]   weight 0.9025 相当（角括弧2つ = 0.95^2）

NovelAI は A1111 の `(tag:1.3)` 明示記法もサポートしているため、
このアダプターは可読性を優先して常に明示的な weight 記法で出力する。

Public API:
  - convert(result)        PipelineResult → NovelAI dict
  - convert_json(result)   JSON 文字列
  - format_prompt(result)  プロンプト文字列のみ（{}weight記法）
  - to_api_payload(result) NovelAI API 互換ペイロード
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_CORE = Path(__file__).parents[2] / "fps-core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from pipeline.models import PipelineResult, TagEntry  # noqa: E402


class NovelAIAdapter:
    """
    PipelineResult を NovelAI 形式に変換するアダプター。

    使い方:
        adapter = NovelAIAdapter()
        output  = adapter.convert(pipeline_result)
        payload = adapter.to_api_payload(pipeline_result, model="nai-diffusion-3")
    """

    def __init__(self, use_brace_notation: bool = False) -> None:
        """
        Args:
            use_brace_notation: True の場合、重み1.0以外のタグを
                                 {tag} 記法（整数倍数のみ近似）で出力。
                                 False（デフォルト）の場合は (tag:weight) 明示記法。
        """
        self._use_brace = use_brace_notation

    # ══════════════════════════════════════════════════════════════
    # Convert
    # ══════════════════════════════════════════════════════════════

    def convert(self, result: PipelineResult) -> dict[str, Any]:
        """
        PipelineResult を NovelAI 形式の辞書に変換する。

        Returns:
            {"prompt": str, "negative_prompt": str (uc相当), "tags": [...], "meta": {...}}
        """
        return {
            "prompt": self.format_prompt(result),
            "negative_prompt": self.format_negative(result),  # NovelAI では "uc" と呼ばれる
            "tags": [
                {
                    "tag": t.tag,
                    "resolved": t.meta.get("resolved", t.tag),
                    "category": t.category,
                    "weight": round(t.weight, 3),
                }
                for t in result.tags
            ],
            "meta": {
                "fps_version": "0.8.0",
                "adapter": "novelai",
                "success": result.success,
            },
        }

    def convert_json(self, result: PipelineResult, indent: int = 2) -> str:
        """JSON 文字列として返す"""
        return json.dumps(self.convert(result), ensure_ascii=False, indent=indent)

    def format_prompt(self, result: PipelineResult) -> str:
        """NovelAI 重み記法のプロンプト文字列を返す"""
        return _format_tags(result.tags, self._use_brace)

    def format_negative(self, result: PipelineResult) -> str:
        """NovelAI 重み記法のネガティブプロンプト（uc）文字列を返す"""
        return _format_tags(result.negative_tags, self._use_brace)

    # ══════════════════════════════════════════════════════════════
    # API Payload
    # ══════════════════════════════════════════════════════════════

    def to_api_payload(
        self,
        result: PipelineResult,
        model: str = "nai-diffusion-3",
        steps: int = 28,
        scale: float = 6.0,
        width: int = 832,
        height: int = 1216,
        sampler: str = "k_euler_ancestral",
        **extra: Any,
    ) -> dict[str, Any]:
        """
        NovelAI generate-image API 互換ペイロードを生成する。

        Args:
            result:  PipelineResult
            model:   NovelAI モデル名
            steps:   サンプリングステップ数
            scale:   ガイダンススケール
            width:   画像幅
            height:  画像高さ
            sampler: サンプラー名
            **extra: その他 NovelAI API パラメータをそのまま追加

        Returns:
            generate-image API 互換の辞書
        """
        payload: dict[str, Any] = {
            "input": self.format_prompt(result),
            "model": model,
            "parameters": {
                "negative_prompt": self.format_negative(result),
                "steps": steps,
                "scale": scale,
                "width": width,
                "height": height,
                "sampler": sampler,
                **extra,
            },
        }
        return payload

    def __repr__(self) -> str:
        return f"NovelAIAdapter(use_brace_notation={self._use_brace})"


# ── Helpers ──────────────────────────────────────────────────────────


def _format_tags(tags: list[TagEntry], use_brace: bool) -> str:
    """タグリストを NovelAI 形式の重み付きプロンプト文字列に変換する"""
    parts: list[str] = []
    for t in tags:
        resolved = t.meta.get("resolved") or t.tag
        display = resolved.replace(".", " ").lower() if "." in resolved else resolved

        if t.weight == 1.0:
            parts.append(display)
        elif use_brace:
            parts.append(_to_brace_notation(display, t.weight))
        else:
            parts.append(f"({display}:{t.weight:.2f})")
    return ", ".join(parts)


def _to_brace_notation(tag: str, weight: float) -> str:
    """
    重みを {} / [] のネスト数による近似記法に変換する。
    {tag} = 1.05倍, [tag] = 0.95倍 をベースに最も近いネスト数を計算する。
    """
    if weight > 1.0:
        # weight = 1.05^n となる n を求める（最大5重まで）
        best_n, best_diff = 1, abs(weight - 1.05)
        for i in range(1, 6):
            approx = 1.05**i
            diff = abs(weight - approx)
            if diff < best_diff:
                best_n, best_diff = i, diff
        return "{" * best_n + tag + "}" * best_n
    elif weight < 1.0:
        best_n, best_diff = 1, abs(weight - 0.95)
        for i in range(1, 6):
            approx = 0.95**i
            diff = abs(weight - approx)
            if diff < best_diff:
                best_n, best_diff = i, diff
        return "[" * best_n + tag + "]" * best_n
    return tag
