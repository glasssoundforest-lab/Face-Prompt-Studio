"""
fps-adapters/rest/app.py — REST API アプリケーション

FastAPI ベースの REST API。CLI と同じ CliContext を再利用することで
ロジックの重複を避ける（Single Source of Truth）。

エンドポイント:
  GET  /health                    ヘルスチェック
  POST /compile                   プロンプト変換
  POST /optimize                  品質分析
  GET  /dictionary/search         辞書検索
  GET  /dictionary/stats          辞書統計
  GET  /presets                   プリセット一覧
  POST /presets                   ★v1.7 プリセット新規作成
  POST /presets/{preset_id}/apply プリセット適用
  PUT  /presets/{preset_id}       ★v1.7 プリセット部分更新
  DELETE /presets/{preset_id}     ★v1.7 プリセット削除
  POST /presets/{preset_id}/tags/add ★v1.7 タグ追記
  GET  /history                   変換履歴一覧
  POST /validate                  辞書/ルール/プリセット検証

起動方法:
  uvicorn fps-adapters.rest.app:app --reload --port 8420
"""

from __future__ import annotations

import json as json_module
import sys
from pathlib import Path

_ROOT = Path(__file__).parents[2]
_ADAPTERS = _ROOT / "fps-adapters"

if str(_ADAPTERS) not in sys.path:
    sys.path.insert(0, str(_ADAPTERS))

try:
    from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect

    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False
    FastAPI = None  # type: ignore[assignment,misc]

from .models import (  # noqa: E402
    CategoryListResponse,
    CompileResponse,
    DeleteHistoryResponse,
    DictionaryEntryItem,
    DictionaryLookupResponse,
    DictionaryStatsResponse,
    DiffResponse,
    EntriesResponse,
    FavoriteToggleResponse,
    HealthResponse,
    HistoryDetailResponse,
    HistoryEntryResponse,
    HistoryListResponse,
    LabelUpdateRequest,
    LabelUpdateResponse,
    OptimizationIssueResponse,
    OptimizeResponse,
    PresetCreateRequest,
    PresetDeleteResponse,
    PresetDetailResponse,
    PresetListResponse,
    PresetSummary,
    PresetTagItem,
    PresetTagsAddRequest,
    PresetUpdateRequest,
    QualityScoreResponse,
    RenderRequest,
    RenderResponse,
    SynonymsResponse,
    TemplateListResponse,
    TemplateSummaryResponse,
    TemplateVariableResponse,
    UserEntryCreateRequest,
    UserEntryDeleteResponse,
    UserEntryListResponse,
    UserEntryResponse,
    UserEntryUpdateRequest,
    ValidationResponse,
    BackupCreateRequest,
    BackupCreateResponse,
    BackupDeleteResponse,
    BackupEntryResponse,
    BackupListResponse,
    BackupRestoreResponse,
    DashboardResponse,
    HistoryExportResponse,
    HistoryStatsResponse,
    TagFrequency,
    TagWeightItem,
    StyleRuleItem,
    TagFreqItem,
    ScoreTrendItem,
    ProfileResponse,
    ProfileLearnResponse,
    ProfileRecommendResponse,
    ProfileScoreTrendResponse,
    SetTagWeightRequest,
    AddStyleRuleRequest,
    ProfileResetResponse,
    ProfileSettingsResponse,
    ProfileSettingsUpdateRequest,
    RelatedTagItem,
    RelatedTagsResponse,
    HistorySearchResponse,
    SaveAsPresetRequest,
    SaveAsPresetResponse,
    StorageStatsResponse,
    RegisterRequest,
    RegisterResponse,
    UserInfoResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    SharePresetRequest,
    ShareTokenResponse,
    SharedPresetResponse,
    DeleteShareResponse,
    CommunityTagItem,
    CommunityTagsResponse,
    ContributeRequest,
    ContributeResponse,
    BatchCompileRequest,
    BatchOptimizeRequest,
    BatchItemResponse,
    BatchResultResponse,
    AutocompleteItem,
    AutocompleteResponse,
    SuggestResponse,
    ProfileExportResponse,
    ProfileImportRequest,
    ProfileImportResponse,
    PresetVersionItem,
    PresetVersionsResponse,
    TranslateRequest,
    TranslateResponse,
    TranslateDetailItem,
    DetectLanguageResponse,
    ChainStepItem,
    ChainCreateRequest,
    ChainUpdateRequest,
    ChainResponse,
    ChainListResponse,
    ChainRunRequest,
    ChainStepResultItem,
    ChainRunResponse,
    ComfyUIQueueRequest,
    ComfyUIQueueResponse,
    ComfyUIStatusResponse,
    ExportRequest,
    ExportResponse,
    SessionCreateRequest,
    SessionUpdateRequest,
    SessionAddEntryRequest,
    SessionEntryItem,
    SessionResponse,
    SessionListResponse,
    SessionCompareResponse,
    CharacterFeatureItem,
    CharacterCreateRequest,
    CharacterUpdateRequest,
    CharacterResponse,
    CharacterListResponse,
    CharacterToPresetRequest,
    RestoreVersionResponse,
    LoraAnalyzeRequest,
    LoraAnalyzeResponse,
    LoraTagCandidateItem,
    AiTagRequest,
    AiTagItem,
    AiTagResponse,
    AiStatusResponse,
    NegativeLearnResponse,
    NegativeTagItem,
    NegativeSuggestResponse,
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
    WildcardCreateRequest,
    WildcardUpdateRequest,
    WildcardResponse,
    WildcardEntryItem,
    WildcardListResponse,
    WildcardExpandRequest,
    WildcardExpandResponse,
    WildcardImportRequest,
    MetricsResponse,
)

