"""
fps-core/ai/consistency_checker.py — スタイル一貫性スコア
★ v2.5 新設

複数のプロンプト・タグセット間のスタイル一貫性を分析する。
同一キャラクター・スタイルの一連の画像生成に使用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConsistencyResult:
    """一貫性チェック結果"""
    overall_score:    float          # 0〜100
    category_scores:  dict[str, float]   # カテゴリ別一貫性スコア
    common_tags:      list[str]      # 全セット共通のタグ
    inconsistent_tags: list[str]     # セット間で矛盾するタグ
    missing_tags:     list[str]      # 一部セットにしかないタグ
    recommendations:  list[str]      # 改善提案
    detail:           list[dict]     # セット別詳細

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score":    round(self.overall_score, 1),
            "category_scores":  {k: round(v, 1)
                                  for k, v in self.category_scores.items()},
            "common_tags":      self.common_tags,
            "inconsistent_tags": self.inconsistent_tags,
            "missing_tags":     self.missing_tags[:20],
            "recommendations":  self.recommendations,
            "detail":           self.detail,
        }


class ConsistencyChecker:
    """
    スタイル一貫性チェッカー。

    複数プロンプトのタグセットを比較し、
    キャラクター・スタイルの一貫性スコアを算出する。

    使い方:
        checker = ConsistencyChecker(dictionary_manager=dm)
        result = checker.check([
            "masterpiece, 1girl, blue_eyes, blonde_hair, school_uniform",
            "masterpiece, 1girl, blue_eyes, blonde_hair, casual_wear",
            "best_quality, 1girl, green_eyes, blonde_hair, school_uniform",
        ])
        print(f"一貫性スコア: {result.overall_score}")
        print(f"矛盾タグ: {result.inconsistent_tags}")
    """

    # カテゴリの重要度（一貫性に影響する度合い）
    _CATEGORY_WEIGHTS = {
        "eyes":       2.0,   # 目の色は必ず統一すべき
        "hair":       2.0,   # 髪の色も統一すべき
        "face_shape": 1.5,
        "skin":       1.5,
        "ethnicity":  1.5,
        "style":      1.2,
        "quality":    1.0,
        "lighting":   0.8,
        "clothing":   0.5,   # 服は変えてもよい
        "pose":       0.3,   # ポーズは変えてもよい
        "scene":      0.3,
    }

    # 同じカテゴリ内で矛盾する可能性があるタググループ
    _CONFLICT_GROUPS = [
        {"blue_eyes", "green_eyes", "brown_eyes", "red_eyes", "gold_eyes",
         "silver_eyes", "purple_eyes", "black_eyes", "gray_eyes"},
        {"blonde_hair", "black_hair", "brown_hair", "red_hair", "silver_hair",
         "blue_hair", "pink_hair", "gradient_hair", "white_hair"},
        {"short_hair", "medium_hair", "long_hair"},
        {"pale_skin", "tan_skin", "dark_skin", "tanned_skin"},
        {"1girl", "1boy", "2girls", "2boys", "multiple_girls"},
    ]

    def __init__(self, dictionary_manager: Any = None) -> None:
        self._dm = dictionary_manager

    def check(
        self,
        prompt_list: list[str],
        labels: list[str] | None = None,
    ) -> ConsistencyResult:
        """
        複数プロンプトの一貫性をチェックする。

        Args:
            prompt_list: プロンプト文字列のリスト
            labels:      各プロンプトのラベル（省略可）

        Returns:
            ConsistencyResult
        """
        if len(prompt_list) < 2:
            return ConsistencyResult(
                overall_score=100.0,
                category_scores={},
                common_tags=[],
                inconsistent_tags=[],
                missing_tags=[],
                recommendations=["比較には2件以上のプロンプトが必要です"],
                detail=[],
            )

        labels = labels or [f"prompt_{i+1}" for i in range(len(prompt_list))]
        tag_sets = [self._parse_tags(p) for p in prompt_list]

        # 共通タグ
        common = set(tag_sets[0])
        for ts in tag_sets[1:]:
            common &= ts
        common_tags = sorted(common)

        # 矛盾タグ（同一グループで異なるタグが使われている）
        inconsistent: list[str] = []
        for group in self._CONFLICT_GROUPS:
            used_per_set = [ts & group for ts in tag_sets]
            all_used = set()
            for s in used_per_set:
                all_used |= s
            if len(all_used) > 1:
                inconsistent.extend(sorted(all_used))

        # 一部にしかないタグ
        all_tags = set()
        for ts in tag_sets:
            all_tags |= ts
        partial = [t for t in all_tags if not all(t in ts for ts in tag_sets)]
        missing_tags = sorted(partial)

        # カテゴリ別スコア
        category_scores = self._calc_category_scores(tag_sets)

        # 全体スコア
        overall = self._calc_overall_score(
            common_count=len(common_tags),
            total_tags=len(all_tags),
            inconsistent_count=len(set(inconsistent)),
            category_scores=category_scores,
        )

        # 推奨事項
        recommendations = self._build_recommendations(
            inconsistent, missing_tags, category_scores
        )

        # セット別詳細
        detail = [
            {
                "label":       labels[i],
                "tags":        sorted(tag_sets[i]),
                "unique_tags": sorted(tag_sets[i] - common),
                "tag_count":   len(tag_sets[i]),
            }
            for i in range(len(tag_sets))
        ]

        return ConsistencyResult(
            overall_score=overall,
            category_scores=category_scores,
            common_tags=common_tags,
            inconsistent_tags=list(set(inconsistent)),
            missing_tags=missing_tags,
            recommendations=recommendations,
            detail=detail,
        )

    # ── 内部処理 ──────────────────────────────────────────────────

    @staticmethod
    def _parse_tags(prompt: str) -> set[str]:
        """プロンプト文字列からタグセットを生成する"""
        import re
        # (tag:weight) 形式のウェイトを除去
        cleaned = re.sub(r'\(([^:)]+):[^)]+\)', r'', prompt)
        tags = {t.strip().lower().replace(" ", "_")
                for t in cleaned.split(",") if t.strip()}
        return tags

    def _get_category(self, tag: str) -> str:
        if not self._dm:
            return ""
        try:
            return self._dm.lookup(tag).category or ""
        except Exception:
            return ""

    def _calc_category_scores(
        self, tag_sets: list[set[str]]
    ) -> dict[str, float]:
        """カテゴリ別の一貫性スコアを計算する"""
        scores: dict[str, float] = {}
        # カテゴリ別に各セットのタグを集める
        cat_tags: dict[str, list[set[str]]] = {}
        for ts in tag_sets:
            cat_in_set: dict[str, set[str]] = {}
            for tag in ts:
                cat = self._get_category(tag)
                if cat:
                    cat_in_set.setdefault(cat, set()).add(tag)
            for cat, tags in cat_in_set.items():
                cat_tags.setdefault(cat, []).append(tags)

        for cat, sets_list in cat_tags.items():
            if len(sets_list) < 2:
                continue
            # Jaccard 類似度の平均
            total = 0.0
            count = 0
            for i in range(len(sets_list)):
                for j in range(i + 1, len(sets_list)):
                    a, b = sets_list[i], sets_list[j]
                    union = len(a | b)
                    inter = len(a & b)
                    total += (inter / union * 100) if union else 100.0
                    count += 1
            scores[cat] = round(total / count, 1) if count else 100.0

        return scores

    def _calc_overall_score(
        self,
        common_count: int,
        total_tags: int,
        inconsistent_count: int,
        category_scores: dict[str, float],
    ) -> float:
        """総合スコアを算出する"""
        if total_tags == 0:
            return 100.0

        # ベーススコア: 共通タグ比率
        base = (common_count / total_tags) * 100

        # カテゴリ加重平均
        weighted_sum = 0.0
        weight_total = 0.0
        for cat, score in category_scores.items():
            w = self._CATEGORY_WEIGHTS.get(cat, 1.0)
            weighted_sum += score * w
            weight_total += w
        cat_avg = (weighted_sum / weight_total) if weight_total else base

        # 矛盾ペナルティ
        penalty = min(inconsistent_count * 5, 30)

        score = (base * 0.3 + cat_avg * 0.7) - penalty
        return max(0.0, min(100.0, round(score, 1)))

    def _build_recommendations(
        self,
        inconsistent: list[str],
        missing: list[str],
        category_scores: dict[str, float],
    ) -> list[str]:
        recs: list[str] = []
        if inconsistent:
            groups_found = []
            for group in self._CONFLICT_GROUPS:
                conflict = set(inconsistent) & group
                if len(conflict) > 1:
                    groups_found.append("、".join(sorted(conflict)))
            if groups_found:
                recs.append(
                    f"矛盾するタグを統一してください: {' / '.join(groups_found)}"
                )
        low_cats = [(cat, score) for cat, score in category_scores.items()
                    if score < 70 and cat in self._CATEGORY_WEIGHTS]
        low_cats.sort(key=lambda x: x[1])
        for cat, score in low_cats[:3]:
            recs.append(
                f"「{cat}」カテゴリの一貫性が低いです（スコア: {score:.0f}）"
            )
        if not recs:
            recs.append("スタイルの一貫性は良好です")
        return recs
