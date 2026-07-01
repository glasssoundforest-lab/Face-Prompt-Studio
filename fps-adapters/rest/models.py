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
        negative_coverage_score: float = 0.0  # ★M6-1

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

    # ── M5-3 Knowledge Browser ────────────────────────────────────

    class CategoryListResponse(BaseModel):
        """GET /dictionary/categories レスポンス"""

        categories: list[str]
        total: int

    class DictionaryEntryItem(BaseModel):
        """辞書エントリ 1 件"""

        key: str
        resolved: str
        weight: float
        category: str
        synonyms: list[str] = []

    class EntriesResponse(BaseModel):
        """GET /dictionary/entries レスポンス"""

        entries: list[DictionaryEntryItem]
        total: int
        category: str | None = None
        search: str | None = None

    class SynonymsResponse(BaseModel):
        """GET /dictionary/synonyms レスポンス"""

        key: str
        synonyms: list[str]
        resolved: str
        weight: float
        category: str

    # ── M5-4 History Timeline ─────────────────────────────────────

    class HistoryDetailResponse(BaseModel):
        """GET /history/{id} レスポンス"""

        id: str
        input_prompt: str
        output_prompt: str
        output_negative: str
        tag_count: int
        overall_score: float
        created_at: str
        favorite: bool
        label: str

    class FavoriteToggleResponse(BaseModel):
        """POST /history/{id}/favorite レスポンス"""

        id: str
        favorite: bool

    class LabelUpdateRequest(BaseModel):
        """PUT /history/{id}/label リクエスト"""

        label: str

    class LabelUpdateResponse(BaseModel):
        """PUT /history/{id}/label レスポンス"""

        id: str
        label: str

    class DiffResponse(BaseModel):
        """GET /history/{id1}/diff/{id2} レスポンス"""

        entry_id_1: str
        entry_id_2: str
        added_tags: list[str]
        removed_tags: list[str]
        unchanged_tags: list[str]
        score_delta: float
        has_changes: bool

    class DeleteHistoryResponse(BaseModel):
        """DELETE /history/{id} レスポンス"""

        id: str
        deleted: bool

    # ── M6-3 テンプレートエンジン ─────────────────────────────────

    class TemplateVariableResponse(BaseModel):
        name: str
        description: str
        default: str
        examples: list[str] = []
        required: bool = True

    class TemplateSummaryResponse(BaseModel):
        id: str
        name: str
        description: str
        body: str
        variables: list[TemplateVariableResponse] = []
        tags: list[str] = []
        category: str

    class TemplateListResponse(BaseModel):
        templates: list[TemplateSummaryResponse]
        total: int

    class RenderRequest(BaseModel):
        variables: dict[str, str] = {}

    class RenderResponse(BaseModel):
        template_id: str
        rendered: str
        variables_used: dict[str, str] = {}
        missing_variables: list[str] = []
        warnings: list[str] = []
        success: bool
