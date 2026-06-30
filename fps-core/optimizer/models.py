"""
fps-core/optimizer/models.py — Optimizer データモデル
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IssueType(StrEnum):
    CONFLICT = "conflict"  # 同一カテゴリの排他的属性が複数（例: blue_eyes + brown_eyes）
    REDUNDANT = "redundant"  # 意味的に重複するタグ（例: smile + grin）
    MISSING_COVERAGE = "missing_coverage"  # 重要カテゴリが未指定
    WEIGHT_IMBALANCE = "weight_imbalance"  # 重みの著しい偏り


@dataclass(slots=True)
class OptimizationIssue:
    """検出された問題 1件"""

    type: IssueType
    severity: IssueSeverity
    message: str
    tags: list[str] = field(default_factory=list)
    category: str = ""
    suggestion: str = ""


@dataclass(slots=True)
class QualityScore:
    """プロンプト品質スコア"""

    coverage_score: float  # 0-100: 重要カテゴリの網羅度
    balance_score: float  # 0-100: 重みバランス
    redundancy_score: float  # 0-100: 非冗長性（100 = 冗長なし）
    overall_score: float  # 0-100: 総合スコア

    def to_dict(self) -> dict[str, float]:
        return {
            "coverage_score": round(self.coverage_score, 1),
            "balance_score": round(self.balance_score, 1),
            "redundancy_score": round(self.redundancy_score, 1),
            "overall_score": round(self.overall_score, 1),
        }


@dataclass(slots=True)
class OptimizationResult:
    """最適化分析の結果"""

    score: QualityScore
    issues: list[OptimizationIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == IssueSeverity.ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == IssueSeverity.WARNING for i in self.issues)

    @property
    def issue_count(self) -> int:
        return len(self.issues)
