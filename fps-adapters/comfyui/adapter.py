"""
fps-adapters/comfyui/adapter.py — ComfyUI Adapter

fps-core から完全独立。core は comfyui を一切 import しない。
ComfyUI API v1 / v2 対応。

Public API:
  - convert(result)   PipelineResult → ComfyUI JSON
  - format_prompt(result)   プロンプト文字列のみ返す
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# fps-core をパスに追加（アダプターは core に依存してよい）
_CORE = Path(__file__).parents[2] / "fps-core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from pipeline.models import PipelineResult, TagEntry  # noqa: E402


class ComfyUIAdapter:
    """
    PipelineResult を ComfyUI JSON 形式に変換するアダプター。

    使い方:
        adapter = ComfyUIAdapter(api_version="v1")
        output  = adapter.convert(pipeline_result)
        json_str = json.dumps(output, ensure_ascii=False, indent=2)
    """

    SUPPORTED_VERSIONS = ("v1", "v2")

    def __init__(self, api_version: str = "v1") -> None:
        if api_version not in self.SUPPORTED_VERSIONS:
            raise ValueError(
                f"非対応の API バージョン: '{api_version}'. " f"対応: {self.SUPPORTED_VERSIONS}"
            )
        self._api_version = api_version

    # ══════════════════════════════════════════════════════════════
    # Convert
    # ══════════════════════════════════════════════════════════════

    def convert(self, result: PipelineResult) -> dict[str, Any]:
        """
        PipelineResult を ComfyUI JSON 形式に変換する。

        Returns:
            ComfyUI API 形式の辞書
        """
        if self._api_version == "v1":
            return self._to_v1(result)
        return self._to_v2(result)

    def convert_json(self, result: PipelineResult, indent: int = 2) -> str:
        """JSON 文字列として返す"""
        return json.dumps(self.convert(result), ensure_ascii=False, indent=indent)

    def format_prompt(self, result: PipelineResult) -> str:
        """プロンプト文字列のみ返す（重みフォーマット済み）"""
        return _format_tags(result.tags)

    def format_negative(self, result: PipelineResult) -> str:
        """ネガティブプロンプト文字列のみ返す"""
        return _format_tags(result.negative_tags)

    # ══════════════════════════════════════════════════════════════
    # API バージョン別フォーマット
    # ══════════════════════════════════════════════════════════════

    def _to_v1(self, result: PipelineResult) -> dict[str, Any]:
        """
        ComfyUI API v1 形式。
        {
          "prompt": "...",
          "negative_prompt": "...",
          "tags": [...],
          "meta": {...}
        }
        """
        return {
            "prompt": _format_tags(result.tags),
            "negative_prompt": _format_tags(result.negative_tags),
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
                "fps_version": "0.5.0",
                "adapter": "comfyui",
                "api_version": "v1",
                "stage_count": result.stage_count,
                "success": result.success,
            },
        }

    def _to_v2(self, result: PipelineResult) -> dict[str, Any]:
        """
        ComfyUI API v2 形式（ノードグラフ形式）。
        CLIPTextEncode ノードを生成する。
        """
        pos_prompt = _format_tags(result.tags)
        neg_prompt = _format_tags(result.negative_tags)

        return {
            "nodes": {
                "6": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": pos_prompt,
                        "clip": ["4", 1],
                    },
                    "_meta": {"title": "CLIP Text Encode (Prompt)"},
                },
                "7": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": neg_prompt,
                        "clip": ["4", 1],
                    },
                    "_meta": {"title": "CLIP Text Encode (Negative)"},
                },
            },
            "meta": {
                "fps_version": "0.5.0",
                "adapter": "comfyui",
                "api_version": "v2",
                "prompt": pos_prompt,
                "negative": neg_prompt,
            },
        }

    def __repr__(self) -> str:
        return f"ComfyUIAdapter(api_version={self._api_version!r})"


# ── Helpers ──────────────────────────────────────────────────────────


def _format_tags(tags: list[TagEntry]) -> str:
    """タグリストをプロンプト文字列に変換する（重み付き）"""
    parts: list[str] = []
    for t in tags:
        resolved = t.meta.get("resolved") or t.tag
        if t.weight != 1.0:
            parts.append(f"({resolved}:{t.weight:.2f})")
        else:
            parts.append(resolved)
    return ", ".join(parts)
