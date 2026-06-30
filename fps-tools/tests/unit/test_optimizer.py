"""
fps-tools/tests/unit/test_optimizer.py

OptimizerManager のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_optimizer.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from optimizer.conflict_detector import detect_conflicts
from optimizer.manager import OptimizerManager
from optimizer.models import (
    IssueSeverity,
    IssueType,
    OptimizationIssue,
    OptimizationResult,
    QualityScore,
)
from optimizer.quality_scorer import (
    calculate_balance_score,
    calculate_coverage_score,
    calculate_quality_score,
    calculate_redundancy_score,
)
from optimizer.recommender import generate_recommendations, suggest_missing_tags
from optimizer.redundancy_detector import detect_redundancy


def make_tag(tag: str, category: str, weight: float = 1.0, resolved: str = "") -> dict:
    return {
        "tag": tag,
        "category": category,
        "weight": weight,
        "meta": {"resolved": resolved or tag},
    }


# ══════════════════════════════════════════════════════════════════
# models
# ══════════════════════════════════════════════════════════════════

class TestModels:
    def test_quality_score_to_dict(self):
        s = QualityScore(80.0, 70.0, 90.0, 80.0)
        d = s.to_dict()
        assert d["overall_score"] == 80.0

    def test_optimization_result_has_errors(self):
        issue = OptimizationIssue(
            type=IssueType.CONFLICT, severity=IssueSeverity.ERROR, message="x"
        )
        result = OptimizationResult(
            score=QualityScore(0, 0, 0, 0), issues=[issue]
        )
        assert result.has_errors is True
        assert result.has_warnings is False

    def test_optimization_result_issue_count(self):
        issues = [
            OptimizationIssue(type=IssueType.CONFLICT, severity=IssueSeverity.WARNING, message="a"),
            OptimizationIssue(type=IssueType.REDUNDANT, severity=IssueSeverity.INFO, message="b"),
        ]
        result = OptimizationResult(score=QualityScore(0, 0, 0, 0), issues=issues)
        assert result.issue_count == 2


# ══════════════════════════════════════════════════════════════════
# conflict_detector
# ══════════════════════════════════════════════════════════════════

class TestConflictDetector:
    def test_no_conflict_single_eye_color(self):
        tags = [make_tag("blue_eyes", "eyes", resolved="Eyes.Blue")]
        issues = detect_conflicts(tags)
        assert issues == []

    def test_conflict_two_eye_colors(self):
        tags = [
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
            make_tag("brown_eyes", "eyes", resolved="Eyes.Brown"),
        ]
        issues = detect_conflicts(tags)
        assert len(issues) == 1
        assert issues[0].type == IssueType.CONFLICT
        assert issues[0].category == "eyes_color"

    def test_no_conflict_color_and_shape(self):
        """色と形状は別の排他グループなので矛盾としない"""
        tags = [
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
            make_tag("large_eyes", "eyes", resolved="Eyes.Large"),
        ]
        issues = detect_conflicts(tags)
        assert issues == []

    def test_conflict_hair_color(self):
        tags = [
            make_tag("blonde_hair", "hair", resolved="Hair.Blonde"),
            make_tag("black_hair", "hair", resolved="Hair.Black"),
        ]
        issues = detect_conflicts(tags)
        assert any(i.category == "hair_color" for i in issues)

    def test_conflict_hair_length(self):
        tags = [
            make_tag("long_hair", "hair", resolved="Hair.Long"),
            make_tag("short_hair", "hair", resolved="Hair.Short"),
        ]
        issues = detect_conflicts(tags)
        assert any(i.category == "hair_length" for i in issues)

    def test_conflict_quality_level(self):
        tags = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("low_quality", "quality", resolved="Quality.Low"),
        ]
        issues = detect_conflicts(tags)
        assert any(i.category == "quality_level" for i in issues)

    def test_conflict_message_contains_tags(self):
        tags = [
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
            make_tag("brown_eyes", "eyes", resolved="Eyes.Brown"),
        ]
        issues = detect_conflicts(tags)
        assert "blue_eyes" in issues[0].tags
        assert "brown_eyes" in issues[0].tags

    def test_empty_tags_no_conflict(self):
        assert detect_conflicts([]) == []


# ══════════════════════════════════════════════════════════════════
# redundancy_detector
# ══════════════════════════════════════════════════════════════════

class TestRedundancyDetector:
    def test_no_redundancy_single_smile(self):
        tags = [make_tag("smile", "expression", resolved="Expression.Smile")]
        issues = detect_redundancy(tags)
        assert issues == []

    def test_redundancy_smile_and_grin(self):
        tags = [
            make_tag("smile", "expression", resolved="Expression.Smile"),
            make_tag("grin", "expression", resolved="Expression.Grin"),
        ]
        issues = detect_redundancy(tags)
        assert any(i.category == "smile_family" for i in issues)

    def test_redundancy_severity_is_info(self):
        tags = [
            make_tag("smile", "expression", resolved="Expression.Smile"),
            make_tag("grin", "expression", resolved="Expression.Grin"),
        ]
        issues = detect_redundancy(tags)
        semantic = [i for i in issues if i.category == "smile_family"]
        assert semantic[0].severity == IssueSeverity.INFO

    def test_exact_duplicate_detected(self):
        tags = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("best_quality", "quality", resolved="Quality.High"),
        ]
        issues = detect_redundancy(tags)
        dup_issues = [i for i in issues if i.category == "exact_duplicate"]
        assert len(dup_issues) == 1
        assert dup_issues[0].severity == IssueSeverity.WARNING

    def test_hair_tied_redundancy(self):
        tags = [
            make_tag("ponytail", "hair", resolved="Hair.Ponytail"),
            make_tag("twintails", "hair", resolved="Hair.Twintails"),
        ]
        issues = detect_redundancy(tags)
        assert any(i.category == "hair_tied" for i in issues)

    def test_empty_tags_no_redundancy(self):
        assert detect_redundancy([]) == []


# ══════════════════════════════════════════════════════════════════
# quality_scorer
# ══════════════════════════════════════════════════════════════════

class TestQualityScorer:
    def test_coverage_full(self):
        tags = [
            make_tag("masterpiece", "quality"),
            make_tag("blue_eyes", "eyes"),
            make_tag("long_hair", "hair"),
            make_tag("oval_face", "face_shape"),
            make_tag("smile", "expression"),
            make_tag("smooth_skin", "skin"),
        ]
        score = calculate_coverage_score(tags)
        assert score == 100.0

    def test_coverage_partial(self):
        tags = [make_tag("masterpiece", "quality")]
        score = calculate_coverage_score(tags)
        assert 0 < score < 100

    def test_coverage_zero(self):
        tags = [make_tag("unrelated_tag", "unknown_category")]
        score = calculate_coverage_score(tags)
        assert score == 0.0

    def test_balance_perfect_for_uniform_weights(self):
        tags = [make_tag("a", "x", weight=1.0), make_tag("b", "y", weight=1.0)]
        score = calculate_balance_score(tags)
        assert score == 100.0

    def test_balance_low_for_extreme_variance(self):
        tags = [
            make_tag("a", "x", weight=3.0),
            make_tag("b", "y", weight=0.1),
            make_tag("c", "z", weight=0.1),
        ]
        score = calculate_balance_score(tags)
        assert score < 100.0

    def test_balance_single_tag_full_score(self):
        tags = [make_tag("a", "x", weight=2.0)]
        score = calculate_balance_score(tags)
        assert score == 100.0

    def test_redundancy_score_no_issues(self):
        score = calculate_redundancy_score([])
        assert score == 100.0

    def test_redundancy_score_with_error(self):
        issue = OptimizationIssue(type=IssueType.CONFLICT, severity=IssueSeverity.ERROR, message="x")
        score = calculate_redundancy_score([issue])
        assert score == 70.0

    def test_redundancy_score_floor_at_zero(self):
        issues = [
            OptimizationIssue(type=IssueType.CONFLICT, severity=IssueSeverity.ERROR, message="x")
            for _ in range(10)
        ]
        score = calculate_redundancy_score(issues)
        assert score == 0.0

    def test_overall_score_in_range(self):
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        score = calculate_quality_score(tags)
        assert 0 <= score.overall_score <= 100


# ══════════════════════════════════════════════════════════════════
# recommender
# ══════════════════════════════════════════════════════════════════

class TestRecommender:
    def test_recommendations_for_missing_categories(self):
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        score = calculate_quality_score(tags)
        recs = generate_recommendations(tags, [], score)
        assert any("指定されていません" in r for r in recs)

    def test_recommendations_for_conflicts(self):
        tags = [
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
            make_tag("brown_eyes", "eyes", resolved="Eyes.Brown"),
        ]
        issues = detect_conflicts(tags)
        score = calculate_quality_score(tags, issues=issues)
        recs = generate_recommendations(tags, issues, score)
        assert any("矛盾" in r for r in recs)

    def test_recommendations_good_score_message(self):
        tags = [
            make_tag("masterpiece", "quality", resolved="Quality.High"),
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
            make_tag("long_hair", "hair", resolved="Hair.Long"),
            make_tag("oval_face", "face_shape", resolved="FaceShape.Oval"),
            make_tag("smile", "expression", resolved="Expression.Smile"),
            make_tag("smooth_skin", "skin", resolved="Skin.Smooth"),
        ]
        score = calculate_quality_score(tags, issues=[])
        recs = generate_recommendations(tags, [], score)
        assert any("良好" in r or "標準的" in r for r in recs)

    def test_suggest_missing_tags_returns_candidates(self):
        tags = [make_tag("masterpiece", "quality")]
        suggestions = suggest_missing_tags(tags)
        assert len(suggestions) > 0
        assert "blue_eyes" in suggestions or "long_hair" in suggestions

    def test_suggest_missing_tags_full_coverage_empty(self):
        tags = [
            make_tag("masterpiece", "quality"),
            make_tag("blue_eyes", "eyes"),
            make_tag("long_hair", "hair"),
            make_tag("oval_face", "face_shape"),
            make_tag("smile", "expression"),
            make_tag("smooth_skin", "skin"),
        ]
        suggestions = suggest_missing_tags(tags)
        assert suggestions == []


# ══════════════════════════════════════════════════════════════════
# OptimizerManager
# ══════════════════════════════════════════════════════════════════

class TestOptimizerManager:
    def test_analyze_returns_result(self):
        om = OptimizerManager()
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        result = om.analyze(tags)
        assert isinstance(result, OptimizationResult)

    def test_analyze_detects_conflict_and_redundancy(self):
        om = OptimizerManager()
        tags = [
            make_tag("blue_eyes", "eyes", resolved="Eyes.Blue"),
            make_tag("brown_eyes", "eyes", resolved="Eyes.Brown"),
            make_tag("smile", "expression", resolved="Expression.Smile"),
            make_tag("grin", "expression", resolved="Expression.Grin"),
        ]
        result = om.analyze(tags)
        assert any(i.type == IssueType.CONFLICT for i in result.issues)
        assert any(i.type == IssueType.REDUNDANT for i in result.issues)

    def test_analyze_empty_tags(self):
        om = OptimizerManager()
        result = om.analyze([])
        assert result.score.overall_score >= 0

    def test_analyze_recommendations_present(self):
        om = OptimizerManager()
        tags = [make_tag("masterpiece", "quality", resolved="Quality.High")]
        result = om.analyze(tags)
        assert len(result.recommendations) > 0

    def test_analyze_pipeline_result(self):
        sys.path.insert(0, str(ROOT / "fps-core"))
        from pipeline.manager import PipelineManager

        pm = PipelineManager()
        pipeline_result = pm.compile("masterpiece, blue_eyes")

        om = OptimizerManager()
        result = om.analyze_pipeline_result(pipeline_result)
        assert isinstance(result, OptimizationResult)

    def test_suggest_tags_method(self):
        om = OptimizerManager()
        tags = [make_tag("masterpiece", "quality")]
        suggestions = om.suggest_tags(tags)
        assert isinstance(suggestions, list)

    def test_repr(self):
        om = OptimizerManager()
        assert "OptimizerManager" in repr(om)

    def test_with_dictionary_manager(self):
        sys.path.insert(0, str(ROOT / "fps-core"))
        from dictionary.manager import DictionaryManager

        dm = DictionaryManager(
            system_dir=ROOT / "fps-data" / "dictionaries" / "system",
            user_dir=ROOT / "fps-data" / "dictionaries" / "user",
        )
        dm.load()
        om = OptimizerManager(dictionary_manager=dm)
        tags = [make_tag("masterpiece", "quality")]
        suggestions = om.suggest_tags(tags)
        assert isinstance(suggestions, list)
