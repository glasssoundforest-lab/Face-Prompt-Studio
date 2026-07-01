"""
fps-core/template/manager.py — TemplateManager

プロンプトテンプレートの読み込み・管理・展開を行う。

Public API:
  - load()           テンプレートを読み込む
  - list_templates() テンプレート一覧
  - get(id)          IDでテンプレートを取得
  - render(id, vars) テンプレートを変数で展開する
  - render_body(body, vars) テンプレート本文を直接展開
"""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any

from .models import RenderResult, Template, TemplateVariable

logger = logging.getLogger(__name__)


class TemplateManager:
    """
    FPS プロンプトテンプレート管理クラス。

    使い方:
        tm = TemplateManager(template_dir="fps-data/templates/system")
        tm.load()
        result = tm.render("face_basic", {"eye_color": "blue_eyes", "hair_color": "gold_hair"})
        print(result.rendered)
    """

    def __init__(
        self,
        system_dir: str | Path | None = None,
        user_dir: str | Path | None = None,
    ) -> None:
        self._system_dir = Path(system_dir) if system_dir else None
        self._user_dir = Path(user_dir) if user_dir else None
        self._templates: dict[str, Template] = {}
        self._lock = threading.RLock()
        self._loaded = False

    # ══════════════════════════════════════════════════════════════
    # Load
    # ══════════════════════════════════════════════════════════════

    def load(self) -> TemplateManager:
        """テンプレートファイルを読み込む（存在しなければ内蔵デフォルトで開始）"""
        with self._lock:
            self._templates.clear()
            # 組み込みデフォルトテンプレートを登録
            for t in _builtin_templates():
                self._templates[t.id] = t

            # system_dir のファイルをロード
            if self._system_dir and self._system_dir.exists():
                for path in sorted(self._system_dir.glob("*.json")):
                    self._load_file(path)

            # user_dir のファイルをロード（上書き可能）
            if self._user_dir and self._user_dir.exists():
                for path in sorted(self._user_dir.glob("*.json")):
                    self._load_file(path)

            self._loaded = True
            logger.info("TemplateManager loaded: %d templates", len(self._templates))
        return self

    def _load_file(self, path: Path) -> None:
        """JSON ファイルからテンプレートを読み込む"""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry in data.get("templates", []):
                t = Template(
                    id=entry["id"],
                    name=entry.get("name", entry["id"]),
                    body=entry["body"],
                    description=entry.get("description", ""),
                    variables=[
                        TemplateVariable(
                            name=v["name"],
                            description=v.get("description", ""),
                            default=v.get("default", ""),
                            examples=v.get("examples", []),
                            required=v.get("required", True),
                        )
                        for v in entry.get("variables", [])
                    ],
                    tags=entry.get("tags", []),
                    category=entry.get("category", "general"),
                )
                self._templates[t.id] = t
        except Exception as exc:
            logger.warning("Failed to load template file %s: %s", path, exc)

    # ══════════════════════════════════════════════════════════════
    # Query
    # ══════════════════════════════════════════════════════════════

    def list_templates(self, category: str | None = None) -> list[Template]:
        """テンプレート一覧を返す（任意でカテゴリ絞り込み）"""
        with self._lock:
            templates = list(self._templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return sorted(templates, key=lambda t: t.id)

    def get(self, template_id: str) -> Template | None:
        """IDでテンプレートを取得する"""
        with self._lock:
            return self._templates.get(template_id)

    def exists(self, template_id: str) -> bool:
        with self._lock:
            return template_id in self._templates

    def categories(self) -> list[str]:
        """利用可能なカテゴリ一覧を返す（ソート済み）"""
        with self._lock:
            return sorted({t.category for t in self._templates.values()})

    def statistics(self) -> dict[str, Any]:
        with self._lock:
            by_cat: dict[str, int] = {}
            for t in self._templates.values():
                by_cat[t.category] = by_cat.get(t.category, 0) + 1
            return {
                "total_templates": len(self._templates),
                "by_category": by_cat,
            }

    # ══════════════════════════════════════════════════════════════
    # Render
    # ══════════════════════════════════════════════════════════════

    def render(
        self,
        template_id: str,
        variables: dict[str, str],
    ) -> RenderResult:
        """テンプレートIDと変数辞書からプロンプトを展開する。

        Args:
            template_id: テンプレートID
            variables:   {"eye_color": "blue_eyes", ...} の辞書

        Returns:
            RenderResult（変数不足でも部分展開して返す）

        Raises:
            KeyError: テンプレートが存在しない場合
        """
        tmpl = self.get(template_id)
        if tmpl is None:
            raise KeyError(f"Template '{template_id}' not found")
        result = self.render_body(tmpl.body, variables)
        result.template_id = template_id
        return result

    def render_body(
        self,
        body: str,
        variables: dict[str, str],
    ) -> RenderResult:
        """テンプレート本文を直接展開する（テンプレートID不要）。

        Args:
            body:      テンプレート本文（例: "{quality}, {eye_color} eyes"）
            variables: 変数辞書

        Returns:
            RenderResult
        """
        placeholders = list(dict.fromkeys(re.findall(r"\{(\w+)\}", body)))
        missing: list[str] = []
        used: dict[str, str] = {}
        warnings: list[str] = []

        rendered = body
        for name in placeholders:
            if name in variables and variables[name].strip():
                value = variables[name].strip()
                rendered = rendered.replace(f"{{{name}}}", value)
                used[name] = value
            else:
                # デフォルト値があれば使う
                # （この呼び出しではテンプレートメタが不明なのでスキップ）
                missing.append(name)
                warnings.append(f"変数 '{name}' が未指定です。")

        return RenderResult(
            template_id="",
            rendered=rendered,
            variables_used=used,
            missing_variables=missing,
            warnings=warnings,
        )

    def __repr__(self) -> str:
        return f"TemplateManager(templates={len(self._templates)})"


# ══════════════════════════════════════════════════════════════════
# 組み込みデフォルトテンプレート
# ══════════════════════════════════════════════════════════════════

def _builtin_templates() -> list[Template]:
    """常に利用可能な組み込みテンプレート"""
    return [
        Template(
            id="face_basic",
            name="基本顔プロンプト",
            body="{quality}, {eye_color} eyes, {hair_color} {hair_length} hair, {expression}",
            description="目・髪・表情の基本セットを展開するシンプルなテンプレート。",
            variables=[
                TemplateVariable("quality",     "品質タグ",   "masterpiece",  ["masterpiece", "best quality"]),
                TemplateVariable("eye_color",   "目の色",     "blue_eyes",    ["blue_eyes", "green_eyes", "red_eyes"]),
                TemplateVariable("hair_color",  "髪の色",     "blonde",       ["blonde", "black", "silver"]),
                TemplateVariable("hair_length", "髪の長さ",   "long",         ["long", "short", "medium"]),
                TemplateVariable("expression",  "表情",       "smile",        ["smile", "serious", "blush"]),
            ],
            tags=["basic", "face"],
            category="face",
        ),
        Template(
            id="face_detailed",
            name="詳細顔プロンプト",
            body=(
                "{quality}, {eye_color} eyes, {hair_color} {hair_length} hair, "
                "{expression}, {skin_tone} skin, {face_shape} face"
            ),
            description="目・髪・表情・肌・顔型を含む詳細テンプレート。",
            variables=[
                TemplateVariable("quality",     "品質タグ",   "masterpiece",  ["masterpiece"]),
                TemplateVariable("eye_color",   "目の色",     "blue_eyes",    ["blue_eyes", "brown_eyes"]),
                TemplateVariable("hair_color",  "髪の色",     "blonde",       ["blonde", "black"]),
                TemplateVariable("hair_length", "髪の長さ",   "long",         ["long", "short"]),
                TemplateVariable("expression",  "表情",       "smile",        ["smile", "serious"]),
                TemplateVariable("skin_tone",   "肌の色",     "fair",         ["fair", "tan", "pale"]),
                TemplateVariable("face_shape",  "顔型",       "oval",         ["oval", "round", "heart"]),
            ],
            tags=["detailed", "face"],
            category="face",
        ),
        Template(
            id="fantasy_character",
            name="ファンタジーキャラクター",
            body=(
                "{quality}, {eye_color} eyes, {hair_color} hair, "
                "{fantasy_feature}, {expression}, {accessories}"
            ),
            description="ファンタジー要素（猫耳・翼・角など）を含むキャラクタープロンプト。",
            variables=[
                TemplateVariable("quality",         "品質タグ",         "masterpiece",  ["masterpiece"]),
                TemplateVariable("eye_color",       "目の色",           "purple_eyes",  ["purple_eyes", "red_eyes"]),
                TemplateVariable("hair_color",      "髪の色",           "silver_hair",  ["silver_hair", "white_hair"]),
                TemplateVariable("fantasy_feature", "ファンタジー要素", "cat_ears",     ["cat_ears", "wings", "horns"]),
                TemplateVariable("expression",      "表情",             "smile",        ["smile", "serious"]),
                TemplateVariable("accessories",     "アクセサリー",     "",             ["glasses", "ribbon"], required=False),
            ],
            tags=["fantasy", "character"],
            category="fantasy",
        ),
        Template(
            id="negative_basic",
            name="基本ネガティブプロンプト",
            body=(
                "low_quality, worst_quality, bad_anatomy, bad_hands, "
                "extra_fingers, {additional_negative}"
            ),
            description="定番ネガティブプロンプトに追加要素を加えるテンプレート。",
            variables=[
                TemplateVariable(
                    "additional_negative",
                    "追加ネガティブ要素",
                    "watermark, text",
                    ["watermark, text", "blurry, out_of_focus"],
                    required=False,
                ),
            ],
            tags=["negative", "basic"],
            category="negative",
        ),
        Template(
            id="style_transfer",
            name="スタイル転写",
            body="{quality}, {style} style, {subject}, {color_palette}",
            description="絵柄・スタイルを指定してキャラクターを描くテンプレート。",
            variables=[
                TemplateVariable("quality",       "品質タグ",   "masterpiece",    ["masterpiece"]),
                TemplateVariable("style",         "スタイル",   "anime",          ["anime", "photorealistic", "watercolor"]),
                TemplateVariable("subject",       "被写体",     "1girl, smile",   ["1girl, blue_eyes", "1girl, long hair"]),
                TemplateVariable("color_palette", "カラーパレット", "warm colors", ["warm colors", "cool tones", "pastel"]),
            ],
            tags=["style", "advanced"],
            category="style",
        ),
    ]
