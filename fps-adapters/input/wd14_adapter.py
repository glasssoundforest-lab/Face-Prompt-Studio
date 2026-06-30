"""
fps-adapters/input/wd14_adapter.py — WD14 Tagger Adapter

WD14 タガー（wd-v1-4-*, wd-eva02-* 等）の出力を前処理する。

対応入力形式:
  1. 単純カンマ区切り: "1girl, blue_eyes, smile, masterpiece"
  2. 信頼度付き:       "1girl:0.998, blue_eyes:0.95, smile:0.42"
     （min_confidence 未満のタグは除去）
  3. 改行区切り:        "1girl\\nblue_eyes\\nsmile"
"""

from __future__ import annotations

import re

from .base_input_adapter import BaseInputAdapter

# WD14 特有のメタタグ（人数カウント等、顔プロンプトとして不要なものは除外候補）
WD14_RATING_TAGS = frozenset({"general", "sensitive", "questionable", "explicit"})


class WD14Adapter(BaseInputAdapter):
    """
    WD14 タガー出力アダプター。

    使い方:
        adapter = WD14Adapter(min_confidence=0.35)
        dsl = adapter.preprocess("1girl:0.998, blue_eyes:0.95, rating_safe:0.9")
        # → "1girl, blue_eyes"  (rating系・低信頼度タグは除去)
    """

    model_name = "wd14"

    def __init__(
        self,
        min_confidence: float = 0.35,
        exclude_rating_tags: bool = True,
        **kwargs: object,
    ) -> None:
        super().__init__(min_confidence=min_confidence, **kwargs)  # type: ignore[arg-type]
        self.exclude_rating_tags = exclude_rating_tags

    def preprocess(self, raw_output: str) -> str:
        """WD14 出力を DSL タグ文字列に変換する"""
        if not raw_output.strip():
            return ""

        # 改行・カンマ両対応で分割
        raw_tags = re.split(r"[,\n]", raw_output)

        tags: list[str] = []
        for raw_tag in raw_tags:
            raw_tag = raw_tag.strip()
            if not raw_tag:
                continue

            tag, confidence = self._parse_confidence(raw_tag)

            if confidence is not None and confidence < self.min_confidence:
                continue

            normalized = self.normalize_tag(tag)

            if self.exclude_rating_tags and self._is_rating_tag(normalized):
                continue

            tags.append(normalized)

        tags = self.remove_stopwords(tags)
        tags = self.deduplicate(tags)

        return ", ".join(tags)

    # ── Private ──────────────────────────────────────────────────

    def _parse_confidence(self, raw_tag: str) -> tuple[str, float | None]:
        """'tag:0.95' 形式から (tag, confidence) を抽出する"""
        if ":" in raw_tag:
            parts = raw_tag.rsplit(":", 1)
            try:
                confidence = float(parts[1])
                return parts[0].strip(), confidence
            except ValueError:
                pass
        return raw_tag, None

    def _is_rating_tag(self, tag: str) -> bool:
        """rating_safe / general 等の評価タグかどうか判定する"""
        if tag in WD14_RATING_TAGS:
            return True
        if tag.startswith("rating_") or tag.startswith("rating:"):
            return True
        return False
