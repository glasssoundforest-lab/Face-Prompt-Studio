"""
fps-adapters/input/florence2_adapter.py — Florence2 Adapter

Florence2 の出力を前処理する。

対応入力形式:
  1. タスクトークン付き: "<MORE_DETAILED_CAPTION>A woman with blue eyes..."
  2. プレーン自然文（JoyCaption 同様の処理を流用）

Florence2 はタスクプレフィックストークンを含むことが多いため、
それを除去してから JoyCaption と同様の自然言語処理を適用する。
"""

from __future__ import annotations

import re

from .joycaption_adapter import JoyCaptionAdapter

_TASK_TOKEN_PATTERN = re.compile(r"<[A-Z_]+>")


class Florence2Adapter(JoyCaptionAdapter):
    """
    Florence2 出力アダプター。

    JoyCaptionAdapter の自然言語処理ロジックを継承し、
    Florence2 特有のタスクトークン除去を追加する。

    使い方:
        adapter = Florence2Adapter()
        dsl = adapter.preprocess(
            "<MORE_DETAILED_CAPTION>A woman with captivating blue eyes "
            "and cascading hair."
        )
    """

    model_name = "florence2"

    def preprocess(self, raw_output: str) -> str:
        """Florence2 出力からタスクトークンを除去してから自然言語処理する"""
        cleaned = _TASK_TOKEN_PATTERN.sub("", raw_output).strip()
        return super().preprocess(cleaned)
