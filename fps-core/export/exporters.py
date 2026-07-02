"""
fps-core/export/exporters.py — マルチフォーマット エクスポーター
★ v2.8 新設

サポートする出力形式:
  a1111    — Automatic1111 WebUI 互換（改行区切り pos/neg）
  novelai  — NovelAI 互換（UD記法 {{強調}} / [[抑制]]）
  json     — FPS ネイティブ JSON
  yaml     — 人間可読 YAML
  csv      — スプレッドシート互換 CSV
  bundle   — 上記を zip にまとめた一括エクスポート
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExportFormat(str, Enum):
    A1111   = "a1111"
    NOVELAI = "novelai"
    JSON    = "json"
    YAML    = "yaml"
    CSV     = "csv"
    BUNDLE  = "bundle"


@dataclass
class ExportResult:
    """エクスポート結果"""
    format:   str
    content:  str | bytes
    filename: str
    mime_type: str
    meta:     dict[str, Any] = field(default_factory=dict)

    @property
    def is_binary(self) -> bool:
        return isinstance(self.content, bytes)


class PromptExporter:
    """エクスポートの共通インターフェース"""

    def export(
        self,
        pos: str,
        neg: str = "",
        meta: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ExportResult:
        raise NotImplementedError


class A1111Exporter(PromptExporter):
    """
    Automatic1111 WebUI 互換エクスポーター。

    出力形式:
      <positive prompt>
      Negative prompt: <negative prompt>
      Steps: 20, Sampler: Euler a, CFG scale: 7, Size: 512x512
    """

    def __init__(
        self,
        steps:   int   = 20,
        sampler: str   = "Euler a",
        cfg:     float = 7.0,
        width:   int   = 512,
        height:  int   = 512,
        model:   str   = "",
        seed:    int   = -1,
    ) -> None:
        self.steps   = steps
        self.sampler = sampler
        self.cfg     = cfg
        self.width   = width
        self.height  = height
        self.model   = model
        self.seed    = seed

    def export(
        self,
        pos: str,
        neg: str = "",
        meta: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ExportResult:
        m = meta or {}
        steps   = m.get("steps",   kwargs.get("steps",   self.steps))
        sampler = m.get("sampler", kwargs.get("sampler", self.sampler))
        cfg     = m.get("cfg",     kwargs.get("cfg",     self.cfg))
        width   = m.get("width",   kwargs.get("width",   self.width))
        height  = m.get("height",  kwargs.get("height",  self.height))
        model   = m.get("model",   kwargs.get("model",   self.model))
        seed    = m.get("seed",    kwargs.get("seed",    self.seed))

        lines = [pos.strip()]
        if neg.strip():
            lines.append(f"Negative prompt: {neg.strip()}")
        params = [
            f"Steps: {steps}",
            f"Sampler: {sampler}",
            f"CFG scale: {cfg}",
            f"Size: {width}x{height}",
        ]
        if seed >= 0:
            params.append(f"Seed: {seed}")
        if model:
            params.append(f"Model: {model}")
        lines.append(", ".join(params))

        return ExportResult(
            format="a1111",
            content="
".join(lines),
            filename="prompt_a1111.txt",
            mime_type="text/plain",
            meta={"steps": steps, "sampler": sampler,
                  "cfg": cfg, "width": width, "height": height},
        )


class NovelAIExporter(PromptExporter):
    """
    NovelAI 互換エクスポーター。

    強調構文: {{tag}} → 重みを上げる
    抑制構文: [[tag]] → 重みを下げる
    A1111 の (tag:1.2) 記法を NovelAI 記法に変換する。
    """

    def export(
        self,
        pos: str,
        neg: str = "",
        meta: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ExportResult:
        nai_pos = self._convert(pos)
        nai_neg = self._convert(neg)
        content = json.dumps({
            "input":     nai_pos,
            "model":     meta.get("model", "nai-diffusion-3") if meta else "nai-diffusion-3",
            "action":    "generate",
            "parameters": {
                "width":    meta.get("width",  832) if meta else 832,
                "height":   meta.get("height", 1216) if meta else 1216,
                "scale":    meta.get("cfg",    5.0) if meta else 5.0,
                "steps":    meta.get("steps",  28) if meta else 28,
                "negative_prompt": nai_neg,
            }
        }, ensure_ascii=False, indent=2)
        return ExportResult(
            format="novelai",
            content=content,
            filename="prompt_novelai.json",
            mime_type="application/json",
        )

    @staticmethod
    def _convert(prompt: str) -> str:
        """A1111 記法を NovelAI 記法に変換する"""
        import re
        # (tag:1.2) → {{tag}} (weight > 1.0)
        # (tag:0.8) → [[tag]] (weight < 1.0)
        def replace_weight(m: re.Match) -> str:
            tag    = m.group(1).strip()
            weight = float(m.group(2))
            if weight > 1.0:
                reps = min(int((weight - 1.0) / 0.05) + 1, 4)
                return "{" * reps + tag + "}" * reps
            elif weight < 1.0:
                reps = min(int((1.0 - weight) / 0.05) + 1, 4)
                return "[" * reps + tag + "]" * reps
            return tag
        result = re.sub(r'\(([^:)]+):([0-9.]+)\)', replace_weight, prompt)
        # 残った括弧を除去
        result = re.sub(r'\(([^)]+)\)', r'', result)
        return result


class BundleExporter(PromptExporter):
    """
    一括エクスポーター — 全形式を zip にまとめて返す。
    """

    def __init__(self) -> None:
        self._a1111  = A1111Exporter()
        self._novelai = NovelAIExporter()

    def export(
        self,
        pos: str,
        neg: str = "",
        meta: dict[str, Any] | None = None,
        label: str = "export",
        **kwargs: Any,
    ) -> ExportResult:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # A1111
            r1 = self._a1111.export(pos, neg, meta, **kwargs)
            zf.writestr(f"{label}_a1111.txt", r1.content)
            # NovelAI
            r2 = self._novelai.export(pos, neg, meta, **kwargs)
            zf.writestr(f"{label}_novelai.json", r2.content)
            # FPS JSON
            fps_data = {
                "version":    "2.8.0",
                "pos":        pos,
                "neg":        neg,
                "meta":       meta or {},
                "label":      label,
            }
            zf.writestr(f"{label}_fps.json",
                        json.dumps(fps_data, ensure_ascii=False, indent=2))
            # CSV
            csv_buf = io.StringIO()
            writer  = csv.writer(csv_buf)
            writer.writerow(["format", "prompt_type", "content"])
            writer.writerow(["a1111",  "positive",    pos])
            writer.writerow(["a1111",  "negative",    neg])
            writer.writerow(["novelai", "positive",   NovelAIExporter._convert(pos)])
            writer.writerow(["novelai", "negative",   NovelAIExporter._convert(neg)])
            zf.writestr(f"{label}_prompts.csv", csv_buf.getvalue())
            # YAML（PyYAML 不要の簡易実装）
            yaml_lines = [
                f"# FacePromptStudio Export — {label}",
                f"label: {label}",
                f"positive: |",
                *[f"  {line}" for line in pos.split("
")],
                f"negative: |",
                *[f"  {line}" for line in neg.split("
")],
                "meta:",
                *[f"  {k}: {v}" for k, v in (meta or {}).items()],
            ]
            zf.writestr(f"{label}_prompt.yaml", "
".join(yaml_lines))

        return ExportResult(
            format="bundle",
            content=buf.getvalue(),
            filename=f"{label}_bundle.zip",
            mime_type="application/zip",
        )


def get_exporter(fmt: str | ExportFormat, **kwargs: Any) -> PromptExporter:
    """形式名からエクスポーターインスタンスを返すファクトリ関数"""
    fmt = ExportFormat(fmt) if isinstance(fmt, str) else fmt
    if fmt == ExportFormat.A1111:
        return A1111Exporter(**kwargs)
    if fmt == ExportFormat.NOVELAI:
        return NovelAIExporter()
    if fmt == ExportFormat.BUNDLE:
        return BundleExporter()
    raise ValueError(f"未対応のフォーマット: {fmt}")
