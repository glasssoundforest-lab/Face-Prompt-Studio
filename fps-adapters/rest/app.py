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
)

if _FASTAPI_AVAILABLE:
    from cli.context import CliContext

    app = FastAPI(
        title="Face Prompt Studio API",
        description="REST API for prompt compilation, optimization, and management",
        version="2.3.0",
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
        ctx = get_context()
        setup_event_bridge(ctx.event_bus)

    _ctx: CliContext | None = None
    _compile_count: int = 0   # ★v2.1 compile 実行回数カウンター

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
            version="2.3.0",
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
            version="2.3.0",
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
