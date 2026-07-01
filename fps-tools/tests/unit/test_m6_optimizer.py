"""
fps-tools/tests/unit/test_m6_optimizer.py

M6-1 ネガティブプロンプト最適化 テスト (40件)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from optimizer.conflict_detector import detect_cross_conflicts  # noqa: E402
from optimizer.manager import OptimizerManager  # noqa: E402
from optimizer.models import IssueType, QualityScore  # noqa: E402
from optimizer.quality_scorer import calculate_negative_coverage_score  # noqa: E402
from optimizer.redundancy_detector import detect_negative_redundancy  # noqa: E402


def make_tag(tag: str, category: str = "unknown", weight: float = 1.0, resolved: str = "") -> dict:
    return {"tag": tag, "category": category, "weight": weight,
            "meta": {"resolved": resolved or tag}}


# ══════════════════════════════════════════════════════════════════
# QualityScore: negative_coverage_score フィールド (5件)
# ══════════════════════════════════════════════════════════════════
class TestQualityScoreM6:
    def test_default_negative_coverage_is_zero(self):
        s = QualityScore(80.0, 70.0, 90.0, 80.0)
        assert s.negative_coverage_score == 0.0

    def test_set_negative_coverage(self):
        s = QualityScore(80.0, 70.0, 90.0, 80.0, negative_coverage_score=65.0)
        assert s.negative_coverage_score == 65.0

    def test_to_dict_includes_negative_coverage(self):
        s = QualityScore(80.0, 70.0, 90.0, 80.0, negative_coverage_score=50.0)
        d = s.to_dict()
        assert "negative_coverage_score" in d
        assert d["negative_coverage_score"] == 50.0

    def test_to_dict_backward_compat(self):
        """既存フィールドが壊れていないこと"""
        s = QualityScore(80.0, 70.0, 90.0, 80.0)
        d = s.to_dict()
        for key in ("coverage_score", "balance_score", "redundancy_score", "overall_score"):
            assert key in d

    def test_positional_4_args_still_valid(self):
        """位置引数4個での構築が後方互換できること"""
        s = QualityScore(100.0, 100.0, 100.0, 100.0)
        assert s.negative_coverage_score == 0.0


# ══════════════════════════════════════════════════════════════════
# detect_cross_conflicts (12件)
# ══════════════════════════════════════════════════════════════════
class TestCrossConflicts:
    def test_no_cross_conflict_empty(self):
        assert detect_cross_conflicts([], []) == []

    def test_no_cross_conflict_different_groups(self):
        pos = [make_tag("blue_eyes", resolved="Eyes.Blue")]
        neg = [make_tag("low_quality", resolved="Quality.Low")]
        issues = detect_cross_conflicts(pos, neg)
        assert not any(i.type == IssueType.CROSS_CONFLICT and
                       i.category == "eyes_color" for i in issues)

    def test_cross_conflict_same_eye_color(self):
        pos = [make_tag("blue_eyes", resolved="Eyes.Blue")]
        neg = [make_tag("blue_eyes", resolved="Eyes.Blue")]
        issues = detect_cross_conflicts(pos, neg)
        assert any(i.type == IssueType.CROSS_CONFLICT for i in issues)

    def test_cross_conflict_same_quality(self):
        pos = [make_tag("masterpiece", resolved="Quality.High")]
        neg = [make_tag("high_quality", resolved="Quality.High")]
        issues = detect_cross_conflicts(pos, neg)
        assert any(i.category == "quality_level" for i in issues)

    def test_cross_conflict_diff_eye_colors_info(self):
        """同グループの異なる値（blue vs brown）は INFO レベル"""
        pos = [make_tag("blue_eyes", resolved="Eyes.Blue")]
        neg = [make_tag("brown_eyes", resolved="Eyes.Brown")]
        issues = detect_cross_conflicts(pos, neg)
        assert len(issues) > 0

    def test_cross_conflict_issue_type(self):
        pos = [make_tag("blue_eyes", resolved="Eyes.Blue")]
        neg = [make_tag("blue_eyes", resolved="Eyes.Blue")]
        issues = detect_cross_conflicts(pos, neg)
        assert all(i.type == IssueType.CROSS_CONFLICT for i in issues)

    def test_cross_conflict_hair_color(self):
        pos = [make_tag("blonde_hair", resolved="Hair.Blonde")]
        neg = [make_tag("blonde_hair", resolved="Hair.Blonde")]
        issues = detect_cross_conflicts(pos, neg)
        assert any(i.category == "hair_color" for i in issues)

    def test_cross_conflict_smile_expression(self):
        pos = [make_tag("smile", resolved="Expression.Smile")]
        neg = [make_tag("smile", resolved="Expression.Smile")]
        issues = detect_cross_conflicts(pos, neg)
        assert any(i.category == "expression_smile" for i in issues)

    def test_cross_conflict_no_false_positive_unrelated(self):
        pos = [make_tag("blue_eyes", resolved="Eyes.Blue")]
        neg = [make_tag("long_hair", resolved="Hair.Long")]
        issues = detect_cross_conflicts(pos, neg)
        assert issues == []

    def test_cross_conflict_tags_field_populated(self):
        pos = [make_tag("blue_eyes", resolved="Eyes.Blue")]
        neg = [make_tag("blue_eyes", resolved="Eyes.Blue")]
        issues = detect_cross_conflicts(pos, neg)
        assert any(len(i.tags) > 0 for i in issues)

    def test_cross_conflict_suggestion_present(self):
        pos = [make_tag("masterpiece", resolved="Quality.High")]
        neg = [make_tag("masterpiece", resolved="Quality.High")]
        issues = detect_cross_conflicts(pos, neg)
        assert all(i.suggestion for i in issues)

    def test_cross_conflict_multiple_groups(self):
        pos = [make_tag("blue_eyes", resolved="Eyes.Blue"),
               make_tag("masterpiece", resolved="Quality.High")]
        neg = [make_tag("blue_eyes", resolved="Eyes.Blue"),
               make_tag("masterpiece", resolved="Quality.High")]
        issues = detect_cross_conflicts(pos, neg)
        assert len(issues) >= 2


# ══════════════════════════════════════════════════════════════════
# detect_negative_redundancy (8件)
# ══════════════════════════════════════════════════════════════════
class TestNegativeRedundancy:
    def test_empty_returns_empty(self):
        assert detect_negative_redundancy([]) == []

    def test_single_neg_tag_no_redundancy(self):
        tags = [make_tag("low_quality", resolved="Quality.Low")]
        assert detect_negative_redundancy(tags) == []

    def test_neg_low_quality_group(self):
        tags = [
            make_tag("low_quality", resolved="Quality.Low"),
            make_tag("worst_quality", resolved="Quality.Worst"),
        ]
        issues = detect_negative_redundancy(tags)
        assert any(i.type == IssueType.REDUNDANT for i in issues)

    def test_neg_blur_group(self):
        tags = [
            make_tag("blurry", resolved="Style.Blur"),
            make_tag("out_of_focus", resolved="Style.OutOfFocus"),
        ]
        issues = detect_negative_redundancy(tags)
        assert len(issues) > 0

    def test_neg_body_distortion_group(self):
        tags = [
            make_tag("bad_hands", resolved="Body.BadHands"),
            make_tag("extra_fingers", resolved="Body.ExtraFingers"),
        ]
        issues = detect_negative_redundancy(tags)
        assert len(issues) > 0

    def test_neg_redundancy_category_prefix(self):
        tags = [
            make_tag("low_quality", resolved="Quality.Low"),
            make_tag("worst_quality", resolved="Quality.Worst"),
        ]
        issues = detect_negative_redundancy(tags)
        assert all("neg_" in i.category for i in issues)

    def test_neg_redundancy_is_info_severity(self):
        from optimizer.models import IssueSeverity
        tags = [
            make_tag("low_quality", resolved="Quality.Low"),
            make_tag("worst_quality", resolved="Quality.Worst"),
        ]
        issues = detect_negative_redundancy(tags)
        assert any(i.severity == IssueSeverity.INFO for i in issues)

    def test_neg_unrelated_groups_no_cross_redundancy(self):
        tags = [
            make_tag("low_quality", resolved="Quality.Low"),
            make_tag("blurry", resolved="Style.Blur"),
        ]
        issues = detect_negative_redundancy(tags)
        # 別グループなので冗長ではない
        assert issues == []


# ══════════════════════════════════════════════════════════════════
# calculate_negative_coverage_score (5件)
# ══════════════════════════════════════════════════════════════════
class TestNegativeCoverage:
    def test_empty_returns_zero(self):
        assert calculate_negative_coverage_score([]) == 0.0

    def test_quality_covered(self):
        tags = [make_tag("low_quality", resolved="Quality.Low")]
        score = calculate_negative_coverage_score(tags)
        assert score > 0.0

    def test_full_coverage_high_score(self):
        tags = [
            make_tag("low_quality", resolved="Quality.Low"),
            make_tag("bad_anatomy", resolved="Body.BadAnatomy"),
            make_tag("blurry", resolved="Style.Blur"),
            make_tag("watermark", resolved="Style.Watermark"),
        ]
        score = calculate_negative_coverage_score(tags)
        assert score > 50.0

    def test_score_in_range(self):
        tags = [make_tag("low_quality", resolved="Quality.Low")]
        score = calculate_negative_coverage_score(tags)
        assert 0.0 <= score <= 100.0

    def test_unrelated_tags_return_zero(self):
        tags = [make_tag("random_tag", resolved="Unknown.Thing")]
        score = calculate_negative_coverage_score(tags)
        assert score == 0.0


# ══════════════════════════════════════════════════════════════════
# OptimizerManager.analyze() with negative_tags (10件)
# ══════════════════════════════════════════════════════════════════
class TestOptimizerManagerM6:
    def test_analyze_with_no_negative_returns_result(self):
        om = OptimizerManager()
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        result = om.analyze(tags)
        assert result.score.negative_coverage_score == 0.0

    def test_analyze_with_negative_sets_coverage(self):
        om = OptimizerManager()
        pos = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        neg = [make_tag("low_quality", "quality", resolved="Quality.Low")]
        result = om.analyze(pos, negative_tags=neg)
        assert result.score.negative_coverage_score > 0.0

    def test_analyze_detects_cross_conflict(self):
        om = OptimizerManager()
        pos = [make_tag("blue_eyes", "eyes", resolved="Eyes.Blue")]
        neg = [make_tag("blue_eyes", "eyes", resolved="Eyes.Blue")]
        result = om.analyze(pos, negative_tags=neg)
        assert any(i.type == IssueType.CROSS_CONFLICT for i in result.issues)

    def test_analyze_no_cross_conflict_unrelated(self):
        om = OptimizerManager()
        pos = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        neg = [make_tag("blurry", "style", resolved="Style.Blur")]
        result = om.analyze(pos, negative_tags=neg)
        assert not any(i.type == IssueType.CROSS_CONFLICT for i in result.issues)

    def test_analyze_negative_recommendations_present(self):
        om = OptimizerManager()
        pos = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        neg = [make_tag("low_quality", "quality", resolved="Quality.Low")]
        result = om.analyze(pos, negative_tags=neg)
        assert len(result.recommendations) > 0

    def test_analyze_no_negative_recommends_adding(self):
        om = OptimizerManager()
        pos = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        result = om.analyze(pos, negative_tags=None)
        assert any("ネガティブ" in r for r in result.recommendations)

    def test_analyze_negative_coverage_stored_in_score(self):
        om = OptimizerManager()
        pos = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        neg = [make_tag("low_quality", "quality", resolved="Quality.Low"),
               make_tag("blurry", "style", resolved="Style.Blur")]
        result = om.analyze(pos, negative_tags=neg)
        assert result.score.negative_coverage_score >= 0.0

    def test_analyze_cross_conflict_warnings_in_recommendations(self):
        om = OptimizerManager()
        pos = [make_tag("blue_eyes", "eyes", resolved="Eyes.Blue")]
        neg = [make_tag("blue_eyes", "eyes", resolved="Eyes.Blue")]
        result = om.analyze(pos, negative_tags=neg)
        assert any("競合" in r or "クロス" in r or "ネガティブ" in r for r in result.recommendations)

    def test_analyze_empty_negative_list(self):
        om = OptimizerManager()
        pos = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        result = om.analyze(pos, negative_tags=[])
        assert result.score.negative_coverage_score == 0.0

    def test_analyze_neg_redundancy_detected(self):
        om = OptimizerManager()
        pos = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        neg = [
            make_tag("low_quality", "quality", resolved="Quality.Low"),
            make_tag("worst_quality", "quality", resolved="Quality.Worst"),
        ]
        result = om.analyze(pos, negative_tags=neg)
        assert any(i.type == IssueType.REDUNDANT for i in result.issues)
