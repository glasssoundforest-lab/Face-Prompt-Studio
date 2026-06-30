"""
fps-adapters/a1111/adapter.py — AUTOMATIC1111 WebUI Adapter

fps-core から完全独立。core は a1111 を一切 import しない。

AUTOMATIC1111 の重み記法:
  (tag)        weight 1.1 相当（括弧1つで1.1倍）
  ((tag))      weight 1.21 相当（括弧2つで1.21倍 = 1.1^2）
  (tag:1.3)    明示的な重み指定
  [tag]        weight 0.91 相当（角括弧1つで0.91倍）

このアダプターは常に明示的な (tag:weight) 形式で出力する
（曖昧な括弧の数による表現は使わない）。

Public API:
  - convert(result)        PipelineResult → A1111 dict
  - convert_json(result)   JSON 文字列
  - format_prompt(result)  プロンプト文字列のみ
  - to_api_payload(result) A1111 WebUI REST API 互換ペイロード
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


class A1111Adapter:
    """
    PipelineResult を AUTOMATIC1111 WebUI 形式に変換するアダプター。

    使い方:
        adapter = A1111Adapter()
        output  = adapter.convert(pipeline_result)
        payload = adapter.to_api_payload(pipeline_result, steps=20, cfg_scale=7.0)
    """

    def __init__(self, weight_precision: int = 2) -> None:
        """
        Args:
            weight_precision: 重み表記の小数桁数（A1111 慣習は2桁）
        """
        self._precision = weight_precision

    # ══════════════════════════════════════════════════════════════
    # Convert
    # ══════════════════════════════════════════════════════════════

    def convert(self, result: PipelineResult) -> dict[str, Any]:
        """
        PipelineResult を A1111 形式の辞書に変換する。

        Returns:
            {"prompt": str, "negative_prompt": str, "tags": [...], "meta": {...}}
        """
        return {
            "prompt": self.format_prompt(result),
            "negative_prompt": self.format_negative(result),
            "tags": [
                {
                    "tag": t.tag,
                    "resolved": t.meta.get("resolved", t.tag),
                    "category": t.category,
                    "weight": round(t.weight, self._precision),
                }
                for t in result.tags
            ],
            "meta": {
                "fps_version": "0.8.0",
                "adapter": "a1111",
                "success": result.success,
            },
        }

    def convert_json(self, result: PipelineResult, indent: int = 2) -> str:
        """JSON 文字列として返す"""
        return json.dumps(self.convert(result), ensure_ascii=False, indent=indent)

    def format_prompt(self, result: PipelineResult) -> str:
        """A1111 重み記法のプロンプト文字列を返す"""
        return _format_tags(result.tags, self._precision)

    def format_negative(self, result: PipelineResult) -> str:
        """A1111 重み記法のネガティブプロンプト文字列を返す"""
        return _format_tags(result.negative_tags, self._precision)

    # ══════════════════════════════════════════════════════════════
    # API Payload
    # ══════════════════════════════════════════════════════════════

    def to_api_payload(
        self,
        result: PipelineResult,
        steps: int = 20,
        cfg_scale: float = 7.0,
        width: int = 512,
        height: int = 512,
        sampler_name: str = "Euler a",
        **extra: Any,
    ) -> dict[str, Any]:
        """
        AUTOMATIC1111 WebUI の /sdapi/v1/txt2img 互換ペイロードを生成する。

        Args:
            result:       PipelineResult
            steps:        サンプリングステップ数
            cfg_scale:    CFG スケール
            width:        画像幅
            height:       画像高さ
            sampler_name: サンプラー名
            **extra:      その他 A1111 API パラメータをそのまま追加

        Returns:
            txt2img API 互換の辞書
        """
        payload: dict[str, Any] = {
            "prompt": self.format_prompt(result),
            "negative_prompt": self.format_negative(result),
            "steps": steps,
            "cfg_scale": cfg_scale,
            "width": width,
            "height": height,
            "sampler_name": sampler_name,
        }
        payload.update(extra)
        return payload

    def __repr__(self) -> str:
        return f"A1111Adapter(weight_precision={self._precision})"


# ── Helpers ──────────────────────────────────────────────────────────


def _format_tags(tags: list[TagEntry], precision: int) -> str:
    """タグリストを A1111 形式の重み付きプロンプト文字列に変換する"""
    parts: list[str] = []
    for t in tags:
        resolved = t.meta.get("resolved") or t.tag
        # A1111 の慣習に合わせ resolved を小文字・スペース区切りに変換
        display = resolved.replace(".", " ").lower() if "." in resolved else resolved
        if t.weight != 1.0:
            parts.append(f"({display}:{t.weight:.{precision}f})")
        else:
            parts.append(display)
    return ", ".join(parts)