if _FASTAPI_AVAILABLE:
    from cli.context import CliContext

    app = FastAPI(
        title="Face Prompt Studio API",
        description="REST API for prompt compilation, optimization, and management",
        version="2.9.0",
    )

    # Web UI のスタティックファイルを配信（オプション）
    _GUI_DIR = _ROOT / "fps-gui" / "web"
    if _GUI_DIR.exists():
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        app.mount("/static", StaticFiles(directory=str(_GUI_DIR)), name="static")

        @app.get("/", include_in_schema=False)
        def serve_ui() -> FileResponse:
            return FileResponse(str(_GUI_DIR / "index.html"))


    from .ws import manager as ws_manager, setup_event_bridge

    @app.on_event("startup")
    async def on_startup() -> None:
        """アプリ起動時に EventBus ↔ WebSocket ブリッジを初期化する。"""
        global _start_time
        import time as _time
        _start_time = _time.time()
        ctx = get_context()
        setup_event_bridge(ctx.event_bus)

    _ctx: CliContext | None = None
    _compile_count: int = 0   # ★v2.1 compile 実行回数カウンター
    _compile_ms_total: float = 0.0
    _error_count: int = 0
    _endpoint_calls: dict[str, int] = {}
    _start_time: float = 0.0

    def get_context() -> CliContext:
        global _ctx
        if _ctx is None:
            _ctx = CliContext()
        return _ctx

    # ── Health ───────────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        ctx = get_context()
        dict_stats = ctx.dictionary_manager.statistics()
        rule_stats = ctx.rule_manager.statistics()
        return HealthResponse(
            status="ok",
            version="2.9.0",
            dictionary_keys=dict_stats["total_keys"],
            rule_count=rule_stats["total_rules"],
        )

    # ── Compile ──────────────────────────────────────────────

    def _convert_with_adapter(result, adapter_name: str) -> dict | None:
        try:
            if adapter_name == "comfyui":
                from comfyui.adapter import ComfyUIAdapter

                return ComfyUIAdapter(api_version="v1").convert(result)
            if adapter_name == "a1111":
                from a1111.adapter import A1111Adapter

                return A1111Adapter().convert(result)
            if adapter_name == "novelai":
                from novelai.adapter import NovelAIAdapter

                return NovelAIAdapter().convert(result)
        except Exception:
            return None
        return None

    @app.post("/compile", response_model=CompileResponse)
    def compile_prompt(
        prompt: str,
        adapter: str | None = None,
        apply_profile: bool = Query(
            default=False,
            description="★v2.1 プロファイル適用（除外タグ除去・追加タグ挿入）"),
        negative_profile: bool = Query(
            default=False,
            description="★v2.1 スタイルルールの always_exclude をネガティブに追加"),
    ) -> CompileResponse:
        """
        プロンプトをコンパイルして pos/neg テキストを返す。

        apply_profile=true の場合:
          1. スタイルルールの always_include を先頭に追加
          2. 除外設定（weight=0.0 / always_exclude）のタグを pos から除去
          3. always_exclude タグを neg に追加（negative_profile=true 時）
        """
        global _compile_count
        ctx = get_context()

        # ── ★v2.1 Profile 適用（compile 前処理）────────────────
        profile_applied = False
        excluded_tags: list[str] = []
        added_tags: list[str] = []

        if apply_profile:
            try:
                upm = _get_upm()
                original_tags = [t.strip() for t in prompt.split(",") if t.strip()]
                applied_tags  = upm.apply_profile(original_tags)
                excluded_tags = [t for t in original_tags if t not in applied_tags]
                added_tags    = [t for t in applied_tags  if t not in original_tags]
                # プロファイル適用済みのタグ文字列で再コンパイル
                prompt = ", ".join(applied_tags)
                profile_applied = True
            except Exception:
                pass  # プロファイル未設定時はスキップ

        result = ctx.pipeline_manager.compile(prompt)

        # ── negative_profile: always_exclude を neg に追加 ───────
        final_negative = result.negative
        if negative_profile and apply_profile:
            try:
                upm = _get_upm()
                p = upm.get_profile()
                neg_adds: list[str] = []
                for rule in p.style_rules:
                    if rule.enabled:
                        neg_adds.extend(rule.always_exclude)
                if neg_adds:
                    existing_neg = {t.strip() for t in final_negative.split(",") if t.strip()}
                    new_neg_tags = [t for t in neg_adds if t not in existing_neg]
                    if new_neg_tags:
                        final_negative = (
                            (final_negative.rstrip(", ") + ", " if final_negative.strip() else "")
                            + ", ".join(new_neg_tags)
                        )
            except Exception:
                pass

        adapter_output = None
        if adapter:
            adapter_output = _convert_with_adapter(result, adapter)

        # ── v1.9: history 記録 + WS emit ────────────────────────
        _compile_count += 1
        auto_learned = False
        try:
            ctx.history_manager.record(
                input_prompt=prompt,
                output_prompt=result.prompt,
                output_negative=final_negative,
                tag_count=result.tag_count,
                overall_score=0.0,
            )
            ctx.event_bus.emit(
                "history.recorded",
                {
                    "input": prompt,
                    "output": result.prompt,
                    "negative": final_negative,
                    "tag_count": result.tag_count,
                    "profile_applied": profile_applied,
                },
                source="compile",
            )
            # ── ★v2.1 自動学習チェック ──────────────────────────
            upm = _get_upm()
            if upm.should_auto_learn(_compile_count):
                entries = ctx.history_manager.list_entries(limit=100)
                upm.learn(entries)
                upm.build_score_trends(entries, days=30)
                ctx.event_bus.emit(
                    "profile.auto_learned",
                    {"compile_count": _compile_count, "entry_count": len(entries)},
                    source="compile",
                )
                auto_learned = True
        except Exception:
            pass

        return CompileResponse(
            success=result.success,
            prompt=result.prompt,
            negative=final_negative,
            tag_count=result.tag_count,
            errors=result.errors,
            adapter_output=adapter_output,
            profile_applied=profile_applied,
            excluded_tags=excluded_tags,
            added_tags=added_tags,
            auto_learned=auto_learned,
        )

    # ── Optimize ─────────────────────────────────────────────

    @app.post("/optimize", response_model=OptimizeResponse)
    def optimize_prompt(
        prompt: str,
        negative_prompt: str | None = Query(default=None, description="★M6-1 ネガティブプロンプト（省略可）"),
    ) -> OptimizeResponse:
        """プロンプトを分析してスコア・問題・推奨事項を返す。

        Args:
            prompt:          ポジティブプロンプト
            negative_prompt: ★M6-1 ネガティブプロンプト（省略可）
        """
        ctx = get_context()

        # ポジティブプロンプトをパイプライン経由で解析
        pipeline_result = ctx.pipeline_manager.compile(prompt)

        # M6-1: ネガティブプロンプトも同様にパイプライン処理
        neg_tags: list[dict] = []
        if negative_prompt and negative_prompt.strip():
            neg_pipeline = ctx.pipeline_manager.compile(negative_prompt)
            neg_tags = [
                {"tag": t.tag, "category": t.category, "weight": t.weight, "meta": dict(t.meta)}
                for t in neg_pipeline.tags
            ]

        pos_tags = [
            {"tag": t.tag, "category": t.category, "weight": t.weight, "meta": dict(t.meta)}
            for t in pipeline_result.tags
        ]

        opt_result = ctx.optimizer_manager.analyze(pos_tags, negative_tags=neg_tags or None)

        # v1.9: optimizer.analyzed を emit
        try:
            ctx.event_bus.emit(
                "optimizer.analyzed",
                {"overall_score": opt_result.score.overall_score,
                 "issue_count": len(opt_result.issues)},
                source="optimize",
            )
        except Exception:
            pass
        return OptimizeResponse(
            score=QualityScoreResponse(**opt_result.score.to_dict()),
            issues=[
                OptimizationIssueResponse(
                    type=str(i.type), severity=str(i.severity), message=i.message
                )
                for i in opt_result.issues
            ],
            recommendations=opt_result.recommendations,
        )

    # ── Dictionary ───────────────────────────────────────────

    @app.get("/dictionary/search", response_model=DictionaryLookupResponse)
    def dictionary_search(
        query: str = Query(..., description="検索するタグ名"),
    ) -> DictionaryLookupResponse:
        ctx = get_context()
        result = ctx.dictionary_manager.lookup(query)
        return DictionaryLookupResponse(
            found=result.found,
            key=query,
            resolved=result.resolved,
            category=result.category,
            weight=result.weight,
        )

    @app.get("/dictionary/stats", response_model=DictionaryStatsResponse)
    def dictionary_stats() -> DictionaryStatsResponse:
        ctx = get_context()
        stats = ctx.dictionary_manager.statistics()
        return DictionaryStatsResponse(
            total_keys=stats["total_keys"],
            by_source=stats["by_source"],
            by_category=stats["by_category"],
            system_files=stats["system_files"],
            user_files=stats["user_files"],
        )

    # ── Presets ──────────────────────────────────────────────

    def _preset_to_detail(p) -> PresetDetailResponse:
        """Preset オブジェクトを PresetDetailResponse に変換する"""
        return PresetDetailResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            tags=[PresetTagItem(tag=t.tag, category=t.category, weight=t.weight) for t in p.tags],
            negative_tags=[PresetTagItem(tag=t.tag, category=t.category, weight=t.weight) for t in p.negative_tags],
            tag_count=p.tag_count,
            source=str(p.source),
        )

    @app.get("/presets", response_model=PresetListResponse)
    def list_presets() -> PresetListResponse:
        ctx = get_context()
        presets = ctx.preset_manager.list_presets()
        return PresetListResponse(
            presets=[
                PresetSummary(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                    tag_count=p.tag_count,
                    source=str(p.source),
                )
                for p in presets
            ]
        )

    @app.post("/presets", response_model=PresetDetailResponse, status_code=201)
    def create_preset(body: PresetCreateRequest) -> PresetDetailResponse:
        """★v1.7 ユーザープリセット新規作成"""
        ctx = get_context()
        from preset.models import Preset, PresetSource, PresetTag  # type: ignore[import]
        if ctx.preset_manager.exists(body.id):
            raise HTTPException(status_code=409, detail=f"Preset '{body.id}' already exists")
        preset = Preset(
            id=body.id,
            name=body.name,
            description=body.description,
            tags=[PresetTag(tag=t.tag, category=t.category, weight=t.weight) for t in body.tags],
            negative_tags=[PresetTag(tag=t.tag, category=t.category, weight=t.weight) for t in body.negative_tags],
            source=PresetSource.USER,
        )
        ctx.preset_manager.save(preset)
        return _preset_to_detail(ctx.preset_manager.get(body.id))

    @app.post("/presets/{preset_id}/apply", response_model=CompileResponse)
    def apply_preset(preset_id: str) -> CompileResponse:
        ctx = get_context()
        if not ctx.preset_manager.exists(preset_id):
            raise HTTPException(status_code=404, detail=f"preset '{preset_id}' not found")

        applied = ctx.preset_manager.apply(preset_id)
        prompt_str = ", ".join(t["tag"] for t in applied["tags"])
        result = ctx.pipeline_manager.compile(prompt_str)

        return CompileResponse(
            success=result.success,
            prompt=result.prompt,
            negative=result.negative,
            tag_count=result.tag_count,
            errors=result.errors,
        )

    @app.put("/presets/{preset_id}", response_model=PresetDetailResponse)
    def update_preset(preset_id: str, body: PresetUpdateRequest) -> PresetDetailResponse:
        """★v1.7 プリセット部分更新"""
        ctx = get_context()
        from preset.models import PresetTag  # type: ignore[import]
        if not ctx.preset_manager.exists(preset_id):
            raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
        try:
            tags = [PresetTag(tag=t.tag, category=t.category, weight=t.weight) for t in body.tags] if body.tags is not None else None
            neg_tags = [PresetTag(tag=t.tag, category=t.category, weight=t.weight) for t in body.negative_tags] if body.negative_tags is not None else None
            updated = ctx.preset_manager.update(
                preset_id,
                name=body.name,
                description=body.description,
                tags=tags,
                negative_tags=neg_tags,
            )
        except Exception as e:
            raise HTTPException(status_code=403, detail=str(e))
        return _preset_to_detail(updated)

    @app.delete("/presets/{preset_id}", response_model=PresetDeleteResponse)
    def delete_preset(preset_id: str) -> PresetDeleteResponse:
        """★v1.7 プリセット削除"""
        ctx = get_context()
        try:
            deleted = ctx.preset_manager.delete(preset_id)
        except Exception as e:
            raise HTTPException(status_code=403, detail=str(e))
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
        return PresetDeleteResponse(id=preset_id, deleted=True)

    @app.post("/presets/{preset_id}/tags/add", response_model=PresetDetailResponse)
    def add_tags_to_preset(preset_id: str, body: PresetTagsAddRequest) -> PresetDetailResponse:
        """★v1.7 プリセットにタグを追記する"""
        ctx = get_context()
        from preset.models import PresetTag  # type: ignore[import]
        if not ctx.preset_manager.exists(preset_id):
            raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
        try:
            tags = [PresetTag(tag=t.tag, category=t.category, weight=t.weight) for t in body.tags]
            updated = ctx.preset_manager.add_tags(preset_id, tags, negative=body.negative)
        except Exception as e:
            raise HTTPException(status_code=403, detail=str(e))
        return _preset_to_detail(updated)

    # ── History ──────────────────────────────────────────────

    @app.get("/history", response_model=HistoryListResponse)
    def list_history(limit: int = Query(default=20, ge=1, le=200)) -> HistoryListResponse:
        ctx = get_context()
        entries = ctx.history_manager.list_entries(limit=limit)
        return HistoryListResponse(
            entries=[
                HistoryEntryResponse(
                    id=e.id,
                    input_prompt=e.input_prompt,
                    output_prompt=e.output_prompt,
                    tag_count=e.tag_count,
                    overall_score=e.overall_score,
                    created_at=e.created_at_str,
                    favorite=e.favorite,
                    label=e.label,
                )
                for e in entries
            ],
            total=len(entries),
        )

    # ── Validate ─────────────────────────────────────────────

    @app.post("/validate", response_model=ValidationResponse)
    def validate_all() -> ValidationResponse:
        ctx = get_context()
        errors: dict[str, list[str]] = {}

        dict_errors = ctx.dictionary_manager.validate()
        if dict_errors:
            errors["dictionary"] = dict_errors

        rule_errors = ctx.rule_manager.validate()
        if rule_errors:
            errors["rules"] = rule_errors

        preset_errors = ctx.preset_manager.validate()
        if preset_errors:
            errors["presets"] = preset_errors

        return ValidationResponse(success=len(errors) == 0, errors=errors)

    # ── M5-3 Knowledge Browser ────────────────────────────────────

    @app.get(
        "/dictionary/categories",
        response_model=CategoryListResponse,
        summary="Get all dictionary categories",
        tags=["dictionary"],
    )
    def get_dictionary_categories() -> CategoryListResponse:
        """辞書に登録されているカテゴリ一覧を返す（ソート済み）。"""
        ctx = get_context()
        cats = ctx.dictionary_manager.categories()
        return CategoryListResponse(categories=cats, total=len(cats))

    @app.get(
        "/dictionary/entries",
        response_model=EntriesResponse,
        summary="Browse dictionary entries",
        tags=["dictionary"],
    )
    def get_dictionary_entries(
        category: str | None = Query(default=None, description="絞り込むカテゴリ名"),
        search: str | None = Query(default=None, description="タグ名に対する部分一致検索"),
        limit: int = Query(default=50, ge=1, le=500, description="最大取得件数"),
    ) -> EntriesResponse:
        """カテゴリ絞り込み・テキスト検索でエントリ一覧を取得する。"""
        ctx = get_context()
        dm = ctx.dictionary_manager

        with dm._lock:
            raw_index: dict = dict(dm._index)

        seen: set[str] = set()
        unique_entries = []
        for entry in raw_index.values():
            if entry.key not in seen:
                seen.add(entry.key)
                unique_entries.append(entry)

        if category:
            unique_entries = [e for e in unique_entries if e.category == category]

        if search:
            q = search.lower()
            unique_entries = [
                e for e in unique_entries
                if q in e.key or q in e.resolved.lower()
            ]

        total = len(unique_entries)
        unique_entries.sort(key=lambda e: e.key)

        return EntriesResponse(
            entries=[
                DictionaryEntryItem(
                    key=e.key,
                    resolved=e.resolved,
                    weight=e.weight,
                    category=e.category,
                    synonyms=e.aliases,
                )
                for e in unique_entries[:limit]
            ],
            total=total,
            category=category,
            search=search or None,
        )

    @app.get(
        "/dictionary/synonyms",
        response_model=SynonymsResponse,
        summary="Get synonyms for a dictionary key",
        tags=["dictionary"],
    )
    def get_dictionary_synonyms(
        key: str = Query(..., description="辞書キー（例: blue_eyes）"),
    ) -> SynonymsResponse:
        """指定キーの同義語・詳細情報を返す。存在しない場合は 404。"""
        ctx = get_context()
        result = ctx.dictionary_manager.lookup(key)
        if not result.found or result.entry is None:
            raise HTTPException(status_code=404, detail=f"Key '{key}' not found in dictionary")

        return SynonymsResponse(
            key=result.key,
            synonyms=result.entry.aliases,
            resolved=result.resolved,  # type: ignore[arg-type]
            weight=result.weight,
            category=result.category,  # type: ignore[arg-type]
        )

    # ── v1.2 User Dictionary CRUD ─────────────────────────────────

    @app.get(
        "/dictionary/user/entries",
        response_model=UserEntryListResponse,
        summary="List user dictionary entries",
        tags=["dictionary"],
    )
    def list_user_entries() -> UserEntryListResponse:
        """ユーザー辞書エントリ一覧を返す。"""
        ctx = get_context()
        entries = ctx.dictionary_manager.list_user_entries()
        return UserEntryListResponse(
            entries=[UserEntryResponse(**e) for e in entries],
            total=len(entries),
        )

    @app.post(
        "/dictionary/user/entries",
        response_model=UserEntryResponse,
        summary="Add a user dictionary entry",
        tags=["dictionary"],
        status_code=201,
    )
    def create_user_entry(body: UserEntryCreateRequest) -> UserEntryResponse:
        """ユーザー辞書にエントリを追加する（既存キーは上書き）。"""
        ctx = get_context()
        ctx.dictionary_manager.add_user_entry(
            key=body.key,
            resolved=body.resolved,
            category=body.category,
            aliases=body.aliases,
            weight=body.weight,
        )
        return UserEntryResponse(
            key=body.key,
            resolved=body.resolved,
            category=body.category,
            aliases=body.aliases,
            weight=body.weight,
            tags=["user"],
        )

    @app.put(
        "/dictionary/user/entries/{key}",
        response_model=UserEntryResponse,
        summary="Update a user dictionary entry",
        tags=["dictionary"],
    )
    def update_user_entry(key: str, body: UserEntryUpdateRequest) -> UserEntryResponse:
        """ユーザー辞書エントリを部分更新する。存在しない場合は 404。"""
        ctx = get_context()
        ok = ctx.dictionary_manager.update_user_entry(
            key=key,
            resolved=body.resolved,
            category=body.category,
            aliases=body.aliases,
            weight=body.weight,
        )
        if not ok:
            raise HTTPException(status_code=404, detail=f"User entry '{key}' not found")
        result = ctx.dictionary_manager.lookup(key)
        if not result.found or result.entry is None:
            raise HTTPException(status_code=404, detail=f"User entry '{key}' not found after update")
        return UserEntryResponse(
            key=result.key,
            resolved=result.resolved or "",  # type: ignore[arg-type]
            category=result.category or "",  # type: ignore[arg-type]
            aliases=result.entry.aliases,
            weight=result.weight,
            tags=list(result.entry.tags),
        )

    @app.delete(
        "/dictionary/user/entries/{key}",
        response_model=UserEntryDeleteResponse,
        summary="Delete a user dictionary entry",
        tags=["dictionary"],
    )
    def delete_user_entry(key: str) -> UserEntryDeleteResponse:
        """ユーザー辞書からエントリを削除する。存在しない場合は 404。"""
        ctx = get_context()
        deleted = ctx.dictionary_manager.delete_user_entry(key)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"User entry '{key}' not found")
        return UserEntryDeleteResponse(key=key, deleted=True)

    # ── M5-4 History Timeline ────────────────────────────────────

    @app.get(
        "/history/{entry_id}",
        response_model=HistoryDetailResponse,
        summary="Get a single history entry",
        tags=["history"],
    )
    def get_history_entry(entry_id: str) -> HistoryDetailResponse:
        """ID で履歴エントリを 1 件取得する。存在しない場合は 404。"""
        ctx = get_context()
        entry = ctx.history_manager.get(entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"History entry '{entry_id}' not found")
        return HistoryDetailResponse(
            id=entry.id,
            input_prompt=entry.input_prompt,
            output_prompt=entry.output_prompt,
            output_negative=entry.output_negative,
            tag_count=entry.tag_count,
            overall_score=entry.overall_score,
            created_at=entry.created_at_str,
            favorite=entry.favorite,
            label=entry.label,
        )

    @app.post(
        "/history/{entry_id}/favorite",
        response_model=FavoriteToggleResponse,
        summary="Toggle favorite on a history entry",
        tags=["history"],
    )
    def toggle_history_favorite(entry_id: str) -> FavoriteToggleResponse:
        """お気に入りをトグルする。存在しない場合は 404。"""
        ctx = get_context()
        try:
            new_state = ctx.history_manager.toggle_favorite(entry_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"History entry '{entry_id}' not found"
            ) from exc
        return FavoriteToggleResponse(id=entry_id, favorite=new_state)

    @app.put(
        "/history/{entry_id}/label",
        response_model=LabelUpdateResponse,
        summary="Set label on a history entry",
        tags=["history"],
    )
    def update_history_label(entry_id: str, body: LabelUpdateRequest) -> LabelUpdateResponse:
        """履歴エントリにラベルを設定する。存在しない場合は 404。"""
        ctx = get_context()
        ok = ctx.history_manager.set_label(entry_id, body.label)
        if not ok:
            raise HTTPException(status_code=404, detail=f"History entry '{entry_id}' not found")
        return LabelUpdateResponse(id=entry_id, label=body.label)

    @app.get(
        "/history/{entry_id_1}/diff/{entry_id_2}",
        response_model=DiffResponse,
        summary="Compare two history entries",
        tags=["history"],
    )
    def diff_history_entries(entry_id_1: str, entry_id_2: str) -> DiffResponse:
        """2つの履歴エントリ間のタグ差分・スコア差分を返す。"""
        ctx = get_context()
        try:
            diff = ctx.history_manager.compare(entry_id_1, entry_id_2)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return DiffResponse(
            entry_id_1=entry_id_1,
            entry_id_2=entry_id_2,
            added_tags=diff.added_tags,
            removed_tags=diff.removed_tags,
            unchanged_tags=diff.unchanged_tags,
            score_delta=diff.score_delta,
            has_changes=diff.has_changes,
        )

    @app.delete(
        "/history/{entry_id}",
        response_model=DeleteHistoryResponse,
        summary="Delete a history entry",
        tags=["history"],
    )
    def delete_history_entry(entry_id: str) -> DeleteHistoryResponse:
        """履歴エントリを削除する。存在しない場合は 404。"""
        ctx = get_context()
        deleted = ctx.history_manager.delete(entry_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"History entry '{entry_id}' not found")
        return DeleteHistoryResponse(id=entry_id, deleted=True)

    # ── M6-3 Template Engine ─────────────────────────────────────

    def _get_template_manager():  # noqa: ANN201
        """TemplateManager を CliContext 経由で取得する（★v1.7 CliContext 委譲）"""
        ctx = get_context()
        return ctx.template_manager

    @app.get(
        "/templates",
        response_model=TemplateListResponse,
        summary="List prompt templates",
        tags=["templates"],
    )
    def list_templates(
        category: str | None = Query(default=None, description="カテゴリで絞り込み"),
    ) -> TemplateListResponse:
        """利用可能なテンプレート一覧を返す。"""
        tm = _get_template_manager()
        templates = tm.list_templates(category=category)
        return TemplateListResponse(
            templates=[
                TemplateSummaryResponse(
                    id=t.id,
                    name=t.name,
                    description=t.description,
                    body=t.body,
                    variables=[
                        TemplateVariableResponse(
                            name=v.name,
                            description=v.description,
                            default=v.default,
                            examples=v.examples,
                            required=v.required,
                        )
                        for v in t.variables
                    ],
                    tags=t.tags,
                    category=t.category,
                )
                for t in templates
            ],
            total=len(templates),
        )

    @app.post(
        "/templates/{template_id}/render",
        response_model=RenderResponse,
        summary="Render a template with variables",
        tags=["templates"],
    )
    def render_template(template_id: str, body: RenderRequest) -> RenderResponse:
        """テンプレートIDと変数辞書からプロンプトを展開する。存在しない場合は 404。"""
        tm = _get_template_manager()
        try:
            result = tm.render(template_id, body.variables)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RenderResponse(
            template_id=result.template_id,
            rendered=result.rendered,
            variables_used=result.variables_used,
            missing_variables=result.missing_variables,
            warnings=result.warnings,
            success=result.success,
        )

    @app.post(
        "/templates/render",
        response_model=RenderResponse,
        summary="Render a template body directly",
        tags=["templates"],
    )
    def render_template_body(
        template_body: str = Query(..., description="テンプレート本文（{var} 形式）"),
        body: RenderRequest = None,  # type: ignore[assignment]
    ) -> RenderResponse:
        """テンプレート本文を直接展開する（IDなし）。"""
        if body is None:
            body = RenderRequest()
        tm = _get_template_manager()
        result = tm.render_body(template_body, body.variables)
        return RenderResponse(
            template_id="",
            rendered=result.rendered,
            variables_used=result.variables_used,
            missing_variables=result.missing_variables,
            warnings=result.warnings,
            success=result.success,
        )

    # ── v1.8 Backup ──────────────────────────────────────────────

    def _get_backup_manager():
        """BackupManager を CliContext 経由で取得する"""
        ctx = get_context()
        return ctx.backup_manager

    @app.post(
        "/backup",
        response_model=BackupCreateResponse,
        summary="Create a backup",
        tags=["backup"],
        status_code=201,
    )
    def create_backup(body: BackupCreateRequest) -> BackupCreateResponse:
        """指定ターゲット（省略時は all）をバックアップする。"""
        from backup.models import BackupTarget  # type: ignore[import]
        bm = _get_backup_manager()
        try:
            target = BackupTarget(body.target)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid target: {body.target!r}")
        result = bm.backup(target)
        return BackupCreateResponse(
            success=result.success,
            entry_count=result.entry_count,
            total_kb=result.total_bytes / 1024,
            entries=[
                BackupEntryResponse(
                    id=e.id,
                    target=str(e.target),
                    source_path=str(e.source_path),
                    created_at=e.created_at_str,
                    size_kb=e.size_kb,
                )
                for e in result.entries
            ],
            error=result.error,
        )

    @app.get(
        "/backup",
        response_model=BackupListResponse,
        summary="List backups",
        tags=["backup"],
    )
    def list_backups(
        target: str | None = Query(default=None, description="ターゲット絞り込み"),
    ) -> BackupListResponse:
        """バックアップ一覧を新しい順で返す。"""
        from backup.models import BackupTarget  # type: ignore[import]
        bm = _get_backup_manager()
        t = None
        if target:
            try:
                t = BackupTarget(target)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid target: {target!r}")
        entries = bm.list_backups(target=t)
        return BackupListResponse(
            entries=[
                BackupEntryResponse(
                    id=e.id,
                    target=str(e.target),
                    source_path=str(e.source_path),
                    created_at=e.created_at_str,
                    size_kb=e.size_kb,
                )
                for e in entries
            ],
            total=len(entries),
        )

    @app.delete(
        "/backup/{entry_id}",
        response_model=BackupDeleteResponse,
        summary="Delete a backup entry",
        tags=["backup"],
    )
    def delete_backup(entry_id: str) -> BackupDeleteResponse:
        """バックアップを削除する。存在しない場合は 404。"""
        bm = _get_backup_manager()
        deleted = bm.delete(entry_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Backup '{entry_id}' not found")
        return BackupDeleteResponse(id=entry_id, deleted=True)

    @app.post(
        "/backup/{entry_id}/restore",
        response_model=BackupRestoreResponse,
        summary="Restore from a backup entry",
        tags=["backup"],
    )
    def restore_backup(entry_id: str) -> BackupRestoreResponse:
        """バックアップからリストアする。存在しない場合は 404。"""
        bm = _get_backup_manager()
        entry = bm.get_or_none(entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Backup '{entry_id}' not found")
        result = bm.restore(entry_id)
        return BackupRestoreResponse(
            success=result.success,
            restored_files=len(result.restored_files),
            error=result.error,
        )

    # ── v1.8 History 強化 ─────────────────────────────────────────

    @app.get(
        "/history/stats",
        response_model=HistoryStatsResponse,
        summary="Get history statistics",
        tags=["history"],
    )
    def history_stats() -> HistoryStatsResponse:
        """変換履歴の統計情報（頻出タグ・スコア分布）を返す。"""
        ctx = get_context()
        entries = ctx.history_manager.list_entries(limit=500)

        # スコア分布
        dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
        total_score = 0.0
        fav_count = 0
        tag_counts: dict[str, int] = {}
        tag_weight: dict[str, float] = {}

        for e in entries:
            s = e.overall_score
            total_score += s
            if e.favorite:
                fav_count += 1
            if s >= 80:
                dist["excellent"] += 1
            elif s >= 60:
                dist["good"] += 1
            elif s >= 40:
                dist["fair"] += 1
            else:
                dist["poor"] += 1
            # タグ頻度集計（output_prompt から簡易抽出）
            for tag in e.output_prompt.split(","):
                t = tag.strip().lower()
                if t:
                    tag_counts[t] = tag_counts.get(t, 0) + 1
                    tag_weight[t] = tag_weight.get(t, 0.0) + 1.0

        avg_score = total_score / len(entries) if entries else 0.0
        top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:20]

        return HistoryStatsResponse(
            total_entries=len(entries),
            favorite_count=fav_count,
            avg_score=round(avg_score, 1),
            top_tags=[
                TagFrequency(
                    tag=t,
                    count=c,
                    avg_weight=round(tag_weight.get(t, 0) / c, 2),
                )
                for t, c in top_tags
            ],
            score_distribution=dist,
        )

    @app.get(
        "/history/export",
        response_model=HistoryExportResponse,
        summary="Export history as CSV or JSON",
        tags=["history"],
    )
    def export_history(
        format: str = Query(default="csv", description="出力フォーマット: csv | json"),
        limit: int = Query(default=100, ge=1, le=1000),
        favorite_only: bool = Query(default=False),
        min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    ) -> HistoryExportResponse:
        """変換履歴を CSV または JSON でエクスポートする。"""
        import csv, io
        ctx = get_context()
        entries = ctx.history_manager.list_entries(limit=limit)
        if favorite_only:
            entries = [e for e in entries if e.favorite]
        if min_score > 0:
            entries = [e for e in entries if e.overall_score >= min_score]

        if format == "json":
            data = json_module.dumps([
                {
                    "id": e.id,
                    "input_prompt": e.input_prompt,
                    "output_prompt": e.output_prompt,
                    "score": e.overall_score,
                    "favorite": e.favorite,
                    "label": e.label,
                    "created_at": e.created_at_str,
                }
                for e in entries
            ], ensure_ascii=False, indent=2)
        else:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["id", "created_at", "score", "favorite", "label",
                             "input_prompt", "output_prompt"])
            for e in entries:
                writer.writerow([
                    e.id, e.created_at_str, e.overall_score,
                    e.favorite, e.label, e.input_prompt, e.output_prompt,
                ])
            data = buf.getvalue()

        return HistoryExportResponse(format=format, total=len(entries), data=data)

    # ── v1.8 Dashboard ───────────────────────────────────────────

    @app.get(
        "/dashboard",
        response_model=DashboardResponse,
        summary="Get overall dashboard stats",
        tags=["dashboard"],
    )
    def dashboard() -> DashboardResponse:
        """辞書・プリセット・履歴・バックアップの統計サマリを返す。"""
        from fps_core import __version__  # type: ignore[import]
        ctx = get_context()
        dict_stats   = ctx.dictionary_manager.statistics()
        preset_stats = ctx.preset_manager.statistics()
        bm = _get_backup_manager()
        bk_list = bm.list_backups()
        history = ctx.history_manager.list_entries(limit=200)

        # 日本語エントリ数（tags フィールドに "japanese" を含むもの）
        jp_count = 0
        try:
            import json as _json
            jp_path = _ROOT / "fps-data" / "dictionaries" / "system" / "synonyms" / "japanese_tags.json"
            if jp_path.exists():
                jp_data = _json.loads(jp_path.read_text(encoding="utf-8"))
                jp_count = len(jp_data.get("entries", []))
        except Exception:
            pass

        avg_score = 0.0
        tag_counts: dict[str, int] = {}
        for e in history:
            avg_score += e.overall_score
            for tag in e.output_prompt.split(","):
                t = tag.strip().lower()
                if t:
                    tag_counts[t] = tag_counts.get(t, 0) + 1
        if history:
            avg_score /= len(history)

        top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]
        recent = [e.input_prompt[:60] for e in history[:5]]

        return DashboardResponse(
            version="2.9.0",
            dictionary_keys=dict_stats.get("total_keys", 0),
            japanese_entries=jp_count,
            preset_count=preset_stats.get("total_presets", 0),
            history_count=len(history),
            backup_count=len(bk_list),
            avg_score=round(avg_score, 1),
            top_tags=[TagFrequency(tag=t, count=c) for t, c in top_tags],
            recent_activity=recent,
        )



    # ══════════════════════════════════════════════════════════════
    # v2.0 パーソナライゼーション — /profile
    # ══════════════════════════════════════════════════════════════

    def _get_upm():
        """UserProfileManager を CliContext 経由で取得する"""
        return get_context().user_profile_manager

    @app.get(
        "/profile",
        response_model=ProfileResponse,
        summary="Get user profile",
        tags=["profile"],
    )
    def get_profile() -> ProfileResponse:
        """ユーザープロファイルの概要を返す（頻出タグ・スタイルルール・学習日時）。"""
        upm = _get_upm()
        p = upm.get_profile()
        stats = upm.statistics()
        top = upm.recommend(20)
        return ProfileResponse(
            tag_weight_count=stats["tag_weight_count"],
            excluded_tag_count=stats["excluded_tag_count"],
            style_rule_count=stats["style_rule_count"],
            tag_frequency_count=stats["tag_frequency_count"],
            score_trend_count=stats["score_trend_count"],
            last_learned=stats["last_learned"],
            top_tags=[TagFreqItem(tag=e.tag, count=e.count,
                                  avg_weight=round(e.avg_weight, 3),
                                  last_used=e.last_used.isoformat()) for e in top],
            style_rules=[StyleRuleItem(id=r.id, name=r.name,
                                       always_include=r.always_include,
                                       always_exclude=r.always_exclude,
                                       enabled=r.enabled)
                         for r in p.style_rules],
        )

    @app.post(
        "/profile/learn",
        response_model=ProfileLearnResponse,
        summary="Learn from history",
        tags=["profile"],
    )
    def learn_from_history(
        limit: int = Query(default=200, ge=10, le=1000,
                           description="学習に使う履歴件数"),
        days: int = Query(default=30, ge=1, le=365,
                          description="スコアトレンド集計日数"),
    ) -> ProfileLearnResponse:
        """変換履歴からタグ頻度を学習し、スコアトレンドを更新する。"""
        ctx = get_context()
        upm = _get_upm()
        entries = ctx.history_manager.list_entries(limit=limit)
        result = upm.learn(entries)
        upm.build_score_trends(entries, days=days)
        return ProfileLearnResponse(
            learned=result["learned"],
            updated=result["updated"],
            total=result["total"],
            trend_days=days,
        )

    @app.get(
        "/profile/recommendations",
        response_model=ProfileRecommendResponse,
        summary="Get tag recommendations",
        tags=["profile"],
    )
    def get_recommendations(
        n: int = Query(default=20, ge=1, le=50, description="推奨タグ件数"),
    ) -> ProfileRecommendResponse:
        """使用頻度と重みに基づく推奨タグリストを返す。"""
        upm = _get_upm()
        recs = upm.recommend(n)
        return ProfileRecommendResponse(
            recommendations=[TagFreqItem(tag=e.tag, count=e.count,
                                         avg_weight=round(e.avg_weight, 3),
                                         last_used=e.last_used.isoformat()) for e in recs],
            total=len(recs),
        )

    @app.get(
        "/profile/score-trend",
        response_model=ProfileScoreTrendResponse,
        summary="Get score trend",
        tags=["profile"],
    )
    def get_score_trend(
        days: int = Query(default=30, ge=1, le=365),
    ) -> ProfileScoreTrendResponse:
        """過去N日間のスコア傾向（日別集計）を返す。"""
        ctx = get_context()
        upm = _get_upm()
        entries = ctx.history_manager.list_entries(limit=500)
        trends = upm.build_score_trends(entries, days=days)
        return ProfileScoreTrendResponse(
            trends=[ScoreTrendItem(date=t.date, avg_score=t.avg_score,
                                   entry_count=t.entry_count, top_tag=t.top_tag)
                    for t in trends],
            days=days,
            total=len(trends),
        )

    @app.put(
        "/profile/tags/{tag}/weight",
        response_model=TagWeightItem,
        summary="Set tag weight",
        tags=["profile"],
    )
    def set_tag_weight(tag: str, body: SetTagWeightRequest) -> TagWeightItem:
        """タグの重みを設定する（0.0 = 除外、1.0 = 標準、最大 3.0）。"""
        upm = _get_upm()
        tw = upm.set_tag_weight(tag, body.weight, body.reason)
        return TagWeightItem(tag=tw.tag, weight=tw.weight, reason=tw.reason)

    @app.delete(
        "/profile/tags/{tag}/weight",
        summary="Remove tag weight override",
        tags=["profile"],
    )
    def remove_tag_weight(tag: str) -> dict:
        """タグの重み設定を削除してデフォルトに戻す。"""
        upm = _get_upm()
        deleted = upm.remove_tag_weight(tag)
        return {"tag": tag, "deleted": deleted}

    @app.post(
        "/profile/rules",
        response_model=StyleRuleItem,
        status_code=201,
        summary="Add a style rule",
        tags=["profile"],
    )
    def add_style_rule(body: AddStyleRuleRequest) -> StyleRuleItem:
        """スタイルルール（常時include/exclude）を追加する。"""
        from user.models import StyleRule as SR  # type: ignore[import]
        upm = _get_upm()
        rule = SR(id=body.id, name=body.name,
                  always_include=body.always_include,
                  always_exclude=body.always_exclude,
                  enabled=body.enabled)
        r = upm.add_style_rule(rule)
        return StyleRuleItem(id=r.id, name=r.name,
                             always_include=r.always_include,
                             always_exclude=r.always_exclude,
                             enabled=r.enabled)

    @app.delete(
        "/profile/rules/{rule_id}",
        summary="Remove a style rule",
        tags=["profile"],
    )
    def remove_style_rule(rule_id: str) -> dict:
        """スタイルルールを削除する。"""
        upm = _get_upm()
        deleted = upm.remove_style_rule(rule_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
        return {"id": rule_id, "deleted": True}

    @app.delete(
        "/profile/reset",
        response_model=ProfileResetResponse,
        summary="Reset user profile",
        tags=["profile"],
    )
    def reset_profile() -> ProfileResetResponse:
        """ユーザープロファイルを完全リセットする。"""
        upm = _get_upm()
        upm.reset()
        return ProfileResetResponse(reset=True, message="プロファイルをリセットしました")










    # ══════════════════════════════════════════════════════════════
    # v2.9 日本語→タグ翻訳（/translate）
    # ══════════════════════════════════════════════════════════════

    def _get_te():
        """TranslateEngine を CliContext 経由で取得する"""
        return get_context().translate_engine

    @app.post(
        "/translate/jp-to-tags",
        response_model=TranslateResponse,
        summary="Translate Japanese text to English tags",
        tags=["translate"],
    )
    def translate_jp_to_tags(body: TranslateRequest) -> TranslateResponse:
        """
        ★ v2.9 — 日本語テキストを英語タグリストに変換する。

        「青い目の金髪の少女、笑顔、アニメ風」
        → ["blue_eyes", "blonde_hair", "1girl", "smile", "anime_style"]

        辞書ベースで外部API不要。use_api=true を指定すると
        /profile/settings で設定した翻訳APIを使って補完する。
        """
        engine = _get_te()
        result = engine.translate(body.text, max_tags=body.max_tags,
                                  use_api=body.use_api)
        return TranslateResponse(
            original=result.original,
            tags=result.tags,
            prompt=result.to_prompt(),
            unmapped=result.unmapped,
            confidence=result.confidence,
            method=result.method,
            detail=[TranslateDetailItem(**d) for d in result.detail],
        )

    @app.post(
        "/translate/detect",
        response_model=DetectLanguageResponse,
        summary="Detect language of prompt text",
        tags=["translate"],
    )
    def detect_language(body: TranslateRequest) -> DetectLanguageResponse:
        """★ v2.9 — テキストの言語を検出する（ja/en/mixed/unknown）。"""
        engine = _get_te()
        lang   = engine.detect_language(body.text)
        return DetectLanguageResponse(text=body.text, language=lang)

    # ══════════════════════════════════════════════════════════════
    # v2.9 プロンプトチェーン（/chains）
    # ══════════════════════════════════════════════════════════════

    def _get_chainm():
        """ChainManager を CliContext 経由で取得する"""
        return get_context().chain_manager

    def _chain_to_response(c: Any) -> ChainResponse:
        return ChainResponse(
            id=c.id, name=c.name, description=c.description,
            steps=[ChainStepItem(type=s.type, params=s.params,
                                  label=s.label, enabled=s.enabled)
                   for s in c.steps],
            step_count=len(c.steps),
            created_at=c.created_at, updated_at=c.updated_at,
        )

    @app.get(
        "/chains",
        response_model=ChainListResponse,
        summary="List all prompt chains",
        tags=["chains"],
    )
    def list_chains() -> ChainListResponse:
        """★ v2.9 — プロンプトチェーン一覧を返す。"""
        cm = _get_chainm()
        chains = cm.list_all()
        return ChainListResponse(
            chains=[_chain_to_response(c) for c in chains],
            total=len(chains),
        )

    @app.post(
        "/chains",
        response_model=ChainResponse,
        status_code=201,
        summary="Create a prompt chain",
        tags=["chains"],
    )
    def create_chain(body: ChainCreateRequest) -> ChainResponse:
        """★ v2.9 — プロンプトチェーンを新規作成する。"""
        cm = _get_chainm()
        c  = cm.create(body.name, [s.model_dump() for s in body.steps],
                       body.description)
        return _chain_to_response(c)

    @app.get(
        "/chains/{chain_id}",
        response_model=ChainResponse,
        summary="Get a prompt chain",
        tags=["chains"],
    )
    def get_chain(chain_id: str) -> ChainResponse:
        """★ v2.9 — プロンプトチェーンを取得する。"""
        cm = _get_chainm()
        c  = cm.get(chain_id)
        if c is None:
            raise HTTPException(status_code=404, detail=f"Chain '{chain_id}' not found")
        return _chain_to_response(c)

    @app.put(
        "/chains/{chain_id}",
        response_model=ChainResponse,
        summary="Update a prompt chain",
        tags=["chains"],
    )
    def update_chain(chain_id: str, body: ChainUpdateRequest) -> ChainResponse:
        """★ v2.9 — プロンプトチェーンを更新する。"""
        cm = _get_chainm()
        c  = cm.update(chain_id, body.name,
                       [s.model_dump() for s in body.steps] if body.steps else None,
                       body.description)
        if c is None:
            raise HTTPException(status_code=404, detail=f"Chain '{chain_id}' not found")
        return _chain_to_response(c)

    @app.delete(
        "/chains/{chain_id}",
        summary="Delete a prompt chain",
        tags=["chains"],
    )
    def delete_chain(chain_id: str) -> dict:
        """★ v2.9 — プロンプトチェーンを削除する。"""
        cm = _get_chainm()
        if not cm.delete(chain_id):
            raise HTTPException(status_code=404, detail=f"Chain '{chain_id}' not found")
        return {"id": chain_id, "deleted": True}

    @app.post(
        "/chains/{chain_id}/run",
        response_model=ChainRunResponse,
        summary="Run a prompt chain",
        tags=["chains"],
    )
    def run_chain(chain_id: str, body: ChainRunRequest) -> ChainRunResponse:
        """
        ★ v2.9 — プロンプトチェーンを実行する。

        各ステップを順番に実行し、最終的な pos/neg プロンプトを返す。

        ステップ種別:
          wildcard  — Wildcard 構文を展開
          translate — 日本語→タグ変換
          compile   — FPS パイプラインでコンパイル
          profile   — UserProfile を適用
          filter    — カテゴリフィルタ
          export    — 形式変換
        """
        cm = _get_chainm()
        result = cm.run(chain_id, body.prompt, body.neg, context=get_context())
        return ChainRunResponse(
            chain_id=result.chain_id,
            chain_name=result.chain_name,
            input=result.input,
            final_pos=result.final_pos,
            final_neg=result.final_neg,
            total_ms=round(result.total_ms, 1),
            success=result.success,
            error=result.error,
            steps=[
                ChainStepResultItem(
                    step_index=s.step_index, step_type=s.step_type,
                    output_pos=s.output_pos,
                    elapsed_ms=round(s.elapsed_ms, 1),
                    success=s.success, error=s.error,
                ) for s in result.steps
            ],
        )

    # ══════════════════════════════════════════════════════════════
    # v2.9 ComfyUI API クライアント（/comfyui-client）
    # ══════════════════════════════════════════════════════════════

    def _get_cc():
        """ComfyUIClient を CliContext 経由で取得する"""
        return get_context().comfyui_client

    @app.get(
        "/comfyui-client/status",
        response_model=ComfyUIStatusResponse,
        summary="Get ComfyUI connection status",
        tags=["comfyui-client"],
    )
    def comfyui_status() -> ComfyUIStatusResponse:
        """
        ★ v2.9 — ComfyUI の接続状態とキュー状態を返す。

        ComfyUI が起動していない場合も available=false で正常にレスポンスする。
        """
        cc = _get_cc()
        available = cc.is_available()
        if not available:
            return ComfyUIStatusResponse(
                available=False, base_url=cc._base,
                queue_running=0, queue_pending=0, queue_remaining=0,
            )
        qs    = cc.get_queue_status()
        stats = cc.get_system_stats()
        return ComfyUIStatusResponse(
            available=True, base_url=cc._base,
            queue_running=len(qs.running),
            queue_pending=len(qs.pending),
            queue_remaining=qs.queue_remaining,
            system_stats=stats,
        )

    @app.post(
        "/comfyui-client/queue",
        response_model=ComfyUIQueueResponse,
        summary="Queue a prompt to ComfyUI",
        tags=["comfyui-client"],
    )
    def comfyui_queue(body: ComfyUIQueueRequest) -> ComfyUIQueueResponse:
        """
        ★ v2.9 — プロンプトを ComfyUI キューに送信する。

        ComfyUI が起動していない場合は 503 を返す。
        返却された prompt_id で /comfyui-client/status/{id} から状態を確認できる。
        """
        cc = _get_cc()
        if not cc.is_available():
            raise HTTPException(status_code=503,
                                detail="ComfyUI が起動していません (localhost:8188)")
        entry = cc.queue_prompt(
            body.pos, body.neg, body.workflow,
            body.model, body.steps, body.cfg,
            body.width, body.height, body.seed,
        )
        return ComfyUIQueueResponse(
            prompt_id=entry.prompt_id,
            status=entry.status,
            error=entry.error,
        )

    @app.get(
        "/comfyui-client/queue",
        summary="Get ComfyUI queue status",
        tags=["comfyui-client"],
    )
    def comfyui_queue_status() -> dict:
        """★ v2.9 — ComfyUI キューの現在の状態を返す。"""
        cc = _get_cc()
        if not cc.is_available():
            return {"available": False, "queue_remaining": 0}
        qs = cc.get_queue_status()
        return qs.to_dict()


    # ══════════════════════════════════════════════════════════════
    # v2.8 マルチフォーマット エクスポート（/export）
    # ══════════════════════════════════════════════════════════════

    @app.post(
        "/export/a1111",
        response_model=ExportResponse,
        summary="Export to Automatic1111 format",
        tags=["export"],
    )
    def export_a1111(body: ExportRequest) -> ExportResponse:
        """
        ★ v2.8 — A1111 WebUI 互換テキスト形式でエクスポートする。

        出力例:
          masterpiece, 1girl, blue_eyes
          Negative prompt: bad_quality, blurry
          Steps: 20, Sampler: Euler a, CFG scale: 7, Size: 512x512
        """
        from export.exporters import A1111Exporter  # type: ignore
        exporter = A1111Exporter(
            steps=body.steps, sampler=body.sampler, cfg=body.cfg,
            width=body.width, height=body.height,
            model=body.model, seed=body.seed,
        )
        result = exporter.export(body.pos, body.neg, body.meta)
        return ExportResponse(
            format=result.format, content=result.content,
            filename=result.filename, mime_type=result.mime_type,
        )

    @app.post(
        "/export/novelai",
        response_model=ExportResponse,
        summary="Export to NovelAI format",
        tags=["export"],
    )
    def export_novelai(body: ExportRequest) -> ExportResponse:
        """
        ★ v2.8 — NovelAI 互換 JSON 形式でエクスポートする。

        A1111 の (tag:1.2) 記法を {{tag}} / [[tag]] に自動変換する。
        """
        from export.exporters import NovelAIExporter  # type: ignore
        result = NovelAIExporter().export(body.pos, body.neg, body.meta)
        return ExportResponse(
            format=result.format, content=result.content,
            filename=result.filename, mime_type=result.mime_type,
        )

    @app.post(
        "/export/bundle",
        summary="Export all formats as ZIP bundle",
        tags=["export"],
    )
    def export_bundle(body: ExportRequest):
        """
        ★ v2.8 — 全形式（A1111/NovelAI/JSON/YAML/CSV）を ZIP で一括エクスポートする。
        バイナリレスポンスとして返す。
        """
        from fastapi.responses import Response  # type: ignore
        from export.exporters import BundleExporter  # type: ignore
        result = BundleExporter().export(
            body.pos, body.neg, body.meta, label=body.label
        )
        return Response(
            content=result.content,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={result.filename}"},
        )

    # ══════════════════════════════════════════════════════════════
    # v2.8 セッション管理（/sessions）
    # ══════════════════════════════════════════════════════════════

    def _get_sm():
        """SessionManager を CliContext 経由で取得する"""
        return get_context().session_manager

    def _session_to_response(
        s: Any, include_entries: bool = False
    ) -> SessionResponse:
        return SessionResponse(
            id=s.id, name=s.name, description=s.description,
            tags=s.tags, entry_count=s.entry_count,
            is_pinned=s.is_pinned,
            created_at=s.created_at, updated_at=s.updated_at,
            entries=[
                SessionEntryItem(
                    index=e.index, label=e.label,
                    pos=e.pos, neg=e.neg,
                    score=e.score, metadata=e.metadata,
                    created_at=e.created_at,
                )
                for e in s.entries
            ] if include_entries else [],
        )

    @app.get(
        "/sessions",
        response_model=SessionListResponse,
        summary="List all sessions",
        tags=["sessions"],
    )
    def list_sessions(
        tag: str | None = Query(default=None, description="タグでフィルタ"),
    ) -> SessionListResponse:
        """★ v2.8 — セッション一覧（ピン留め優先、更新日時降順）。"""
        sm = _get_sm()
        sessions = sm.list_all(tag_filter=tag)
        return SessionListResponse(
            sessions=[_session_to_response(s) for s in sessions],
            total=len(sessions), stats=sm.statistics(),
        )

    @app.post(
        "/sessions",
        response_model=SessionResponse,
        status_code=201,
        summary="Create a session",
        tags=["sessions"],
    )
    def create_session(body: SessionCreateRequest) -> SessionResponse:
        """★ v2.8 — 新しいセッションを作成する。"""
        sm = _get_sm()
        s  = sm.create(body.name, body.description, body.tags)
        return _session_to_response(s)

    @app.get(
        "/sessions/{session_id}",
        response_model=SessionResponse,
        summary="Get a session with all entries",
        tags=["sessions"],
    )
    def get_session(session_id: str) -> SessionResponse:
        """★ v2.8 — セッションの全エントリを含む詳細を返す。"""
        sm = _get_sm()
        s  = sm.get(session_id)
        if s is None:
            raise HTTPException(status_code=404,
                                detail=f"Session '{session_id}' not found")
        return _session_to_response(s, include_entries=True)

    @app.put(
        "/sessions/{session_id}",
        response_model=SessionResponse,
        summary="Update a session",
        tags=["sessions"],
    )
    def update_session(session_id: str,
                       body: SessionUpdateRequest) -> SessionResponse:
        """★ v2.8 — セッションのメタ情報を更新する（ピン留め/名前/タグ）。"""
        sm = _get_sm()
        s  = sm.update(session_id, body.name, body.description,
                       body.tags, body.is_pinned)
        if s is None:
            raise HTTPException(status_code=404,
                                detail=f"Session '{session_id}' not found")
        return _session_to_response(s)

    @app.delete(
        "/sessions/{session_id}",
        summary="Delete a session",
        tags=["sessions"],
    )
    def delete_session(session_id: str) -> dict:
        """★ v2.8 — セッションを削除する。"""
        sm = _get_sm()
        if not sm.delete(session_id):
            raise HTTPException(status_code=404,
                                detail=f"Session '{session_id}' not found")
        return {"id": session_id, "deleted": True}

    @app.post(
        "/sessions/{session_id}/entries",
        response_model=SessionEntryItem,
        status_code=201,
        summary="Add an entry to a session",
        tags=["sessions"],
    )
    def add_session_entry(
        session_id: str, body: SessionAddEntryRequest
    ) -> SessionEntryItem:
        """★ v2.8 — セッションにプロンプトエントリを追加する。"""
        sm    = _get_sm()
        entry = sm.add_entry(
            session_id, body.pos, body.neg, body.label,
            body.score, body.metadata,
        )
        if entry is None:
            raise HTTPException(status_code=404,
                                detail=f"Session '{session_id}' not found")
        return SessionEntryItem(
            index=entry.index, label=entry.label,
            pos=entry.pos, neg=entry.neg,
            score=entry.score, metadata=entry.metadata,
            created_at=entry.created_at,
        )

    @app.get(
        "/sessions/{session_id}/compare/{idx_a}/{idx_b}",
        response_model=SessionCompareResponse,
        summary="Compare two entries in a session",
        tags=["sessions"],
    )
    def compare_session_entries(
        session_id: str, idx_a: int, idx_b: int
    ) -> SessionCompareResponse:
        """
        ★ v2.8 — セッション内の2エントリを比較する。

        only_in_a: A にのみあるタグ
        only_in_b: B にのみあるタグ
        common:    両方にあるタグ
        score_diff: B.score - A.score
        """
        sm     = _get_sm()
        result = sm.compare(session_id, idx_a, idx_b)
        if result is None:
            raise HTTPException(status_code=404,
                                detail="Session or entry not found")
        return SessionCompareResponse(**result)


    # ══════════════════════════════════════════════════════════════
    # v2.7 キャラクターシート（/characters）
    # ══════════════════════════════════════════════════════════════

    def _get_cm():
        """CharacterManager を CliContext 経由で取得する"""
        return get_context().character_manager

    def _char_to_response(char: Any) -> CharacterResponse:
        return CharacterResponse(
            id=char.id, name=char.name, description=char.description,
            features=[CharacterFeatureItem(tag=f.tag, weight=f.weight,
                       category=f.category, note=f.note) for f in char.features],
            neg_features=[CharacterFeatureItem(tag=f.tag, weight=f.weight,
                           category=f.category, note=f.note) for f in char.neg_features],
            tags=char.tags,
            pos_prompt=char.to_pos_prompt(),
            neg_prompt=char.to_neg_prompt(),
            feature_count=len(char.features),
            created_at=char.created_at, updated_at=char.updated_at,
        )

    @app.get(
        "/characters",
        response_model=CharacterListResponse,
        summary="List all characters",
        tags=["characters"],
    )
    def list_characters() -> CharacterListResponse:
        """★ v2.7 — キャラクターシート一覧を返す。"""
        cm = _get_cm()
        chars = cm.list_all()
        return CharacterListResponse(
            characters=[_char_to_response(c) for c in chars],
            total=len(chars), stats=cm.statistics(),
        )

    @app.post(
        "/characters",
        response_model=CharacterResponse,
        status_code=201,
        summary="Create a character",
        tags=["characters"],
    )
    def create_character(body: CharacterCreateRequest) -> CharacterResponse:
        """★ v2.7 — キャラクターシートを新規作成する。"""
        cm = _get_cm()
        char = cm.create(
            id=body.id, name=body.name, description=body.description,
            features=[f.model_dump() for f in body.features],
            neg_features=[f.model_dump() for f in body.neg_features],
            tags=body.tags,
        )
        return _char_to_response(char)

    @app.get(
        "/characters/{character_id}",
        response_model=CharacterResponse,
        summary="Get a character",
        tags=["characters"],
    )
    def get_character(character_id: str) -> CharacterResponse:
        """★ v2.7 — 指定キャラクターを取得する。"""
        cm   = _get_cm()
        char = cm.get(character_id)
        if char is None:
            raise HTTPException(status_code=404,
                                detail=f"Character '{character_id}' not found")
        return _char_to_response(char)

    @app.put(
        "/characters/{character_id}",
        response_model=CharacterResponse,
        summary="Update a character",
        tags=["characters"],
    )
    def update_character(
        character_id: str, body: CharacterUpdateRequest
    ) -> CharacterResponse:
        """★ v2.7 — キャラクターシートを部分更新する。"""
        cm   = _get_cm()
        char = cm.update(
            character_id,
            name=body.name, description=body.description,
            features=[f.model_dump() for f in body.features] if body.features else None,
            neg_features=[f.model_dump() for f in body.neg_features] if body.neg_features else None,
            tags=body.tags,
        )
        if char is None:
            raise HTTPException(status_code=404,
                                detail=f"Character '{character_id}' not found")
        return _char_to_response(char)

    @app.delete(
        "/characters/{character_id}",
        summary="Delete a character",
        tags=["characters"],
    )
    def delete_character(character_id: str) -> dict:
        """★ v2.7 — キャラクターシートを削除する。"""
        cm = _get_cm()
        if not cm.delete(character_id):
            raise HTTPException(status_code=404,
                                detail=f"Character '{character_id}' not found")
        return {"id": character_id, "deleted": True}

    @app.post(
        "/characters/{character_id}/to-preset",
        response_model=None,
        status_code=201,
        summary="Convert character to preset",
        tags=["characters"],
    )
    def character_to_preset(
        character_id: str, body: CharacterToPresetRequest
    ) -> dict:
        """★ v2.7 — キャラクターシートをプリセットに変換して保存する。"""
        ctx  = get_context()
        cm   = _get_cm()
        preset = cm.to_preset(character_id, ctx.preset_manager,
                              preset_id=body.preset_id)
        if preset is None:
            raise HTTPException(status_code=404,
                                detail=f"Character '{character_id}' not found")
        return {
            "preset_id":  preset.id,
            "name":       preset.name,
            "tag_count":  len(preset.tags),
        }


    # ══════════════════════════════════════════════════════════════
    # v2.6 Wildcard CRUD（/wildcards）
    # ══════════════════════════════════════════════════════════════

    def _get_wm():
        """WildcardManager を CliContext 経由で取得する"""
        return get_context().wildcard_manager

    def _wf_to_response(wf: Any, include_entries: bool = False) -> WildcardResponse:
        return WildcardResponse(
            name=wf.name, description=wf.description,
            category=wf.category, entry_count=len(wf.entries),
            entries=[WildcardEntryItem(value=e.value, weight=e.weight,
                                       comment=e.comment)
                     for e in wf.entries] if include_entries else [],
            created_at=wf.created_at, updated_at=wf.updated_at,
        )

    @app.get(
        "/wildcards",
        response_model=WildcardListResponse,
        summary="List all wildcards",
        tags=["wildcards"],
    )
    def list_wildcards(
        category: str | None = Query(default=None),
    ) -> WildcardListResponse:
        """★ v2.6 — Wildcard 一覧を返す。"""
        wm = _get_wm()
        wildcards = wm.list_all(category=category)
        stats = wm.statistics()
        return WildcardListResponse(
            wildcards=[_wf_to_response(wf) for wf in wildcards],
            total=len(wildcards), stats=stats,
        )

    @app.post(
        "/wildcards",
        response_model=WildcardResponse,
        status_code=201,
        summary="Create a wildcard",
        tags=["wildcards"],
    )
    def create_wildcard(body: WildcardCreateRequest) -> WildcardResponse:
        """★ v2.6 — 新しい Wildcard を作成する。"""
        wm = _get_wm()
        wf = wm.create(
            name=body.name, values=body.values,
            description=body.description, category=body.category,
            weights=body.weights,
        )
        return _wf_to_response(wf, include_entries=True)

    @app.get(
        "/wildcards/{name:path}",
        response_model=WildcardResponse,
        summary="Get a wildcard",
        tags=["wildcards"],
    )
    def get_wildcard(name: str) -> WildcardResponse:
        """★ v2.6 — 指定 Wildcard を取得する（エントリ含む）。"""
        wm = _get_wm()
        wf = wm.get(name)
        if wf is None:
            raise HTTPException(status_code=404, detail=f"Wildcard '{name}' not found")
        return _wf_to_response(wf, include_entries=True)

    @app.put(
        "/wildcards/{name:path}",
        response_model=WildcardResponse,
        summary="Update a wildcard",
        tags=["wildcards"],
    )
    def update_wildcard(name: str, body: WildcardUpdateRequest) -> WildcardResponse:
        """★ v2.6 — Wildcard を部分更新する。"""
        wm = _get_wm()
        wf = wm.update(name, values=body.values, description=body.description,
                       category=body.category, weights=body.weights)
        if wf is None:
            raise HTTPException(status_code=404, detail=f"Wildcard '{name}' not found")
        return _wf_to_response(wf, include_entries=True)

    @app.delete(
        "/wildcards/{name:path}",
        summary="Delete a wildcard",
        tags=["wildcards"],
    )
    def delete_wildcard(name: str) -> dict:
        """★ v2.6 — Wildcard を削除する。"""
        wm = _get_wm()
        if not wm.delete(name):
            raise HTTPException(status_code=404, detail=f"Wildcard '{name}' not found")
        return {"name": name, "deleted": True}

    @app.post(
        "/wildcards/expand",
        response_model=WildcardExpandResponse,
        summary="Expand wildcard syntax in a prompt",
        tags=["wildcards"],
    )
    def expand_wildcards(body: WildcardExpandRequest) -> WildcardExpandResponse:
        """
        ★ v2.6 — プロンプト内の Wildcard 構文を展開してプレビューを返す。

        サポートする構文:
          __wildcard__       Wildcard ファイルからランダム選択
          [[A|B|C]]          インラインランダム選択
          [[A|B|C]]:2        複数選択
          {{var:default}}    変数展開
          {A|B|C}            A1111 互換ランダム選択

        n=5 を指定するとランダム展開を 5 パターン生成する。
        """
        from wildcard.engine import WildcardEngine  # type: ignore
        wm = _get_wm()
        engine = WildcardEngine(wildcard_manager=wm, seed=body.seed)
        expanded = engine.preview_expand(body.prompt, n=body.n,
                                         seed=body.seed)
        wildcards_used = engine.extract_wildcards(body.prompt)
        return WildcardExpandResponse(
            original=body.prompt,
            expanded=expanded,
            wildcards_used=wildcards_used,
        )

    @app.post(
        "/wildcards/{name:path}/import",
        response_model=WildcardResponse,
        status_code=201,
        summary="Import wildcard from plain text",
        tags=["wildcards"],
    )
    def import_wildcard_txt(name: str,
                            body: WildcardImportRequest) -> WildcardResponse:
        """★ v2.6 — テキスト形式（1行1値）から Wildcard をインポートする。"""
        wm = _get_wm()
        wf = wm.import_txt(name, body.text, description=body.description)
        return _wf_to_response(wf, include_entries=True)

    # ══════════════════════════════════════════════════════════════
    # v2.6 メトリクス（/metrics）
    # ══════════════════════════════════════════════════════════════

    @app.get(
        "/metrics",
        response_model=MetricsResponse,
        summary="Get server metrics",
        tags=["metrics"],
    )
    def get_metrics() -> MetricsResponse:
        """
        ★ v2.6 — サーバーのパフォーマンスメトリクスを返す。

        compile_count: 起動後のコンパイル実行回数
        avg_compile_ms: 平均コンパイル時間（ms）
        cache_hit_rate: キャッシュヒット率
        error_count: エラー発生回数
        """
        import time as _time
        uptime = _time.time() - _start_time if _start_time else 0.0
        avg_ms = (_compile_ms_total / _compile_count
                  if _compile_count > 0 else 0.0)
        ctx = get_context()
        wm_stats = ctx.wildcard_manager.statistics()
        dict_stats = ctx.dictionary_manager.statistics()
        try:
            cache_stats = ctx.cache_manager.statistics()
            hits   = cache_stats.get("hits", 0)
            misses = cache_stats.get("misses", 0)
            total  = hits + misses
            hit_rate = (hits / total) if total > 0 else 0.0
        except Exception:
            hit_rate = 0.0

        return MetricsResponse(
            uptime_seconds=round(uptime, 1),
            compile_count=_compile_count,
            avg_compile_ms=round(avg_ms, 1),
            cache_hit_rate=round(hit_rate, 3),
            endpoint_calls=dict(_endpoint_calls),
            error_count=_error_count,
            wildcard_count=wm_stats.get("wildcard_count", 0),
            dictionary_keys=dict_stats.get("total_keys", 0),
        )

    @app.get(
        "/metrics/prometheus",
        summary="Get metrics in Prometheus text format",
        tags=["metrics"],
        response_class=None,
    )
    def get_metrics_prometheus():
        """★ v2.6 — Prometheus テキスト形式でメトリクスを返す。"""
        from fastapi.responses import PlainTextResponse
        import time as _time
        uptime = _time.time() - _start_time if _start_time else 0.0
        lines = [
            "# HELP fps_uptime_seconds Server uptime in seconds",
            "# TYPE fps_uptime_seconds gauge",
            f"fps_uptime_seconds {uptime:.1f}",
            "# HELP fps_compile_total Total compile requests",
            "# TYPE fps_compile_total counter",
            f"fps_compile_total {_compile_count}",
            "# HELP fps_error_total Total errors",
            "# TYPE fps_error_total counter",
            f"fps_error_total {_error_count}",
        ]
        return PlainTextResponse("
".join(lines) + "
")


    # ══════════════════════════════════════════════════════════════
    # v2.5 LoRA 分析（/lora）
    # ══════════════════════════════════════════════════════════════

    def _ai(key: str):
        """ai_manager から指定モジュールを取得する"""
        return get_context().ai_manager[key]

    @app.post(
        "/lora/analyze",
        response_model=LoraAnalyzeResponse,
        summary="Analyze a LoRA file and extract tag candidates",
        tags=["lora"],
    )
    def lora_analyze(body: LoraAnalyzeRequest) -> LoraAnalyzeResponse:
        """
        ★ v2.5 — LoRA ファイルのメタデータを解析してタグ候補を返す。

        file_path: SafeTensors ファイルのフルパス（サーバー上）
        metadata:  CivitAI 等から取得したメタデータ辞書（file_path 不要）

        register_to_dict=true の場合、信頼度 0.5 以上のタグを
        ユーザー辞書に自動登録する。
        """
        analyzer = _ai("lora")
        if body.metadata:
            info = analyzer.analyze_from_metadata(body.metadata, body.file_name)
        elif body.file_path:
            info = analyzer.analyze(body.file_path)
        else:
            raise HTTPException(status_code=400,
                                detail="file_path または metadata を指定してください")

        registered = 0
        if body.register_to_dict and info.success:
            ctx = get_context()
            registered = analyzer.register_to_dictionary(
                info, ctx.dictionary_manager,
                category=body.category,
            )

        return LoraAnalyzeResponse(
            file_name=info.file_name,
            model_name=info.model_name,
            base_model=info.base_model,
            description=info.description,
            trigger_words=info.trigger_words,
            training_tags=info.training_tags,
            total_tags=info.total_tags,
            tag_candidates=[
                LoraTagCandidateItem(
                    tag=c.tag, source=c.source,
                    confidence=c.confidence,
                    category=c.category,
                    weight=c.weight,
                ) for c in info.tag_candidates
            ],
            registered=registered,
            error=info.error,
            success=info.success,
        )

    @app.get(
        "/lora/list",
        summary="List analyzed LoRA files",
        tags=["lora"],
    )
    def lora_list(
        lora_dir: str = Query(
            default="",
            description="スキャンするディレクトリ（省略時はデフォルト LoRA パス）",
        )
    ) -> dict:
        """
        ★ v2.5 — 指定ディレクトリの .safetensors ファイル一覧を返す。
        実際の分析は POST /lora/analyze で行う。
        """
        from pathlib import Path
        scan_dir = Path(lora_dir) if lora_dir else Path("models/loras")
        if not scan_dir.exists():
            return {"files": [], "total": 0, "dir": str(scan_dir),
                    "error": "ディレクトリが見つかりません"}
        files = [
            {"name": f.name, "size_mb": round(f.stat().st_size / 1024 / 1024, 1),
             "path": str(f)}
            for f in sorted(scan_dir.glob("*.safetensors"))
        ]
        return {"files": files, "total": len(files), "dir": str(scan_dir)}

    # ══════════════════════════════════════════════════════════════
    # v2.5 AI タグ提案（/ai）
    # ══════════════════════════════════════════════════════════════

    @app.get(
        "/ai/status",
        response_model=AiStatusResponse,
        summary="Get AI feature availability",
        tags=["ai"],
    )
    def ai_status() -> AiStatusResponse:
        """
        ★ v2.5 — 各 AI タガーの利用可能状態を返す。
        外部タガーが起動していない場合は dictionary フォールバックが利用される。
        """
        from ai.tagger_bridge import TaggerModel  # type: ignore
        tagger = _ai("tagger")
        available = tagger.available_models()
        return AiStatusResponse(
            available_models=available,
            wd14_available="wd14" in available,
            joycaption_available="joycaption" in available,
            florence2_available="florence2" in available,
            dictionary_available=True,
        )

    @app.post(
        "/ai/tag",
        response_model=AiTagResponse,
        summary="Get AI tag suggestions",
        tags=["ai"],
    )
    def ai_tag(body: AiTagRequest) -> AiTagResponse:
        """
        ★ v2.5 — AI タグ提案を返す。

        image_url を指定すると外部タガー（WD14等）でタグ付けを行う。
        image_url を省略すると current_tags から辞書ベースで提案する。
        外部タガーが利用不可の場合は自動的に辞書フォールバックに切り替わる。
        """
        from ai.tagger_bridge import TaggerModel  # type: ignore
        tagger = _ai("tagger")

        try:
            model = TaggerModel(body.model)
        except ValueError:
            model = TaggerModel.DICTIONARY

        if body.image_url:
            result = tagger.tag_image(body.image_url, model=model,
                                      threshold=body.threshold)
        else:
            result = tagger.suggest_from_context(body.current_tags, n=body.n)

        return AiTagResponse(
            model=result.model,
            source=result.source,
            tags=[AiTagItem(tag=t["tag"], score=t.get("score", 0.0))
                  for t in result.tags[:body.n]],
            top_tags=result.top_tags(n=body.n, threshold=body.threshold),
            error=result.error,
            success=result.success,
        )

    @app.post(
        "/ai/negative-learn",
        response_model=NegativeLearnResponse,
        summary="Learn negative tags from history",
        tags=["ai"],
    )
    def ai_negative_learn(
        limit: int = Query(default=200, ge=10, le=1000),
    ) -> NegativeLearnResponse:
        """
        ★ v2.5 — 変換履歴からネガティブタグパターンを学習する。

        学習内容:
          1. ネガティブとして頻繁に使われているタグ
          2. スコアが低い履歴の pos タグ（避けるべきタグ候補）
        """
        ctx = get_context()
        learner = _ai("negative")
        entries = ctx.history_manager.list_entries(limit=limit)
        result = learner.learn(entries)
        return NegativeLearnResponse(**result)

    @app.get(
        "/ai/negative-suggest",
        response_model=NegativeSuggestResponse,
        summary="Get negative tag suggestions",
        tags=["ai"],
    )
    def ai_negative_suggest(
        n: int = Query(default=20, ge=1, le=50),
        pos_tags: str | None = Query(
            default=None,
            description="現在の pos タグ（カンマ区切り、含まれるものは除外）",
        ),
    ) -> NegativeSuggestResponse:
        """
        ★ v2.5 — 学習済みデータからネガティブタグ推奨リストを返す。
        POST /ai/negative-learn を先に実行してください。
        """
        learner = _ai("negative")
        if pos_tags:
            current = [t.strip() for t in pos_tags.split(",") if t.strip()]
            suggestions = learner.suggest_negative_for_prompt(current, n=n)
        else:
            suggestions = learner.recommend_negative(n=n)
        return NegativeSuggestResponse(
            suggestions=[
                NegativeTagItem(
                    tag=e.tag, neg_count=e.neg_count,
                    avoid_count=e.avoid_count, priority=round(e.priority, 1),
                ) for e in suggestions
            ],
            total=len(suggestions),
        )

    # ══════════════════════════════════════════════════════════════
    # v2.5 一貫性チェック（/consistency）
    # ══════════════════════════════════════════════════════════════

    @app.post(
        "/consistency/check",
        response_model=ConsistencyCheckResponse,
        summary="Check style consistency across multiple prompts",
        tags=["consistency"],
    )
    def consistency_check(body: ConsistencyCheckRequest) -> ConsistencyCheckResponse:
        """
        ★ v2.5 — 複数プロンプトのスタイル一貫性を分析する。

        同一キャラクター・スタイルで複数枚生成する場合に使用。
        目の色・髪の色・体型などが矛盾していないか検出する。

        prompts: 2〜20件のプロンプトリスト
        labels:  各プロンプトのラベル（省略可）

        戻り値:
          overall_score:     0〜100（高いほど一貫性が高い）
          inconsistent_tags: 矛盾するタグ（例: blue_eyes と green_eyes が混在）
          recommendations:   改善提案
        """
        checker = _ai("consistency")
        result = checker.check(body.prompts, labels=body.labels or None)
        return ConsistencyCheckResponse(
            overall_score=result.overall_score,
            category_scores=result.category_scores,
            common_tags=result.common_tags,
            inconsistent_tags=result.inconsistent_tags,
            missing_tags=result.missing_tags[:20],
            recommendations=result.recommendations,
            detail=result.detail,
        )


    # ══════════════════════════════════════════════════════════════
    # v2.4 バッチ処理（/batch）
    # ══════════════════════════════════════════════════════════════

    def _get_bm():
        """BatchManager を CliContext 経由で取得する"""
        return get_context().batch_manager

    def _get_pvm():
        """PresetVersionManager を CliContext 経由で取得する"""
        return get_context().preset_version_manager

    @app.post(
        "/batch/compile",
        response_model=BatchResultResponse,
        summary="Batch compile prompts",
        tags=["batch"],
    )
    def batch_compile(body: BatchCompileRequest) -> BatchResultResponse:
        """
        ★ v2.4 — 複数プロンプトを一括コンパイルする（最大50件）。

        apply_profile=true の場合、UserProfile を各プロンプトに適用する。
        同期処理のため、件数が多いほどレスポンスに時間がかかる。
        """
        bm = _get_bm()
        apply_fn = None
        if body.apply_profile:
            try:
                upm = _get_upm()
                if upm:
                    apply_fn = upm.apply_profile
            except Exception:
                pass
        try:
            result = bm.compile_batch(body.prompts, apply_profile_fn=apply_fn)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return BatchResultResponse(
            job_id=result.job_id, mode=result.mode,
            total=result.total, succeeded=result.succeeded, failed=result.failed,
            avg_score=round(result.avg_score, 1),
            avg_tag_count=round(result.avg_tag_count, 1),
            total_elapsed_ms=round(result.total_elapsed_ms, 1),
            started_at=result.started_at, finished_at=result.finished_at,
            items=[BatchItemResponse(**i.to_dict()) for i in result.items],
        )

    @app.post(
        "/batch/optimize",
        response_model=BatchResultResponse,
        summary="Batch optimize prompts",
        tags=["batch"],
    )
    def batch_optimize(body: BatchOptimizeRequest) -> BatchResultResponse:
        """
        ★ v2.4 — 複数プロンプトを一括分析する（最大50件）。
        各プロンプトの品質スコアと問題点を返す。
        """
        bm = _get_bm()
        try:
            result = bm.optimize_batch(body.prompts)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return BatchResultResponse(
            job_id=result.job_id, mode=result.mode,
            total=result.total, succeeded=result.succeeded, failed=result.failed,
            avg_score=round(result.avg_score, 1),
            avg_tag_count=round(result.avg_tag_count, 1),
            total_elapsed_ms=round(result.total_elapsed_ms, 1),
            started_at=result.started_at, finished_at=result.finished_at,
            items=[BatchItemResponse(**i.to_dict()) for i in result.items],
        )

    @app.get(
        "/batch/status",
        summary="Get last batch job result summary",
        tags=["batch"],
    )
    def batch_status() -> dict:
        """★ v2.4 — 最後のバッチジョブのサマリーを返す。"""
        bm = _get_bm()
        r = bm.last_result
        if r is None:
            return {"status": "no_job", "message": "バッチジョブ未実行"}
        return {
            "job_id": r.job_id, "mode": r.mode,
            "total": r.total, "succeeded": r.succeeded, "failed": r.failed,
            "avg_score": round(r.avg_score, 1),
            "total_elapsed_ms": round(r.total_elapsed_ms, 1),
            "finished_at": r.finished_at,
        }

    # ══════════════════════════════════════════════════════════════
    # v2.4 タグ補完（/dictionary/autocomplete, /dictionary/suggest）
    # ══════════════════════════════════════════════════════════════

    @app.get(
        "/dictionary/autocomplete",
        response_model=AutocompleteResponse,
        summary="Tag autocomplete",
        tags=["dictionary"],
    )
    def autocomplete_tags(
        q: str = Query(..., min_length=1, description="検索プレフィックス"),
        limit: int = Query(default=15, ge=1, le=50),
    ) -> AutocompleteResponse:
        """
        ★ v2.4 — タグ名のプレフィックス補完候補を返す。
        Web UI のエディタリアルタイム補完に使用する。
        """
        ctx = get_context()
        ql = q.strip().lower()
        try:
            with ctx.dictionary_manager._lock:
                index = dict(ctx.dictionary_manager._index)
            candidates = [
                e for key, e in index.items()
                if key.startswith(ql) or e.resolved.lower().startswith(ql)
            ]
            # 完全一致 → プレフィックス一致 → 部分一致の順でソート
            candidates.sort(key=lambda e: (
                0 if e.key == ql else
                1 if e.key.startswith(ql) else 2
            ))
            candidates = candidates[:limit]
        except Exception:
            candidates = []

        return AutocompleteResponse(
            query=q,
            items=[AutocompleteItem(
                key=e.key, resolved=e.resolved,
                category=e.category, weight=e.weight,
            ) for e in candidates],
            total=len(candidates),
        )

    @app.get(
        "/dictionary/suggest",
        response_model=SuggestResponse,
        summary="Suggest next tags based on current tags",
        tags=["dictionary"],
    )
    def suggest_tags(
        tags: str = Query(..., description="現在のタグ（カンマ区切り）"),
        n: int = Query(default=10, ge=1, le=30),
    ) -> SuggestResponse:
        """
        ★ v2.4 — 現在のタグリストから、次に追加すべきタグを提案する。

        UserProfile の共起データ + 辞書カテゴリ補完を使って提案する。
        """
        current = [t.strip().lower() for t in tags.split(",") if t.strip()]
        ctx = get_context()
        suggestions: list[AutocompleteItem] = []

        # ① プロファイル推奨タグから現在未使用のものを提案
        try:
            upm = _get_upm()
            if upm:
                recs = upm.recommend(30)
                for e in recs:
                    if e.tag not in current and len(suggestions) < n:
                        result = ctx.dictionary_manager.lookup(e.tag)
                        suggestions.append(AutocompleteItem(
                            key=e.tag,
                            resolved=result.resolved or e.tag,
                            category=result.category or "",
                            weight=e.avg_weight,
                        ))
        except Exception:
            pass

        # ② 不足分は辞書の関連カテゴリから補完
        if len(suggestions) < n:
            try:
                for tag in current[:3]:
                    result = ctx.dictionary_manager.lookup(tag)
                    if result.found and result.category:
                        entries = ctx.dictionary_manager.search_by_category(
                            result.category, limit=n
                        )
                        for e in entries:
                            if e.key not in current and not any(
                                s.key == e.key for s in suggestions
                            ) and len(suggestions) < n:
                                suggestions.append(AutocompleteItem(
                                    key=e.key, resolved=e.resolved,
                                    category=e.category, weight=e.weight,
                                ))
            except Exception:
                pass

        return SuggestResponse(
            current_tags=current,
            suggestions=suggestions[:n],
            total=len(suggestions[:n]),
        )

    # ══════════════════════════════════════════════════════════════
    # v2.4 プロファイル エクスポート/インポート
    # ══════════════════════════════════════════════════════════════

    @app.get(
        "/profile/export",
        response_model=ProfileExportResponse,
        summary="Export user profile as JSON",
        tags=["profile"],
    )
    def export_profile() -> ProfileExportResponse:
        """
        ★ v2.4 — ユーザープロファイルを JSON 形式でエクスポートする。
        別環境へのデータ移行や定期バックアップに使用する。
        """
        from datetime import datetime as _dt
        upm = _get_upm()
        if upm is None:
            raise HTTPException(status_code=503, detail="UserProfileManager unavailable")
        profile = upm.get_profile()
        stats   = upm.statistics()
        data = profile.to_dict()
        return ProfileExportResponse(
            version="2.9.0",
            exported_at=_dt.now().isoformat(),
            tag_frequency_count=stats.get("tag_frequency_count", 0),
            tag_weight_count=stats.get("tag_weight_count", 0),
            style_rule_count=stats.get("style_rule_count", 0),
            data=data,
        )

    @app.post(
        "/profile/import",
        response_model=ProfileImportResponse,
        summary="Import user profile from JSON",
        tags=["profile"],
    )
    def import_profile(body: ProfileImportRequest) -> ProfileImportResponse:
        """
        ★ v2.4 — JSON からユーザープロファイルをインポートする。

        merge=true の場合は既存データにマージ（頻度数は加算）。
        merge=false（デフォルト）の場合は既存データを上書き。
        """
        from user.models import TagWeight, StyleRule, TagFrequencyEntry  # type: ignore[import]
        from datetime import datetime as _dt
        upm = _get_upm()
        if upm is None:
            raise HTTPException(status_code=503, detail="UserProfileManager unavailable")
        data = body.data
        freq_count = weight_count = rule_count = 0
        try:
            if not body.merge:
                upm.reset()

            # tag_frequencies インポート
            for tag, e in data.get("tag_frequencies", {}).items():
                try:
                    freq = upm.get_profile().tag_frequencies.get(tag)
                    if freq and body.merge:
                        freq.count += e.get("count", 0)
                        freq.total_weight += e.get("avg_weight", 1.0) * e.get("count", 0)
                    else:
                        from user.models import TagFrequencyEntry as TFE  # type: ignore[import]
                        upm.get_profile().tag_frequencies[tag] = TFE(
                            tag=tag,
                            count=e.get("count", 0),
                            total_weight=e.get("avg_weight", 1.0) * e.get("count", 0),
                            last_used=_dt.fromisoformat(e.get("last_used", _dt.now().isoformat())),
                        )
                    freq_count += 1
                except Exception:
                    pass

            # tag_weights インポート
            for tag, w in data.get("tag_weights", {}).items():
                try:
                    upm.set_tag_weight(tag, w.get("weight", 1.0), w.get("reason", "imported"))
                    weight_count += 1
                except Exception:
                    pass

            # style_rules インポート
            for r in data.get("style_rules", []):
                try:
                    from user.models import StyleRule as SR  # type: ignore[import]
                    upm.add_style_rule(SR(
                        id=r["id"], name=r["name"],
                        always_include=r.get("always_include", []),
                        always_exclude=r.get("always_exclude", []),
                        enabled=r.get("enabled", True),
                    ))
                    rule_count += 1
                except Exception:
                    pass

            upm.save()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Import failed: {e}")

        return ProfileImportResponse(
            imported_frequencies=freq_count,
            imported_weights=weight_count,
            imported_rules=rule_count,
            merged=body.merge,
        )

    # ══════════════════════════════════════════════════════════════
    # v2.4 プリセットバージョン管理
    # ══════════════════════════════════════════════════════════════

    @app.get(
        "/presets/{preset_id}/versions",
        response_model=PresetVersionsResponse,
        summary="List preset versions",
        tags=["presets"],
    )
    def list_preset_versions(preset_id: str) -> PresetVersionsResponse:
        """
        ★ v2.4 — プリセットのバージョン履歴一覧を返す（新しい順）。
        最大 20 件まで保持。
        """
        pvm = _get_pvm()
        versions = pvm.list_versions(preset_id)
        return PresetVersionsResponse(
            preset_id=preset_id,
            versions=[PresetVersionItem(**v.to_dict()) for v in versions],
            total=len(versions),
        )

    @app.post(
        "/presets/{preset_id}/versions/{version_id}/restore",
        response_model=RestoreVersionResponse,
        summary="Restore a preset to a specific version",
        tags=["presets"],
    )
    def restore_preset_version(preset_id: str, version_id: str) -> RestoreVersionResponse:
        """
        ★ v2.4 — 指定バージョンにプリセットをリストアする。
        リストア前に現在の状態を自動スナップショット保存する。
        """
        ctx = get_context()
        pvm = _get_pvm()
        try:
            preset = pvm.restore(ctx.preset_manager, preset_id, version_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return RestoreVersionResponse(
            preset_id=preset_id,
            version_id=version_id,
            restored=True,
            tag_count=len(preset.tags),
        )

    @app.delete(
        "/presets/{preset_id}/versions/{version_id}",
        summary="Delete a specific version",
        tags=["presets"],
    )
    def delete_preset_version(preset_id: str, version_id: str) -> dict:
        """★ v2.4 — 指定バージョンを削除する。"""
        pvm = _get_pvm()
        deleted = pvm.delete_version(preset_id, version_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Version not found")
        return {"preset_id": preset_id, "version_id": version_id, "deleted": True}


    # ══════════════════════════════════════════════════════════════
    # v2.3 ユーザー管理（/users）
    # ══════════════════════════════════════════════════════════════

    def _get_um():
        """UserManager を CliContext 経由で取得する"""
        return get_context().user_manager

    def _get_sm():
        """ShareManager を CliContext 経由で取得する"""
        return get_context().share_manager

    def _get_current_user(x_api_key: str | None = None) -> "Any":
        """
        X-Api-Key ヘッダーからユーザーを取得する。
        未認証の場合は anonymous ユーザーを返す。
        """
        if not x_api_key:
            return None
        return _get_um().verify_api_key(x_api_key)

    @app.post(
        "/users/register",
        response_model=RegisterResponse,
        status_code=201,
        summary="Register a new user",
        tags=["users"],
    )
    def register_user(body: RegisterRequest) -> RegisterResponse:
        """
        ★ v2.3 — 新規ユーザーを登録して API キーを発行する。

        API キーは **このレスポンスにのみ含まれます**。
        再表示はできないため、安全な場所に保存してください。

        以降のリクエストでは `X-Api-Key: fps_xxxxx` ヘッダーを付けてください。
        """
        um = _get_um()
        try:
            user, raw_key = um.register(
                username=body.username,
                display_name=body.display_name,
                expires_days=body.expires_days,
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        return RegisterResponse(
            user=UserInfoResponse(**user.to_dict()),
            api_key=raw_key,
        )

    @app.get(
        "/users/me",
        response_model=UserInfoResponse,
        summary="Get current user info",
        tags=["users"],
    )
    def get_me(x_api_key: str | None = None) -> UserInfoResponse:
        """
        ★ v2.3 — 現在の認証ユーザー情報を返す。

        ヘッダー: `X-Api-Key: fps_xxxxx`
        未認証の場合は 401。
        """
        user = _get_current_user(x_api_key)
        if user is None:
            raise HTTPException(status_code=401, detail="API キーが必要です")
        return UserInfoResponse(**user.to_dict())

    @app.get(
        "/users/{user_id}",
        response_model=UserInfoResponse,
        summary="Get user info by ID",
        tags=["users"],
    )
    def get_user(user_id: str) -> UserInfoResponse:
        """★ v2.3 — ユーザーID でユーザー情報を取得する。"""
        um = _get_um()
        user = um.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
        return UserInfoResponse(**user.to_dict())

    @app.post(
        "/users/me/api-keys",
        response_model=CreateApiKeyResponse,
        status_code=201,
        summary="Create additional API key",
        tags=["users"],
    )
    def create_api_key(
        body: CreateApiKeyRequest,
        x_api_key: str | None = None,
    ) -> CreateApiKeyResponse:
        """★ v2.3 — 追加の API キーを発行する。認証必須。"""
        user = _get_current_user(x_api_key)
        if user is None:
            raise HTTPException(status_code=401, detail="API キーが必要です")
        um = _get_um()
        raw_key, key_info = um.create_api_key(
            user.user_id, label=body.label, expires_days=body.expires_days
        )
        return CreateApiKeyResponse(
            api_key=raw_key,
            key_info=ApiKeyResponse(
                key_id=key_info.key_id, label=key_info.label,
                created_at=key_info.created_at, last_used=key_info.last_used,
                expires_at=key_info.expires_at,
            ),
        )

    @app.delete(
        "/users/me/api-keys/{key_id}",
        summary="Revoke an API key",
        tags=["users"],
    )
    def revoke_api_key(key_id: str, x_api_key: str | None = None) -> dict:
        """★ v2.3 — API キーを無効化する。認証必須。"""
        user = _get_current_user(x_api_key)
        if user is None:
            raise HTTPException(status_code=401, detail="API キーが必要です")
        revoked = _get_um().revoke_api_key(key_id, user.user_id)
        if not revoked:
            raise HTTPException(status_code=404, detail="Key not found")
        return {"key_id": key_id, "revoked": True}

    # ══════════════════════════════════════════════════════════════
    # v2.3 プリセット共有（/presets/{id}/share, /shared）
    # ══════════════════════════════════════════════════════════════

    @app.post(
        "/presets/{preset_id}/share",
        response_model=ShareTokenResponse,
        status_code=201,
        summary="Share a preset",
        tags=["presets", "sharing"],
    )
    def share_preset(
        preset_id: str,
        body: SharePresetRequest,
        x_api_key: str | None = None,
    ) -> ShareTokenResponse:
        """
        ★ v2.3 — プリセットの共有リンクを発行する。

        認証なしでも共有可能（anonymous ユーザーとして登録される）。
        返却される share_url を他のユーザーに共有してください。
        """
        ctx = get_context()
        if not ctx.preset_manager.exists(preset_id):
            raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
        preset = ctx.preset_manager.get(preset_id)
        preset_data = {
            "id":      preset.id,
            "name":    preset.name,
            "tags":    [{"tag": t.tag, "category": t.category, "weight": t.weight}
                        for t in preset.tags],
            "negative_tags": [{"tag": t.tag, "category": t.category, "weight": t.weight}
                               for t in preset.negative_tags],
            "description": preset.description,
        }
        user = _get_current_user(x_api_key)
        user_id = user.user_id if user else _get_um().anonymous_user_id

        sm = _get_sm()
        share = sm.create_share(
            user_id=user_id, preset_id=preset_id,
            preset_data=preset_data,
            title=body.title or preset.name,
            description=body.description,
            expires_days=body.expires_days,
        )
        share_url = f"/shared/presets/{share.token}"
        return ShareTokenResponse(
            token=share.token, preset_id=share.preset_id,
            title=share.title, description=share.description,
            share_url=share_url, created_at=share.created_at,
            expires_at=share.expires_at, view_count=0,
        )

    @app.get(
        "/shared/presets/{token}",
        response_model=SharedPresetResponse,
        summary="Get shared preset",
        tags=["sharing"],
    )
    def get_shared_preset(token: str) -> SharedPresetResponse:
        """
        ★ v2.3 — 共有トークンからプリセット情報を取得する。

        認証不要。閲覧のたびに view_count が増加する。
        有効期限切れや無効化済みトークンは 404 を返す。
        """
        sm = _get_sm()
        share = sm.get_share(token)
        if share is None:
            raise HTTPException(status_code=404, detail="共有リンクが無効か期限切れです")
        return SharedPresetResponse(
            token=share.token, preset_id=share.preset_id,
            title=share.title, description=share.description,
            created_at=share.created_at, view_count=share.view_count,
            preset_data=share.preset_data,
        )

    @app.get(
        "/shared/presets",
        summary="List my shared presets",
        tags=["sharing"],
    )
    def list_my_shares(x_api_key: str | None = None) -> dict:
        """★ v2.3 — 自分が発行した共有リンク一覧を返す。認証必須。"""
        user = _get_current_user(x_api_key)
        if user is None:
            raise HTTPException(status_code=401, detail="API キーが必要です")
        sm = _get_sm()
        shares = sm.list_user_shares(user.user_id)
        return {"shares": [s.to_dict() for s in shares], "total": len(shares)}

    @app.delete(
        "/shared/presets/{token}",
        response_model=DeleteShareResponse,
        summary="Delete a shared preset link",
        tags=["sharing"],
    )
    def delete_share(token: str, x_api_key: str | None = None) -> DeleteShareResponse:
        """★ v2.3 — 共有リンクを無効化する。発行者のみ可能。"""
        user = _get_current_user(x_api_key)
        if user is None:
            raise HTTPException(status_code=401, detail="API キーが必要です")
        sm = _get_sm()
        deleted = sm.delete_share(token, user.user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="共有リンクが見つかりません")
        return DeleteShareResponse(token=token, deleted=True)

    # ══════════════════════════════════════════════════════════════
    # v2.3 コミュニティ統計（/community）
    # ══════════════════════════════════════════════════════════════

    @app.get(
        "/community/tags",
        response_model=CommunityTagsResponse,
        summary="Get community tag statistics",
        tags=["community"],
    )
    def get_community_tags(
        limit: int = Query(default=50, ge=1, le=200),
        category: str | None = Query(default=None),
        min_count: int = Query(default=1, ge=1),
    ) -> CommunityTagsResponse:
        """
        ★ v2.3 — コミュニティのタグ使用統計を返す（匿名集計）。

        POST /community/contribute で投稿されたデータの集計値。
        個人を特定できる情報は含まない。
        """
        sm = _get_sm()
        tags = sm.get_community_tags(limit=limit, category=category, min_count=min_count)
        stats = sm.community_stats()
        return CommunityTagsResponse(
            tags=[CommunityTagItem(
                tag=t.tag, total_count=t.total_count,
                avg_score=t.avg_score, category=t.category,
            ) for t in tags],
            total=len(tags),
            stats=stats,
        )

    @app.post(
        "/community/contribute",
        response_model=ContributeResponse,
        summary="Contribute tag data to community stats",
        tags=["community"],
    )
    def contribute_to_community(body: ContributeRequest) -> ContributeResponse:
        """
        ★ v2.3 — タグ使用データをコミュニティ統計に投稿する（任意・匿名）。

        個人を特定できる情報は送信しないでください。
        タグ名とスコアのみが集計に使われます。
        """
        sm = _get_sm()
        n = sm.contribute_tags(tags=body.tags, avg_score=body.avg_score)
        return ContributeResponse(
            contributed=n,
            message=f"{n}件のタグデータをコミュニティ統計に追加しました",
        )


    # ══════════════════════════════════════════════════════════════
    # v2.2 高度タグ検索
    # ══════════════════════════════════════════════════════════════

    @app.get(
        "/dictionary/related/{tag}",
        response_model=RelatedTagsResponse,
        summary="Get related tags",
        tags=["dictionary"],
    )
    def get_related_tags(
        tag: str,
        n: int = Query(default=20, ge=1, le=50),
    ) -> RelatedTagsResponse:
        """
        ★ v2.2 — 指定タグと関連性の高いタグ一覧を返す。

        UserProfile の tag_frequencies から共起回数を算出する。
        学習データがない場合は辞書のカテゴリ一致で代替する。
        """
        ctx = get_context()
        upm = _get_upm()
        related: list[RelatedTagItem] = []

        # ① プロファイル学習データから共起スコアを計算
        if upm:
            try:
                freqs = upm.get_profile().tag_frequencies
                target = freqs.get(tag.lower())
                if target:
                    all_tags = list(freqs.values())
                    total = max(target.count, 1)
                    candidates = [
                        RelatedTagItem(
                            tag=e.tag,
                            score=round(min(e.count / total, 1.0), 3),
                            co_count=e.count,
                        )
                        for e in all_tags
                        if e.tag != tag.lower() and e.count >= 2
                    ]
                    candidates.sort(key=lambda x: -x.score)
                    related = candidates[:n]
            except Exception:
                pass

        # ② フォールバック: 辞書カテゴリ一致で代替
        if not related:
            try:
                dm = ctx.dictionary_manager
                result = dm.lookup(tag)
                if result.found and result.category:
                    entries = dm.search_by_category(result.category, limit=n + 1)
                    related = [
                        RelatedTagItem(
                            tag=e.key, score=0.5,
                            category=e.category,
                        )
                        for e in entries if e.key != tag
                    ][:n]
            except Exception:
                pass

        return RelatedTagsResponse(tag=tag, related=related, total=len(related))

    # ── v2.2 History 全文検索強化 ──────────────────────────────────

    @app.get(
        "/history/search",
        response_model=HistorySearchResponse,
        summary="Full-text search history",
        tags=["history"],
    )
    def search_history(
        q: str | None = Query(default=None, description="プロンプト全文検索"),
        tag: str | None = Query(default=None, description="特定タグを含む履歴"),
        date_from: str | None = Query(default=None, description="開始日 YYYY-MM-DD"),
        date_to:   str | None = Query(default=None, description="終了日 YYYY-MM-DD"),
        score_min: float = Query(default=0.0, ge=0.0, le=100.0),
        score_max: float = Query(default=100.0, ge=0.0, le=100.0),
        favorite_only: bool = Query(default=False),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> HistorySearchResponse:
        """
        ★ v2.2 — 複合フィルタで履歴を検索する。

        - q:           プロンプト全文（部分一致）
        - tag:         特定タグ（カンマ区切りで複数指定可）
        - date_from/to: 日付範囲
        - score_min/max: スコア範囲
        - favorite_only: お気に入りのみ
        """
        ctx = get_context()
        all_entries = ctx.history_manager.list_entries(limit=1000)
        results = all_entries

        if q:
            ql = q.lower()
            results = [e for e in results
                       if ql in e.input_prompt.lower() or ql in e.output_prompt.lower()]

        if tag:
            tags_filter = {t.strip().lower() for t in tag.split(",") if t.strip()}
            results = [e for e in results
                       if any(tf in e.output_prompt.lower() for tf in tags_filter)]

        if date_from:
            results = [e for e in results
                       if hasattr(e, "created_at_str") and e.created_at_str >= date_from]

        if date_to:
            results = [e for e in results
                       if hasattr(e, "created_at_str") and e.created_at_str[:10] <= date_to]

        results = [e for e in results if score_min <= e.overall_score <= score_max]

        if favorite_only:
            results = [e for e in results if e.favorite]

        results = results[:limit]

        return HistorySearchResponse(
            entries=[
                HistoryEntryResponse(
                    id=e.id,
                    input_prompt=e.input_prompt,
                    output_prompt=e.output_prompt,
                    tag_count=e.tag_count,
                    overall_score=e.overall_score,
                    created_at=e.created_at_str,
                    favorite=e.favorite,
                    label=e.label,
                )
                for e in results
            ],
            total=len(results),
            query=q or "",
        )

    # ── v2.2 プリセット v2（プロファイルから自動生成）─────────────

    @app.post(
        "/profile/save-as-preset",
        response_model=SaveAsPresetResponse,
        status_code=201,
        summary="Save profile recommendations as a preset",
        tags=["profile"],
    )
    def save_profile_as_preset(body: SaveAsPresetRequest) -> SaveAsPresetResponse:
        """
        ★ v2.2 — プロファイルの推奨タグをプリセットとして保存する。

        learn() を実行した後に呼ぶ。
        推奨タグ Top N + スタイルルール always_include を
        ユーザープリセットとして保存する。
        """
        ctx = get_context()
        upm = _get_upm()
        if upm is None:
            raise HTTPException(status_code=503, detail="UserProfileManager unavailable")
        try:
            preset = upm.save_as_preset(
                preset_manager=ctx.preset_manager,
                preset_id=body.preset_id,
                name=body.name,
                top_n=body.top_n,
                category=body.category,
                description=body.description,
            )
            return SaveAsPresetResponse(
                preset_id=preset.id,
                name=preset.name,
                tag_count=len(preset.tags),
                negative_tag_count=len(preset.negative_tags),
                category=body.category,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── v2.2 ストレージ統計 ───────────────────────────────────────

    @app.get(
        "/profile/storage",
        response_model=StorageStatsResponse,
        summary="Get profile storage stats",
        tags=["profile"],
    )
    def get_profile_storage() -> StorageStatsResponse:
        """
        ★ v2.2 — プロファイルストレージの統計を返す。
        storage="sqlite" の場合は SQLite、"json" の場合は profile.json を使用中。
        """
        upm = _get_upm()
        if upm is None:
            raise HTTPException(status_code=503, detail="UserProfileManager unavailable")
        s = upm.statistics()
        return StorageStatsResponse(
            storage=s.get("storage", "json"),
            tag_frequency_count=s.get("tag_frequency_count", 0),
            tag_weight_count=s.get("tag_weight_count", 0),
            style_rule_count=s.get("style_rule_count", 0),
            score_trend_count=s.get("score_trend_count", 0),
            db_path=s.get("db_path", ""),
        )


    # ══════════════════════════════════════════════════════════════
    # v1.9 WebSocket エンドポイント
    # ══════════════════════════════════════════════════════════════

    @app.websocket("/ws/pipeline")
    async def ws_pipeline(websocket: WebSocket) -> None:
        """
        ★ v1.9 WebSocket — コンパイル進捗リアルタイムストリーム。

        購読するイベント:
          pipeline.before_compile / pipeline.after_compile / pipeline.error
          stage.before_run / stage.after_run / stage.error
          optimizer.analyzed / pipeline.cache_hit

        接続直後に {"type": "ws.connected", "channel": "pipeline"} を送信する。

        使い方 (JavaScript):
            const ws = new WebSocket("ws://localhost:8420/ws/pipeline");
            ws.onmessage = e => console.log(JSON.parse(e.data));
        """
        await ws_manager.connect(websocket, "pipeline")
        try:
            await websocket.send_json({
                "type": "ws.connected",
                "channel": "pipeline",
                "msg": "Subscribed to pipeline events",
            })
            while True:
                # クライアントからのメッセージを待つ（ping/pong 兼用）
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, "pipeline")
        except Exception:
            ws_manager.disconnect(websocket, "pipeline")

    @app.websocket("/ws/history")
    async def ws_history(websocket: WebSocket) -> None:
        """
        ★ v1.9 WebSocket — 新規履歴エントリをリアルタイムプッシュ。

        購読するイベント:
          history.recorded — compile 時に新規エントリが追加されたとき
          history.deleted  — エントリが削除されたとき

        接続直後に最新5件の履歴スナップショットを送信する。

        使い方 (JavaScript):
            const ws = new WebSocket("ws://localhost:8420/ws/history");
            ws.onmessage = e => {
              const d = JSON.parse(e.data);
              if (d.type === "history.recorded") appendToList(d.data);
            };
        """
        await ws_manager.connect(websocket, "history")
        try:
            # 接続直後にスナップショット送信
            ctx = get_context()
            recent = ctx.history_manager.list_entries(limit=5)
            await websocket.send_json({
                "type": "ws.connected",
                "channel": "history",
                "snapshot": [
                    {
                        "id": e.id,
                        "input_prompt": e.input_prompt,
                        "output_prompt": e.output_prompt,
                        "score": e.overall_score,
                        "favorite": e.favorite,
                        "created_at": e.created_at_str,
                    }
                    for e in recent
                ],
            })
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, "history")
        except Exception:
            ws_manager.disconnect(websocket, "history")

    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket) -> None:
        """
        ★ v1.9 WebSocket — 全イベントのサブスクライブ（デバッグ・モニタリング用）。

        クライアントは接続後に JSON でフィルタを送信できる:
            {"filter": ["pipeline.", "stage."]}

        フィルタなし（デフォルト）では全イベントを受信する。

        使い方 (JavaScript):
            const ws = new WebSocket("ws://localhost:8420/ws/events");
            ws.send(JSON.stringify({filter: ["pipeline."]}));
            ws.onmessage = e => console.log(JSON.parse(e.data));
        """
        import asyncio as _asyncio
        await ws_manager.connect(websocket, "events")
        event_filter: list[str] = []
        try:
            await websocket.send_json({
                "type": "ws.connected",
                "channel": "events",
                "msg": "Subscribed to all events. Send {filter:[...]} to narrow down.",
            })

            async def receive_loop() -> None:
                nonlocal event_filter
                while True:
                    try:
                        raw = await websocket.receive_text()
                        if raw == "ping":
                            await websocket.send_json({"type": "pong"})
                        else:
                            msg = json_module.loads(raw)
                            if "filter" in msg:
                                event_filter = msg["filter"]
                                await websocket.send_json({
                                    "type": "ws.filter_set",
                                    "filter": event_filter,
                                })
                    except Exception:
                        break

            await receive_loop()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, "events")
        except Exception:
            ws_manager.disconnect(websocket, "events")

    @app.get(
        "/profile/settings",
        response_model=ProfileSettingsResponse,
        summary="Get profile settings",
        tags=["profile"],
    )
    def get_profile_settings() -> ProfileSettingsResponse:
        """
        ★ v2.1 — プロファイル設定を返す。

        auto_learn=true のとき、compile が auto_learn_interval 件ごとに
        自動で学習を実行する。
        apply_profile_default=true のとき、Web UI の apply_profile トグルが
        デフォルトで ON になる。
        """
        upm = _get_upm()
        s = upm.get_settings()
        return ProfileSettingsResponse(
            auto_learn=s.get("auto_learn", False),
            auto_learn_interval=s.get("auto_learn_interval", 10),
            apply_profile_default=s.get("apply_profile_default", False),
            recommendation_threshold=s.get("recommendation_threshold", 2),
            compile_count=_compile_count,
        )

    @app.put(
        "/profile/settings",
        response_model=ProfileSettingsResponse,
        summary="Update profile settings",
        tags=["profile"],
    )
    def update_profile_settings(body: ProfileSettingsUpdateRequest) -> ProfileSettingsResponse:
        """
        ★ v2.1 — プロファイル設定を更新する。None のフィールドは変更しない。
        """
        upm = _get_upm()
        current = upm.get_settings()
        patch = {k: v for k, v in body.model_dump().items() if v is not None}
        merged = {**current, **patch}
        saved = upm.save_settings(merged)
        return ProfileSettingsResponse(
            auto_learn=saved.get("auto_learn", False),
            auto_learn_interval=saved.get("auto_learn_interval", 10),
            apply_profile_default=saved.get("apply_profile_default", False),
            recommendation_threshold=saved.get("recommendation_threshold", 2),
            compile_count=_compile_count,
        )


    @app.get(
        "/ws/stats",
        summary="WebSocket connection stats",
        tags=["websocket"],
    )
    def ws_stats() -> dict:
        """現在の WebSocket 接続数を返す（デバッグ用）。"""
        return {
            "connections": ws_manager.stats(),
            "total": ws_manager.connection_count(),
        }


else:
    app = None  # type: ignore[assignment]
