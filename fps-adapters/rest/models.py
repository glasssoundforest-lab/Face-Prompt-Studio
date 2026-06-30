"""
fps-adapters/rest/models.py — REST API データモデル

Pydantic ベースのリクエスト/レスポンススキーマ定義。
fastapi/pydantic が未インストールの環境でもこのモジュール自体は
import エラーにならないよう、トップレベルで try/except する。
"""

from __future__ import annotations

try:
    from pydantic import BaseModel, Field

    _PYDANTIC_AVAILABLE = True
except ImportError:
    _PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore[assignment,misc]

    def Field(*args, **kwargs):  # type: ignore[no-redef]
        return None


if _PYDANTIC_AVAILABLE:

    class CompileRequest(BaseModel):
        prompt: str = Field(..., description="DSL形式のプロンプト文字列")
        adapter: str | None = Field(
            default=None, description="出力アダプター (comfyui/a1111/novelai)"
        )

    class CompileResponse(BaseModel):
        success: bool
        prompt: str
        negative: str
        tag_count: int
        errors: list[str] = Field(default_factory=list)
        adapter_output: dict | None = None

    class OptimizeRequest(BaseModel):
        prompt: str = Field(..., description="分析対象プロンプト")

    class QualityScoreResponse(BaseModel):
        overall_score: float
        coverage_score: float
        balance_score: float
        redundancy_score: float

    class OptimizationIssueResponse(BaseModel):
        type: str
        severity: str
        message: str

    class OptimizeResponse(BaseModel):
        score: QualityScoreResponse
        issues: list[OptimizationIssueResponse]
        recommendations: list[str]

    class DictionaryLookupResponse(BaseModel):
        found: bool
        key: str
        resolved: str | None = None
        category: str | None = None
        weight: float = 1.0

    class DictionaryStatsResponse(BaseModel):
        total_keys: int
        by_source: dict[str, int]
        by_category: dict[str, int]
        system_files: int
        user_files: int

    class PresetSummary(BaseModel):
        id: str
        name: str
        description: str
        tag_count: int

    class PresetListResponse(BaseModel):
        presets: list[PresetSummary]

    class HistoryEntryResponse(BaseModel):
        id: str
        input_prompt: str
        output_prompt: str
        tag_count: int
        overall_score: float
        created_at: str
        favorite: bool
        label: str

    class HistoryListResponse(BaseModel):
        entries: list[HistoryEntryResponse]
        total: int

    class ValidationResponse(BaseModel):
        success: bool
        errors: dict[str, list[str]] = Field(default_factory=dict)

    class HealthResponse(BaseModel):
        status: str
        version: str
        dictionary_keys: int
        rule_count: int
