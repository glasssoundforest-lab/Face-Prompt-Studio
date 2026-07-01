"""
fps-adapters/comfyui/nodes/face_prompt_template.py
ノード: 🎭 Face Prompt Template

機能:
  - 組み込み / カスタムテンプレートをリスト表示
  - テンプレート変数を ComfyUI UI 上で入力して展開
  - 展開済みプロンプトを下流ノードに接続可能
  - 変数未入力時はデフォルト値を使用

入力:
  template_id    STRING  テンプレート ID（例: "face_basic"）
  variables_json STRING  変数辞書（JSON 形式）
  quality        STRING  {quality} 変数（ショートカット）
  eye_color      STRING  {eye_color} 変数（ショートカット）
  hair_color     STRING  {hair_color} 変数（ショートカット）
  hair_length    STRING  {hair_length} 変数（ショートカット）
  expression     STRING  {expression} 変数（ショートカット）

出力:
  rendered       STRING  変数展開済みプロンプト
  missing        STRING  未指定変数の一覧（カンマ区切り）
  report         STRING  展開レポート
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .node_base import _ROOT, FPSNodeBase

_CORE = _ROOT / "fps-core"
for _p in (str(_CORE),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_template_manager = None


def _get_template_manager():
    """TemplateManager をシングルトンで返す"""
    global _template_manager
    if _template_manager is None:
        from template.manager import TemplateManager

        tm_data = _ROOT / "fps-data" / "templates" / "system"
        _template_manager = TemplateManager(
            system_dir=tm_data if tm_data.exists() else None
        )
        _template_manager.load()
    return _template_manager


def _list_template_ids() -> list[str]:
    """利用可能なテンプレートIDを返す（UI 選択肢用）"""
    try:
        tm = _get_template_manager()
        return [t.id for t in tm.list_templates()]
    except Exception:
        return ["face_basic", "face_detailed", "fantasy_character",
                "negative_basic", "style_transfer"]


class FacePromptTemplateNode(FPSNodeBase):
    """Face Prompt Template ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("rendered", "missing", "report")
    FUNCTION = "render_template"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        template_ids = _list_template_ids()
        return {
            "required": {
                "template_id": (
                    template_ids,
                    {"default": template_ids[0] if template_ids else "face_basic"},
                ),
            },
            "optional": {
                # JSON形式で全変数をまとめて渡す方法
                "variables_json": (
                    "STRING",
                    {
                        "default": "{}",
                        "multiline": True,
                        "placeholder": '{"quality": "masterpiece", "eye_color": "blue_eyes"}',
                    },
                ),
                # 頻出変数のショートカット入力（JSON より優先）
                "quality": ("STRING", {"default": "", "placeholder": "masterpiece"}),
                "eye_color": ("STRING", {"default": "", "placeholder": "blue_eyes"}),
                "hair_color": ("STRING", {"default": "", "placeholder": "blonde"}),
                "hair_length": ("STRING", {"default": "", "placeholder": "long"}),
                "expression": ("STRING", {"default": "", "placeholder": "smile"}),
                "skin_tone": ("STRING", {"default": "", "placeholder": "fair"}),
                "face_shape": ("STRING", {"default": "", "placeholder": "oval"}),
                "fantasy_feature": ("STRING", {"default": "", "placeholder": "cat_ears"}),
                "accessories": ("STRING", {"default": ""}),
                "style": ("STRING", {"default": "", "placeholder": "anime"}),
                "subject": ("STRING", {"default": "", "placeholder": "1girl"}),
                "color_palette": ("STRING", {"default": "", "placeholder": "warm colors"}),
                "additional_negative": ("STRING", {"default": ""}),
            },
        }

    def render_template(
        self,
        template_id: str = "face_basic",
        variables_json: str = "{}",
        quality: str = "",
        eye_color: str = "",
        hair_color: str = "",
        hair_length: str = "",
        expression: str = "",
        skin_tone: str = "",
        face_shape: str = "",
        fantasy_feature: str = "",
        accessories: str = "",
        style: str = "",
        subject: str = "",
        color_palette: str = "",
        additional_negative: str = "",
    ) -> tuple[str, str, str]:
        """テンプレートを変数で展開して返す。

        Returns:
            (rendered, missing, report)
        """
        try:
            tm = _get_template_manager()
        except Exception as e:
            err = f"[ERROR] TemplateManager 初期化失敗: {e}"
            return ("", "", err)

        # ── 変数辞書を構築（JSON → ショートカット でマージ） ────
        try:
            variables: dict[str, str] = json.loads(variables_json) if variables_json.strip() else {}
        except json.JSONDecodeError:
            variables = {}

        # ショートカット入力が空でなければ上書き（JSON より優先）
        shortcuts = {
            "quality": quality,
            "eye_color": eye_color,
            "hair_color": hair_color,
            "hair_length": hair_length,
            "expression": expression,
            "skin_tone": skin_tone,
            "face_shape": face_shape,
            "fantasy_feature": fantasy_feature,
            "accessories": accessories,
            "style": style,
            "subject": subject,
            "color_palette": color_palette,
            "additional_negative": additional_negative,
        }
        for k, v in shortcuts.items():
            if v.strip():
                variables[k] = v.strip()

        # ── テンプレート展開 ──────────────────────────────────────
        try:
            result = tm.render(template_id, variables)
        except KeyError:
            return (
                "",
                template_id,
                f"[ERROR] テンプレート '{template_id}' が見つかりません。",
            )

        # ── レポート生成 ──────────────────────────────────────────
        lines = [
            "=== Face Prompt Template ===",
            f"template : {template_id}",
            f"success  : {result.success}",
            "",
            "[Rendered]",
            result.rendered,
        ]

        if result.variables_used:
            lines += ["", "[Variables Used]"]
            for k, v in result.variables_used.items():
                lines.append(f"  {k}: {v}")

        if result.missing_variables:
            lines += ["", "[Missing Variables]"]
            for m in result.missing_variables:
                lines.append(f"  {m} (using placeholder '{{{m}}}')")

        if result.warnings:
            lines += ["", "[Warnings]"]
            lines.extend(f"  {w}" for w in result.warnings)

        missing_str = ", ".join(result.missing_variables)
        return (result.rendered, missing_str, "\n".join(lines))
