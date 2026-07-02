"""
fps-core/ai/negative_learner.py — ネガティブプロンプト学習
★ v2.5 新設

ネガティブプロンプトの使用履歴から頻出タグを学習し、
低スコア履歴の pos タグから自動除外候補を抽出する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NegativeTagEntry:
    """ネガティブタグエントリ"""
    tag:          str
    neg_count:    int   = 0     # ネガティブとして使われた回数
    avoid_count:  int   = 0     # 低スコア時の pos に含まれていた回数
    score_impact: float = 0.0   # スコアへの影響度（負なら避けるべき）
    last_seen:    str   = ""

    @property
    def priority(self) -> float:
        """高いほど neg に入れるべき"""
        return self.neg_count * 1.5 + self.avoid_count * 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag":          self.tag,
            "neg_count":    self.neg_count,
            "avoid_count":  self.avoid_count,
            "score_impact": round(self.score_impact, 2),
            "priority":     round(self.priority, 1),
            "last_seen":    self.last_seen,
        }


class NegativeLearner:
    """
    ネガティブプロンプト学習クラス。

    History から以下を学習する:
    1. ネガティブに頻繁に使われているタグ → neg 候補
    2. スコアが低い履歴の pos タグ → 除外候補

    使い方:
        learner = NegativeLearner()
        learner.learn(history_entries)
        recs = learner.recommend_negative(n=20)
    """

    _LOW_SCORE_THRESHOLD = 40.0   # このスコア未満は「低スコア」とみなす
    _MIN_COUNT = 2                 # 最低この回数出現しないと推奨しない

    def __init__(self) -> None:
        self._neg_tags:   dict[str, NegativeTagEntry] = {}
        self._avoid_tags: dict[str, NegativeTagEntry] = {}
        self._total_entries = 0
        self._last_learned: datetime | None = None

    def learn(self, history_entries: list[Any]) -> dict[str, int]:
        """
        History エントリからネガティブタグを学習する。

        Args:
            history_entries: HistoryEntry リスト

        Returns:
            {"neg_learned": N, "avoid_learned": N, "total": N}
        """
        neg_learned = avoid_learned = 0
        now = datetime.now().isoformat()

        for entry in history_entries:
            self._total_entries += 1

            # ① ネガティブプロンプトからタグを学習
            neg_prompt = getattr(entry, "output_negative", "") or ""
            for raw_tag in neg_prompt.split(","):
                tag = raw_tag.strip().lower()
                if not tag:
                    continue
                if tag not in self._neg_tags:
                    self._neg_tags[tag] = NegativeTagEntry(tag=tag)
                    neg_learned += 1
                e = self._neg_tags[tag]
                e.neg_count += 1
                e.last_seen = now

            # ② 低スコアの pos タグを「避けるべきタグ候補」として学習
            score = getattr(entry, "overall_score", 100.0)
            if score < self._LOW_SCORE_THRESHOLD:
                pos_prompt = getattr(entry, "output_prompt", "") or ""
                for raw_tag in pos_prompt.split(","):
                    tag = raw_tag.strip().lower()
                    if not tag:
                        continue
                    if tag not in self._avoid_tags:
                        self._avoid_tags[tag] = NegativeTagEntry(tag=tag)
                        avoid_learned += 1
                    e = self._avoid_tags[tag]
                    e.avoid_count += 1
                    # スコア影響: 低スコアほど影響度が大きい
                    e.score_impact -= (self._LOW_SCORE_THRESHOLD - score) / 100
                    e.last_seen = now

        self._last_learned = datetime.now()
        return {
            "neg_learned":   neg_learned,
            "avoid_learned": avoid_learned,
            "total":         len(self._neg_tags),
        }

    def recommend_negative(
        self,
        n: int = 20,
        include_avoid: bool = True,
    ) -> list[NegativeTagEntry]:
        """
        ネガティブプロンプトに追加すべきタグを推奨する。

        Args:
            n:              返す件数
            include_avoid:  低スコア pos タグも含めるか

        Returns:
            優先度順のタグリスト
        """
        candidates: dict[str, NegativeTagEntry] = {}

        # ① よく使われるネガティブタグ
        for tag, e in self._neg_tags.items():
            if e.neg_count >= self._MIN_COUNT:
                candidates[tag] = e

        # ② 低スコア履歴の pos タグ（avoid_count が多いもの）
        if include_avoid:
            for tag, e in self._avoid_tags.items():
                if e.avoid_count >= self._MIN_COUNT and tag not in candidates:
                    candidates[tag] = e

        result = sorted(candidates.values(), key=lambda e: -e.priority)
        return result[:n]

    def suggest_negative_for_prompt(
        self,
        pos_tags: list[str],
        n: int = 15,
    ) -> list[NegativeTagEntry]:
        """
        指定した pos タグリストに対してネガティブ候補を提案する。
        pos に含まれるタグは除外する。
        """
        pos_set = set(t.strip().lower() for t in pos_tags)
        recs = self.recommend_negative(n=n * 2)
        return [e for e in recs if e.tag not in pos_set][:n]

    def statistics(self) -> dict[str, Any]:
        return {
            "neg_tag_count":   len(self._neg_tags),
            "avoid_tag_count": len(self._avoid_tags),
            "total_entries":   self._total_entries,
            "last_learned":    self._last_learned.isoformat()
                               if self._last_learned else None,
        }

    def to_profile_data(self) -> dict[str, Any]:
        """UserProfile の neg_frequencies に保存できる形式で返す"""
        return {
            "neg_tags":   {k: v.to_dict() for k, v in self._neg_tags.items()},
            "avoid_tags": {k: v.to_dict() for k, v in self._avoid_tags.items()},
        }
