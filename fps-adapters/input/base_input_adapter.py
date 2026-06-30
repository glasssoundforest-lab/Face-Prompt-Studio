"""
fps-adapters/input/base_input_adapter.py — Input Adapter 基底クラス

各キャプション/タガーモデルの生出力を、FPS パイプラインが解釈できる
DSL文字列（カンマ区切りタグリスト）に正規化する共通インターフェース。

fps-core から完全独立。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseInputAdapter(ABC):
    """
    入力モデルアダプターの基底クラス。

    使い方:
        class MyModelAdapter(BaseInputAdapter):
            model_name = "my_model"

            def preprocess(self, raw_output: str) -> str:
                # raw_output をクリーニングして DSL 文字列に変換
                return cleaned

    継承先は preprocess() のみ実装すればよい。
    confidence フィルタ・ストップワード除去など共通処理は基底クラスが提供する。
    """

    model_name: str = "generic"

    # 除去すべき定型フィラー語（自然言語キャプション系で頻出）
    DEFAULT_STOPWORDS: frozenset[str] = frozenset(
        {
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "this",
            "that",
            "image",
            "picture",
            "photo",
            "shows",
            "showing",
            "depicts",
        }
    )

    def __init__(
        self,
        min_confidence: float = 0.0,
        extra_stopwords: set[str] | None = None,
    ) -> None:
        """
        Args:
            min_confidence:  タグの信頼度フィルタ閾値（WD14等のタガー出力用）
            extra_stopwords: 追加で除去するストップワード
        """
        self.min_confidence = min_confidence
        self.stopwords = set(self.DEFAULT_STOPWORDS) | (extra_stopwords or set())

    @abstractmethod
    def preprocess(self, raw_output: str) -> str:
        """
        モデルの生出力を DSL カンマ区切りタグ文字列に変換する。

        Args:
            raw_output: モデルの生出力テキスト

        Returns:
            "tag1, tag2, tag3" 形式の文字列
            （DSL構文 (cat:val:weight) / [neg] / {con} もそのまま透過する）
        """
        ...

    def normalize_tag(self, tag: str) -> str:
        """単一タグを正規化する（小文字化・空白→アンダースコア）"""
        return tag.strip().lower().replace(" ", "_").replace("-", "_")

    def remove_stopwords(self, tags: list[str]) -> list[str]:
        """ストップワードに該当するタグを除去する"""
        return [t for t in tags if t.lower().strip() not in self.stopwords]

    def deduplicate(self, tags: list[str]) -> list[str]:
        """重複タグを順序を保ったまま除去する"""
        seen: set[str] = set()
        result: list[str] = []
        for t in tags:
            key = t.lower()
            if key not in seen:
                seen.add(key)
                result.append(t)
        return result

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"model_name='{self.model_name}', "
            f"min_confidence={self.min_confidence})"
        )
