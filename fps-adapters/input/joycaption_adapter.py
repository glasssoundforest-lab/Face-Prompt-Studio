"""
fps-adapters/input/joycaption_adapter.py — JoyCaption Adapter

JoyCaption（自然言語の詳細キャプション）の出力を前処理する。

入力例:
  "A young woman with bright blue eyes and long flowing blonde hair,
   wearing a soft smile. She has fair skin and delicate features."

処理方針:
  1. 文をカンマ・接続詞（and/with）で分割してフレーズ化
  2. 主語（She/He/The woman 等）・be動詞・冠詞を除去
  3. アンダースコア結合してタグ化
"""

from __future__ import annotations

import re

from .base_input_adapter import BaseInputAdapter

_SUBJECT_PATTERN = re.compile(
    r"^(she|he|they|it|a|an|the)\s+"
    r"((young|old|tall|short)\s+)?"
    r"(woman|man|girl|boy|person|character|figure)?\s*"
    r"(has|is|wears|wearing|with)\s*",
    re.IGNORECASE,
)
_LEADING_ARTICLE = re.compile(r"^(a|an|the)\s+", re.IGNORECASE)
_LEADING_VERB = re.compile(r"^(wearing|has|having|is|with)\s+", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"[.!?]\s+")
_CLAUSE_SPLIT = re.compile(r",|\band\b|\bwith\b|\bwhile\b", re.IGNORECASE)


class JoyCaptionAdapter(BaseInputAdapter):
    """
    JoyCaption 出力アダプター。

    使い方:
        adapter = JoyCaptionAdapter()
        dsl = adapter.preprocess(
            "A young woman with bright blue eyes and long flowing "
            "blonde hair, wearing a soft smile."
        )
    """

    model_name = "joycaption"

    FILLER_PHRASES = frozenset(
        {
            "young",
            "woman",
            "man",
            "girl",
            "boy",
            "person",
            "character",
            "figure",
            "appears",
            "appearing",
            "seems",
            "seemingly",
            "overall",
            "background",
            "foreground",
            "image",
            "photo",
        }
    )

    def preprocess(self, raw_output: str) -> str:
        """JoyCaption の自然言語キャプションを DSL タグ文字列に変換する"""
        if not raw_output.strip():
            return ""

        sentences = _SENTENCE_SPLIT.split(raw_output.strip())

        phrases: list[str] = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence = _SUBJECT_PATTERN.sub("", sentence)
            clauses = _CLAUSE_SPLIT.split(sentence)

            for clause in clauses:
                clause = clause.strip()
                clause = _LEADING_ARTICLE.sub("", clause)
                clause = _LEADING_VERB.sub("", clause)
                clause = _LEADING_ARTICLE.sub("", clause)  # "wearing a soft smile" 対応で2段除去
                if not clause:
                    continue
                tag = self._phrase_to_tag(clause)
                if tag:
                    phrases.append(tag)

        phrases = self.remove_stopwords(phrases)
        phrases = [p for p in phrases if p.lower() not in self.FILLER_PHRASES]
        phrases = [p for p in phrases if p]
        phrases = self.deduplicate(phrases)

        return ", ".join(phrases)

    # ── Private ──────────────────────────────────────────────────

    def _phrase_to_tag(self, phrase: str) -> str:
        """自然言語フレーズをタグ形式に変換する"""
        phrase = phrase.strip(" .,!?")
        if not phrase:
            return ""

        words = phrase.split()
        if not words or len(words) > 5:
            return ""

        return self.normalize_tag(phrase)
