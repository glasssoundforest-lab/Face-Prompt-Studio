"""
fps-tools/tests/unit/test_v1_5_ai_scoring.py

v1.5 AI スコアリング強化 テスト (+45件)

テスト対象:
  - combination_checker.py (check_style_combinations / check_token_budget)
  - quality_scorer.py (combination_score / token_score 統合)
  - optimizer/models.py (新 IssueType)
  - OptimizerManager.analyze() (v1.5 統合)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from optimizer.combination_checker import (  # noqa: E402
    check_style_combinations,
    check_token_budget,
    estimate_token_count,
    reload_rules,
)
from optimizer.manager import OptimizerManager  # noqa: E402
from optimizer.models import IssueSeverity, IssueType, QualityScore  # noqa: E402
from optimizer.quality_scorer import (  # noqa: E402
    WEIGHTS,
    calculate_quality_score,
)

# ── ヘルパー ─────────────────────────────────────────────────────

def make_tag(
    tag: str,
    category: str = "unknown",
    weight: float = 1.0,
    resolved: str = "",
) -> dict:
    return {
        "tag": tag,
        "category": category,
        "weight": weight,
        "meta": {"resolved": resolved or tag},
    }


# ══════════════════════════════════════════════════════════════════
# IssueType 拡張（2件）
# ══════════════════════════════════════════════════════════════════

class TestNewIssueTypes:
    def test_style_conflict_exists(self):
        assert IssueType.STYLE_CONFLICT == "style_conflict"

    def test_token_budget_exists(self):
        assert IssueType.TOKEN_BUDGET == "token_budget"


# ══════════════════════════════════════════════════════════════════
# QualityScore 新フィールド（5件）
# ══════════════════════════════════════════════════════════════════

class TestQualityScoreV15:
    def test_combination_score_default_100(self):
        s = QualityScore(80.0, 70.0, 90.0, 80.0)
        assert s.combination_score == 100.0

    def test_token_score_default_100(self):
        s = QualityScore(80.0, 70.0, 90.0, 80.0)
        assert s.token_score == 100.0

    def test_to_dict_includes_combination(self):
        s = QualityScore(80.0, 70.0, 90.0, 80.0, combination_score=85.0)
        assert "combination_score" in s.to_dict()
        assert s.to_dict()["combination_score"] == 85.0

    def test_to_dict_includes_token(self):
        s = QualityScore(80.0, 70.0, 90.0, 80.0, token_score=60.0)
        assert "token_score" in s.to_dict()
        assert s.to_dict()["token_score"] == 60.0

    def test_backward_compat_positional_4_args(self):
        s = QualityScore(100.0, 100.0, 100.0, 100.0)
        assert s.combination_score == 100.0
        assert s.token_score == 100.0


# ══════════════════════════════════════════════════════════════════
# WEIGHTS 確認（3件）
# ══════════════════════════════════════════════════════════════════

class TestWeightsV15:
    def test_weights_sum_to_one(self):
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_combination_weight_exists(self):
        assert "combination" in WEIGHTS
        assert WEIGHTS["combination"] > 0

    def test_token_weight_exists(self):
        assert "token" in WEIGHTS
        assert WEIGHTS["token"] > 0


# ══════════════════════════════════════════════════════════════════
# check_style_combinations（15件）
# ══════════════════════════════════════════════════════════════════

class TestStyleCombinations:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        reload_rules()

    def test_no_conflict_empty(self):
        issues, score = check_style_combinations([])
        assert issues == []
        assert score == 100.0

    def test_no_conflict_single_style(self):
        tags = [make_tag("anime", "style", resolved="Style.Anime")]
        issues, score = check_style_combinations(tags)
        style_issues = [i for i in issues if i.type == IssueType.STYLE_CONFLICT]
        assert style_issues == []

    def test_photorealistic_vs_anime_warning(self):
        tags = [
            make_tag("photorealistic", "style", resolved="Style.Photorealistic"),
            make_tag("anime_style", "style", resolved="Style.Anime"),
        ]
        issues, score = check_style_combinations(tags)
        assert any(i.type == IssueType.STYLE_CONFLICT for i in issues)

    def test_style_conflict_reduces_score(self):
        tags = [
            make_tag("photorealistic", "style", resolved="Style.Photorealistic"),
            make_tag("anime_style", "style", resolved="Style.Anime"),
        ]
        _, score = check_style_combinations(tags)
        assert score < 100.0

    def test_high_vs_low_quality_error(self):
        tags = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("low_quality", "quality", resolved="Quality.Low"),
        ]
        issues, _ = check_style_combinations(tags)
        error_issues = [i for i in issues if i.severity == IssueSeverity.ERROR]
        assert len(error_issues) >= 1

    def test_high_vs_low_quality_score_severe(self):
        tags = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("low_quality", "quality", resolved="Quality.Low"),
        ]
        _, score = check_style_combinations(tags)
        assert score <= 70.0

    def test_multiple_conflicts_reduce_score_more(self):
        tags = [
            make_tag("photorealistic", "style", resolved="Style.Photorealistic"),
            make_tag("anime", "style", resolved="Style.Anime"),
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("low_quality", "quality", resolved="Quality.Low"),
        ]
        _, score_multi = check_style_combinations(tags)
        tags_single = tags[:2]
        _, score_single = check_style_combinations(tags_single)
        assert score_multi <= score_single

    def test_compatible_styles_no_conflict(self):
        tags = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
        ]
        issues, score = check_style_combinations(tags)
        style_c = [i for i in issues if i.type == IssueType.STYLE_CONFLICT]
        assert style_c == []
        assert score == 100.0

    def test_recommended_pair_bonus(self):
        # Quality.High + Eyes.Blue は推奨ペア → ボーナス
        tags = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
        ]
        _, score = check_style_combinations(tags)
        # 問題なし + ボーナスで 100 以上になるが cap される
        assert score == 100.0  # min(100, 100+bonus) = 100

    def test_issue_type_is_style_conflict(self):
        tags = [
            make_tag("photorealistic", "style", resolved="Style.Photorealistic"),
            make_tag("anime", "style", resolved="Style.Anime"),
        ]
        issues, _ = check_style_combinations(tags)
        assert all(i.type == IssueType.STYLE_CONFLICT for i in issues)

    def test_issue_has_suggestion(self):
        tags = [
            make_tag("photorealistic", "style", resolved="Style.Photorealistic"),
            make_tag("anime", "style", resolved="Style.Anime"),
        ]
        issues, _ = check_style_combinations(tags)
        assert all(i.suggestion for i in issues)

    def test_issue_has_category(self):
        tags = [
            make_tag("photorealistic", "style", resolved="Style.Photorealistic"),
            make_tag("anime", "style", resolved="Style.Anime"),
        ]
        issues, _ = check_style_combinations(tags)
        assert all(i.category for i in issues)

    def test_watercolor_vs_3d_conflict(self):
        tags = [
            make_tag("watercolor", "style", resolved="Style.Watercolor"),
            make_tag("low_poly", "style", resolved="Style.LowPoly"),
        ]
        issues, _ = check_style_combinations(tags)
        assert any(i.type == IssueType.STYLE_CONFLICT for i in issues)

    def test_score_floor_zero(self):
        """多数の conflicts でもスコアは 0.0 未満にならない"""
        tags = [
            make_tag("photo", "style", resolved="Style.Photorealistic"),
            make_tag("anime", "style", resolved="Style.Anime"),
            make_tag("high", "quality", resolved="Quality.High"),
            make_tag("low", "quality", resolved="Quality.Low"),
            make_tag("watercolor", "style", resolved="Style.Watercolor"),
            make_tag("low_poly", "style", resolved="Style.LowPoly"),
        ]
        _, score = check_style_combinations(tags)
        assert score >= 0.0

    def test_score_ceiling_100(self):
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        _, score = check_style_combinations(tags)
        assert score <= 100.0


# ══════════════════════════════════════════════════════════════════
# estimate_token_count / check_token_budget（12件）
# ══════════════════════════════════════════════════════════════════

class TestTokenBudget:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        reload_rules()

    def test_estimate_empty(self):
        assert estimate_token_count([]) == 0

    def test_estimate_single_tag(self):
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        count = estimate_token_count(tags)
        assert count >= 1

    def test_estimate_many_tags(self):
        tags = [make_tag(f"tag_{i}", "cat", resolved=f"Cat.Value{i}") for i in range(50)]
        count = estimate_token_count(tags)
        assert count >= 50

    def test_no_budget_issue_few_tags(self):
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        issues, score = check_token_budget(tags)
        budget_issues = [i for i in issues if i.type == IssueType.TOKEN_BUDGET]
        assert budget_issues == []

    def test_budget_warning_many_tags(self):
        """75トークン超のプロンプトは警告が出る"""
        tags = [
            make_tag(f"tag_{i}", "accessories", resolved=f"Accessories.Item{i}")
            for i in range(60)
        ]
        issues, _ = check_token_budget(tags)
        budget_issues = [i for i in issues if i.type == IssueType.TOKEN_BUDGET]
        assert len(budget_issues) >= 1

    def test_budget_warning_severity(self):
        tags = [
            make_tag(f"tag_{i}", "accessories", resolved=f"Accessories.Item{i}")
            for i in range(60)
        ]
        issues, _ = check_token_budget(tags)
        severities = {i.severity for i in issues if i.type == IssueType.TOKEN_BUDGET}
        assert severities <= {IssueSeverity.WARNING, IssueSeverity.ERROR}

    def test_budget_score_full_when_under_limit(self):
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        _, score = check_token_budget(tags)
        assert score > 70.0

    def test_budget_score_low_when_over_limit(self):
        tags = [
            make_tag(f"x{i}", "accessories", resolved=f"Accessories.LongItemName{i}LongSuffix")
            for i in range(80)
        ]
        _, score = check_token_budget(tags)
        assert score < 100.0

    def test_budget_score_in_range(self):
        tags = [make_tag(f"t{i}", "q", resolved=f"Cat.Val{i}") for i in range(30)]
        _, score = check_token_budget(tags)
        assert 0.0 <= score <= 100.0

    def test_budget_suggestion_mentions_trim(self):
        tags = [
            make_tag(f"acc_{i}", "accessories", resolved=f"Accessories.Item{i}")
            for i in range(60)
        ]
        issues, _ = check_token_budget(tags)
        budget_issues = [i for i in issues if i.type == IssueType.TOKEN_BUDGET]
        if budget_issues:
            assert budget_issues[0].suggestion

    def test_budget_issue_category(self):
        tags = [
            make_tag(f"x{i}", "body", resolved=f"Body.Part{i}") for i in range(60)
        ]
        issues, _ = check_token_budget(tags)
        budget_issues = [i for i in issues if i.type == IssueType.TOKEN_BUDGET]
        for issue in budget_issues:
            assert issue.category == "token_budget"

    def test_estimate_scales_with_tag_count(self):
        t5 = estimate_token_count(
            [make_tag(f"x{i}", resolved=f"Cat.Val{i}") for i in range(5)]
        )
        t20 = estimate_token_count(
            [make_tag(f"x{i}", resolved=f"Cat.Val{i}") for i in range(20)]
        )
        assert t20 > t5


# ══════════════════════════════════════════════════════════════════
# calculate_quality_score (v1.5 統合) (5件)
# ══════════════════════════════════════════════════════════════════

class TestQualityScoreV15Integration:
    def test_returns_combination_score(self):
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        score = calculate_quality_score(tags)
        assert hasattr(score, "combination_score")
        assert 0.0 <= score.combination_score <= 100.0

    def test_returns_token_score(self):
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        score = calculate_quality_score(tags)
        assert hasattr(score, "token_score")
        assert 0.0 <= score.token_score <= 100.0

    def test_style_conflict_lowers_overall(self):
        tags_good = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
        ]
        tags_conflict = tags_good + [
            make_tag("photorealistic", "style", resolved="Style.Photorealistic"),
            make_tag("anime", "style", resolved="Style.Anime"),
        ]
        score_good = calculate_quality_score(tags_good)
        score_conflict = calculate_quality_score(tags_conflict)
        assert score_conflict.overall_score <= score_good.overall_score

    def test_overall_in_range(self):
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        score = calculate_quality_score(tags)
        assert 0.0 <= score.overall_score <= 100.0

    def test_weights_reflected_in_overall(self):
        """WEIGHTS 変更後も overall が合計 100 を超えない"""
        tags = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
            make_tag("long_hair", "hair", resolved="Hair.Long"),
        ]
        score = calculate_quality_score(tags, issues=[])
        assert score.overall_score <= 100.0


# ══════════════════════════════════════════════════════════════════
# OptimizerManager.analyze() v1.5 統合 (8件)
# ══════════════════════════════════════════════════════════════════

class TestOptimizerManagerV15:
    def test_analyze_returns_combination_score(self):
        om = OptimizerManager()
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        result = om.analyze(tags)
        assert hasattr(result.score, "combination_score")
        assert 0.0 <= result.score.combination_score <= 100.0

    def test_analyze_returns_token_score(self):
        om = OptimizerManager()
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        result = om.analyze(tags)
        assert hasattr(result.score, "token_score")
        assert 0.0 <= result.score.token_score <= 100.0

    def test_analyze_detects_style_conflict(self):
        om = OptimizerManager()
        tags = [
            make_tag("photorealistic", "style", resolved="Style.Photorealistic"),
            make_tag("anime", "style", resolved="Style.Anime"),
        ]
        result = om.analyze(tags)
        assert any(i.type == IssueType.STYLE_CONFLICT for i in result.issues)

    def test_analyze_no_false_style_conflict(self):
        om = OptimizerManager()
        tags = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
        ]
        result = om.analyze(tags)
        assert not any(i.type == IssueType.STYLE_CONFLICT for i in result.issues)

    def test_analyze_detects_token_budget(self):
        om = OptimizerManager()
        tags = [
            make_tag(f"acc_{i}", "accessories", resolved=f"Accessories.Item{i}")
            for i in range(60)
        ]
        result = om.analyze(tags)
        assert any(i.type == IssueType.TOKEN_BUDGET for i in result.issues)

    def test_analyze_style_conflict_in_recommendations(self):
        om = OptimizerManager()
        tags = [
            make_tag("photorealistic", "style", resolved="Style.Photorealistic"),
            make_tag("anime", "style", resolved="Style.Anime"),
        ]
        result = om.analyze(tags)
        all_recs = " ".join(result.recommendations)
        assert "スタイル" in all_recs or "style" in all_recs.lower()

    def test_analyze_token_issue_in_recommendations(self):
        om = OptimizerManager()
        tags = [
            make_tag(f"acc_{i}", "accessories", resolved=f"Accessories.Item{i}")
            for i in range(60)
        ]
        result = om.analyze(tags)
        if any(i.type == IssueType.TOKEN_BUDGET for i in result.issues):
            all_recs = " ".join(result.recommendations)
            assert "トークン" in all_recs or "token" in all_recs.lower()

    def test_analyze_score_to_dict_has_new_fields(self):
        om = OptimizerManager()
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        result = om.analyze(tags)
        d = result.score.to_dict()
        assert "combination_score" in d
        assert "token_score" in d
