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
        prompt: str           # ポジティブプロンプト（最終出力）
        negative: str         # ネガティブプロンプト（最終出力）
        tag_count: int
        errors: list[str] = Field(default_factory=list)
        adapter_output: dict | None = None
        # ★ v2.1 — Profile 適用結果
        profile_applied: bool = False          # apply_profile が実行されたか
        excluded_tags: list[str] = Field(default_factory=list)   # 除外されたタグ
        added_tags: list[str] = Field(default_factory=list)       # 追加されたタグ
        auto_learned: bool = False             # 自動学習が実行されたか

    class OptimizeRequest(BaseModel):
        prompt: str = Field(..., description="分析対象プロンプト")

    class QualityScoreResponse(BaseModel):
        overall_score: float
        coverage_score: float
        balance_score: float
        redundancy_score: float
        negative_coverage_score: float = 0.0  # ★M6-1
        combination_score: float = 100.0       # ★v1.5
        token_score: float = 100.0             # ★v1.5

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

    class PresetTagItem(BaseModel):
        """プリセットタグ 1件"""
        tag: str
        category: str = ""
        weight: float = 1.0

    class PresetSummary(BaseModel):
        id: str
        name: str
        description: str
        tag_count: int
        source: str = "system"  # ★v1.7

    class PresetListResponse(BaseModel):
        presets: list[PresetSummary]

    # ── v1.7 Preset CRUD ─────────────────────────────────────────

    class PresetCreateRequest(BaseModel):
        """POST /presets リクエスト"""
        id: str = Field(..., description="一意なプリセットID")
        name: str = Field(..., min_length=1)
        description: str = ""
        tags: list[PresetTagItem] = Field(default_factory=list)
        negative_tags: list[PresetTagItem] = Field(default_factory=list)

    class PresetUpdateRequest(BaseModel):
        """PUT /presets/{id} リクエスト"""
        name: str | None = None
        description: str | None = None
        tags: list[PresetTagItem] | None = None
        negative_tags: list[PresetTagItem] | None = None

    class PresetTagsAddRequest(BaseModel):
        """POST /presets/{id}/tags/add リクエスト"""
        tags: list[PresetTagItem] = Field(..., min_length=1)
        negative: bool = False

    class PresetDetailResponse(BaseModel):
        """プリセット詳細レスポンス"""
        id: str
        name: str
        description: str
        tags: list[PresetTagItem]
        negative_tags: list[PresetTagItem]
        tag_count: int
        source: str

    class PresetDeleteResponse(BaseModel):
        """DELETE /presets/{id} レスポンス"""
        id: str
        deleted: bool

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

    # ── v1.2 User Dictionary CRUD ─────────────────────────────────

    class UserEntryCreateRequest(BaseModel):
        """POST /dictionary/user/entries リクエスト"""
        key: str
        resolved: str
        category: str
        aliases: list[str] = []
        weight: float = 1.0

    class UserEntryUpdateRequest(BaseModel):
        """PUT /dictionary/user/entries/{key} リクエスト"""
        resolved: str | None = None
        category: str | None = None
        aliases: list[str] | None = None
        weight: float | None = None

    class UserEntryResponse(BaseModel):
        """ユーザー辞書エントリ 1件レスポンス"""
        key: str
        resolved: str
        category: str
        aliases: list[str] = []
        weight: float
        tags: list[str] = []

    class UserEntryListResponse(BaseModel):
        """GET /dictionary/user/entries レスポンス"""
        entries: list[UserEntryResponse]
        total: int

    class UserEntryDeleteResponse(BaseModel):
        """DELETE /dictionary/user/entries/{key} レスポンス"""
        key: str
        deleted: bool

    # ── v1.8 Backup ──────────────────────────────────────────────

    class BackupEntryResponse(BaseModel):
        """バックアップエントリ 1件"""
        id: str
        target: str
        source_path: str
        created_at: str
        size_kb: float

    class BackupListResponse(BaseModel):
        """GET /backup レスポンス"""
        entries: list[BackupEntryResponse]
        total: int

    class BackupCreateRequest(BaseModel):
        """POST /backup リクエスト"""
        target: str = "all"   # "all" | "dictionary" | "rules" | "presets" | "config"

    class BackupCreateResponse(BaseModel):
        """POST /backup レスポンス"""
        success: bool
        entry_count: int
        total_kb: float
        entries: list[BackupEntryResponse]
        error: str = ""

    class BackupDeleteResponse(BaseModel):
        """DELETE /backup/{id} レスポンス"""
        id: str
        deleted: bool

    class BackupRestoreResponse(BaseModel):
        """POST /backup/{id}/restore レスポンス"""
        success: bool
        restored_files: int
        error: str = ""

    # ── v1.8 History 強化 ─────────────────────────────────────────

    class TagFrequency(BaseModel):
        """タグ使用頻度 1件"""
        tag: str
        count: int
        avg_weight: float = 1.0

    class HistoryStatsResponse(BaseModel):
        """GET /history/stats レスポンス"""
        total_entries: int
        favorite_count: int
        avg_score: float
        top_tags: list[TagFrequency]
        score_distribution: dict[str, int]   # "excellent"/"good"/"fair"/"poor" → count

    class HistoryExportResponse(BaseModel):
        """GET /history/export レスポンス"""
        format: str
        total: int
        data: str    # CSV or JSON string

    # ── v1.8 Dashboard ───────────────────────────────────────────

    class DashboardResponse(BaseModel):
        """GET /dashboard レスポンス"""
        version: str
        dictionary_keys: int
        japanese_entries: int
        preset_count: int
        history_count: int
        backup_count: int
        avg_score: float
        top_tags: list[TagFrequency]
        recent_activity: list[str]

    # ── v2.0 UserProfile ─────────────────────────────────────────

    class TagWeightItem(BaseModel):
        """タグ重みエントリ"""
        tag: str
        weight: float
        reason: str = "manual"

    class StyleRuleItem(BaseModel):
        """スタイルルール 1件"""
        id: str
        name: str
        always_include: list[str] = []
        always_exclude: list[str] = []
        enabled: bool = True

    class TagFreqItem(BaseModel):
        """タグ頻度エントリ"""
        tag: str
        count: int
        avg_weight: float = 1.0
        last_used: str = ""

    class ScoreTrendItem(BaseModel):
        """スコアトレンド 1日分"""
        date: str
        avg_score: float
        entry_count: int
        top_tag: str = ""

    class ProfileResponse(BaseModel):
        """GET /profile レスポンス"""
        tag_weight_count: int
        excluded_tag_count: int
        style_rule_count: int
        tag_frequency_count: int
        score_trend_count: int
        last_learned: str | None
        top_tags: list[TagFreqItem]
        style_rules: list[StyleRuleItem]

    class ProfileLearnResponse(BaseModel):
        """POST /profile/learn レスポンス"""
        learned: int
        updated: int
        total: int
        trend_days: int

    class ProfileRecommendResponse(BaseModel):
        """GET /profile/recommendations レスポンス"""
        recommendations: list[TagFreqItem]
        total: int

    class ProfileScoreTrendResponse(BaseModel):
        """GET /profile/score-trend レスポンス"""
        trends: list[ScoreTrendItem]
        days: int
        total: int

    class SetTagWeightRequest(BaseModel):
        """PUT /profile/tags/{tag}/weight リクエスト"""
        weight: float = Field(..., ge=0.0, le=3.0)
        reason: str = "manual"

    class AddStyleRuleRequest(BaseModel):
        """POST /profile/rules リクエスト"""
        id: str = Field(..., min_length=1)
        name: str = Field(..., min_length=1)
        always_include: list[str] = []
        always_exclude: list[str] = []
        enabled: bool = True

    class ProfileResetResponse(BaseModel):
        """DELETE /profile/reset レスポンス"""
        reset: bool
        message: str

    # ── v2.1 Profile Settings ────────────────────────────────────

    class ProfileSettingsResponse(BaseModel):
        """GET /profile/settings レスポンス"""
        auto_learn: bool = False
        auto_learn_interval: int = 10
        apply_profile_default: bool = False
        recommendation_threshold: int = 2
        compile_count: int = 0        # サーバー起動後のコンパイル回数

    class ProfileSettingsUpdateRequest(BaseModel):
        """PUT /profile/settings リクエスト"""
        auto_learn: bool | None = None
        auto_learn_interval: int | None = Field(default=None, ge=1, le=100)
        apply_profile_default: bool | None = None
        recommendation_threshold: int | None = Field(default=None, ge=1, le=10)

    # ── v2.2 高度検索 ────────────────────────────────────────────

    class RelatedTagItem(BaseModel):
        """関連タグ 1件"""
        tag: str
        score: float        # 関連度スコア（0.0〜1.0）
        co_count: int = 0   # 同時出現回数
        category: str = ""

    class RelatedTagsResponse(BaseModel):
        """GET /dictionary/related/{tag} レスポンス"""
        tag: str
        related: list[RelatedTagItem]
        total: int

    class HistorySearchResponse(BaseModel):
        """GET /history/search レスポンス"""
        entries: list[HistoryEntryResponse]
        total: int
        query: str = ""

    # ── v2.2 プリセット v2 ───────────────────────────────────────

    class SaveAsPresetRequest(BaseModel):
        """POST /profile/save-as-preset リクエスト"""
        preset_id: str = Field(..., min_length=1)
        name: str = Field(..., min_length=1)
        top_n: int = Field(default=20, ge=1, le=50)
        category: str = "personal"
        description: str = ""

    class SaveAsPresetResponse(BaseModel):
        """POST /profile/save-as-preset レスポンス"""
        preset_id: str
        name: str
        tag_count: int
        negative_tag_count: int
        category: str

    # ── v2.2 DB 統計 ─────────────────────────────────────────────

    class StorageStatsResponse(BaseModel):
        """GET /profile/storage レスポンス"""
        storage: str          # "json" | "sqlite"
        tag_frequency_count: int
        tag_weight_count: int
        style_rule_count: int
        score_trend_count: int
        db_path: str = ""

    # ── v2.3 ユーザー管理 ───────────────────────────────────────

    class RegisterRequest(BaseModel):
        """POST /users/register リクエスト"""
        username: str = Field(..., min_length=3, max_length=30,
                              pattern=r"^[a-zA-Z0-9_-]+$")
        display_name: str = ""
        expires_days: int | None = Field(default=None, ge=1, le=3650)

    class UserInfoResponse(BaseModel):
        """ユーザー情報レスポンス"""
        user_id: str
        username: str
        display_name: str
        created_at: str
        last_active: str

    class RegisterResponse(BaseModel):
        """POST /users/register レスポンス"""
        user: UserInfoResponse
        api_key: str     # 登録時のみ返す（再取得不可）
        message: str = "API キーを安全な場所に保存してください"

    class ApiKeyResponse(BaseModel):
        """API キー情報レスポンス"""
        key_id: str
        label: str
        created_at: str
        last_used: str | None
        expires_at: str | None

    class CreateApiKeyRequest(BaseModel):
        """POST /users/me/api-keys リクエスト"""
        label: str = "new key"
        expires_days: int | None = Field(default=None, ge=1, le=3650)

    class CreateApiKeyResponse(BaseModel):
        """POST /users/me/api-keys レスポンス"""
        api_key: str
        key_info: ApiKeyResponse
        message: str = "このキーは1度しか表示されません"

    # ── v2.3 プリセット共有 ──────────────────────────────────────

    class SharePresetRequest(BaseModel):
        """POST /presets/{id}/share リクエスト"""
        title: str = ""
        description: str = ""
        expires_days: int | None = Field(default=30, ge=1, le=365)

    class ShareTokenResponse(BaseModel):
        """共有トークンレスポンス"""
        token: str
        preset_id: str
        title: str
        description: str
        share_url: str
        created_at: str
        expires_at: str | None
        view_count: int

    class SharedPresetResponse(BaseModel):
        """GET /shared/presets/{token} レスポンス"""
        token: str
        preset_id: str
        title: str
        description: str
        created_at: str
        view_count: int
        preset_data: dict

    class DeleteShareResponse(BaseModel):
        token: str
        deleted: bool

    # ── v2.3 コミュニティ統計 ────────────────────────────────────

    class CommunityTagItem(BaseModel):
        """コミュニティタグ 1件"""
        tag: str
        total_count: int
        avg_score: float
        category: str = ""

    class CommunityTagsResponse(BaseModel):
        """GET /community/tags レスポンス"""
        tags: list[CommunityTagItem]
        total: int
        stats: dict

    class ContributeRequest(BaseModel):
        """POST /community/contribute リクエスト"""
        tags: list[str] = Field(..., min_length=1)
        avg_score: float = Field(default=0.0, ge=0.0, le=100.0)

    class ContributeResponse(BaseModel):
        contributed: int
        message: str

    # ── v2.4 バッチ処理 ─────────────────────────────────────────

    class BatchCompileRequest(BaseModel):
        """POST /batch/compile リクエスト"""
        prompts: list[str] = Field(..., min_length=1, max_length=50)
        apply_profile: bool = False
        adapter: str | None = None

    class BatchOptimizeRequest(BaseModel):
        """POST /batch/optimize リクエスト"""
        prompts: list[str] = Field(..., min_length=1, max_length=50)

    class BatchItemResponse(BaseModel):
        """バッチアイテム 1件レスポンス"""
        index: int
        input: str
        prompt_out: str = ""
        negative_out: str = ""
        tag_count: int = 0
        score: float = 0.0
        issues: list[str] = []
        error: str = ""
        elapsed_ms: float = 0.0
        success: bool = True

    class BatchResultResponse(BaseModel):
        """バッチ処理結果レスポンス"""
        job_id: str
        mode: str
        total: int
        succeeded: int
        failed: int
        avg_score: float = 0.0
        avg_tag_count: float = 0.0
        total_elapsed_ms: float
        started_at: str
        finished_at: str
        items: list[BatchItemResponse]

    # ── v2.4 タグ補完 ───────────────────────────────────────────

    class AutocompleteItem(BaseModel):
        key: str
        resolved: str
        category: str = ""
        weight: float = 1.0

    class AutocompleteResponse(BaseModel):
        """GET /dictionary/autocomplete レスポンス"""
        query: str
        items: list[AutocompleteItem]
        total: int

    class SuggestResponse(BaseModel):
        """GET /dictionary/suggest レスポンス"""
        current_tags: list[str]
        suggestions: list[AutocompleteItem]
        total: int

    # ── v2.4 プロファイル エクスポート/インポート ────────────────

    class ProfileExportResponse(BaseModel):
        """GET /profile/export レスポンス"""
        version: str
        exported_at: str
        tag_frequency_count: int
        tag_weight_count: int
        style_rule_count: int
        data: dict

    class ProfileImportRequest(BaseModel):
        """POST /profile/import リクエスト"""
        data: dict
        merge: bool = False  # True = 既存データにマージ / False = 上書き

    class ProfileImportResponse(BaseModel):
        imported_frequencies: int
        imported_weights: int
        imported_rules: int
        merged: bool

    # ── v2.4 プリセットバージョン管理 ────────────────────────────

    class PresetVersionItem(BaseModel):
        version_id: str
        preset_id: str
        created_at: str
        label: str = ""
        tag_count: int = 0
        neg_count: int = 0

    class PresetVersionsResponse(BaseModel):
        """GET /presets/{id}/versions レスポンス"""
        preset_id: str
        versions: list[PresetVersionItem]
        total: int

    class RestoreVersionResponse(BaseModel):
        """POST /presets/{id}/versions/{v}/restore レスポンス"""
        preset_id: str
        version_id: str
        restored: bool
        tag_count: int

    # ── v2.5 LoRA 分析 ───────────────────────────────────────────

    class LoraAnalyzeRequest(BaseModel):
        """POST /lora/analyze リクエスト"""
        file_path:    str | None = None        # SafeTensors ファイルパス
        metadata:     dict | None = None       # メタデータ直接入力（CivitAI等）
        file_name:    str = "unknown.safetensors"
        register_to_dict: bool = False         # 辞書に自動登録するか
        category:     str = "lora"

    class LoraTagCandidateItem(BaseModel):
        tag: str
        source: str
        confidence: float
        category: str = ""
        weight: float = 1.0

    class LoraAnalyzeResponse(BaseModel):
        """POST /lora/analyze レスポンス"""
        file_name:     str
        model_name:    str = ""
        base_model:    str = ""
        description:   str = ""
        trigger_words: list[str]
        training_tags: list[str]
        total_tags:    int
        tag_candidates: list[LoraTagCandidateItem]
        registered:    int = 0
        error:         str = ""
        success:       bool

    # ── v2.5 AI タグ提案 ─────────────────────────────────────────

    class AiTagRequest(BaseModel):
        """POST /ai/tag リクエスト"""
        image_url:     str | None = None
        current_tags:  list[str] = []
        model:         str = "dictionary"      # wd14 / joycaption / florence2 / dictionary
        threshold:     float = Field(default=0.35, ge=0.0, le=1.0)
        n:             int = Field(default=20, ge=1, le=50)

    class AiTagItem(BaseModel):
        tag: str
        score: float

    class AiTagResponse(BaseModel):
        """POST /ai/tag レスポンス"""
        model:   str
        source:  str
        tags:    list[AiTagItem]
        top_tags: list[str]
        error:   str = ""
        success: bool

    class AiStatusResponse(BaseModel):
        """GET /ai/status レスポンス"""
        available_models: list[str]
        wd14_available:        bool
        joycaption_available:  bool
        florence2_available:   bool
        dictionary_available:  bool

    # ── v2.5 Negative 学習 ───────────────────────────────────────

    class NegativeLearnResponse(BaseModel):
        """POST /ai/negative-learn レスポンス"""
        neg_learned:   int
        avoid_learned: int
        total:         int

    class NegativeTagItem(BaseModel):
        tag: str
        neg_count: int
        avoid_count: int
        priority: float

    class NegativeSuggestResponse(BaseModel):
        """GET /ai/negative-suggest レスポンス"""
        suggestions: list[NegativeTagItem]
        total: int

    # ── v2.5 一貫性チェック ──────────────────────────────────────

    class ConsistencyCheckRequest(BaseModel):
        """POST /consistency/check リクエスト"""
        prompts: list[str] = Field(..., min_length=2, max_length=20)
        labels:  list[str] = []

    class ConsistencyCheckResponse(BaseModel):
        """POST /consistency/check レスポンス"""
        overall_score:     float
        category_scores:   dict[str, float]
        common_tags:       list[str]
        inconsistent_tags: list[str]
        missing_tags:      list[str]
        recommendations:   list[str]
        detail:            list[dict]

    # ── v2.6 Wildcard ────────────────────────────────────────────

    class WildcardEntryItem(BaseModel):
        value:   str
        weight:  float = 1.0
        comment: str   = ""

    class WildcardCreateRequest(BaseModel):
        """POST /wildcards リクエスト"""
        name:        str = Field(..., min_length=1, max_length=60,
                                 pattern=r"^[a-zA-Z0-9_/]+$")
        values:      list[str] = Field(..., min_length=1)
        description: str = ""
        category:    str = ""
        weights:     list[float] | None = None

    class WildcardUpdateRequest(BaseModel):
        """PUT /wildcards/{name} リクエスト"""
        values:      list[str] | None = None
        description: str | None = None
        category:    str | None = None
        weights:     list[float] | None = None

    class WildcardResponse(BaseModel):
        """Wildcard レスポンス"""
        name:        str
        description: str
        category:    str
        entry_count: int
        entries:     list[WildcardEntryItem] = []
        created_at:  str
        updated_at:  str

    class WildcardListResponse(BaseModel):
        """GET /wildcards レスポンス"""
        wildcards: list[WildcardResponse]
        total:     int
        stats:     dict

    class WildcardExpandRequest(BaseModel):
        """POST /wildcards/expand リクエスト"""
        prompt:    str
        n:         int = Field(default=5, ge=1, le=20)
        seed:      int | None = None
        variables: dict[str, str] = {}

    class WildcardExpandResponse(BaseModel):
        """POST /wildcards/expand レスポンス"""
        original:  str
        expanded:  list[str]
        wildcards_used: list[str]

    class WildcardImportRequest(BaseModel):
        """POST /wildcards/{name}/import リクエスト"""
        text:        str
        description: str = ""

    # ── v2.6 メトリクス ──────────────────────────────────────────

    class MetricsResponse(BaseModel):
        """GET /metrics レスポンス（Prometheus 形式テキストも /metrics/prometheus から取得可能）"""
        uptime_seconds:    float
        compile_count:     int
        avg_compile_ms:    float
        cache_hit_rate:    float
        endpoint_calls:    dict[str, int]
        error_count:       int
        wildcard_count:    int
        dictionary_keys:   int

    # ── v2.7 キャラクターシート ──────────────────────────────────

    class CharacterFeatureItem(BaseModel):
        tag:      str
        weight:   float = 1.0
        category: str   = ""
        note:     str   = ""

    class CharacterCreateRequest(BaseModel):
        """POST /characters リクエスト"""
        id:          str = Field(..., min_length=1, max_length=60,
                                 pattern=r"^[a-zA-Z0-9_-]+$")
        name:        str = Field(..., min_length=1)
        description: str = ""
        features:    list[CharacterFeatureItem] = []
        neg_features: list[CharacterFeatureItem] = []
        tags:        list[str] = []

    class CharacterUpdateRequest(BaseModel):
        """PUT /characters/{id} リクエスト"""
        name:        str | None = None
        description: str | None = None
        features:    list[CharacterFeatureItem] | None = None
        neg_features: list[CharacterFeatureItem] | None = None
        tags:        list[str] | None = None

    class CharacterResponse(BaseModel):
        id:           str
        name:         str
        description:  str
        features:     list[CharacterFeatureItem]
        neg_features: list[CharacterFeatureItem]
        tags:         list[str]
        pos_prompt:   str
        neg_prompt:   str
        feature_count: int
        created_at:   str
        updated_at:   str

    class CharacterListResponse(BaseModel):
        characters: list[CharacterResponse]
        total:      int
        stats:      dict

    class CharacterToPresetRequest(BaseModel):
        """POST /characters/{id}/to-preset リクエスト"""
        preset_id: str | None = None

