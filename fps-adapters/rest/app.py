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
  POST /presets/{preset_id}/apply プリセット適用
  GET  /history                   変換履歴一覧
  POST /validate                  辞書/ルール/プリセット検証

起動方法:
  uvicorn fps-adapters.rest.app:app --reload --port 8420
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parents[2]
_ADAPTERS = _ROOT / "fps-adapters"

if str(_ADAPTERS) not in sys.path:
    sys.path.insert(0, str(_ADAPTERS))

try:
    from fastapi import FastAPI, HTTPException, Query

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
    PresetListResponse,
    PresetSummary,
    QualityScoreResponse,
    RenderRequest,
    RenderResponse,
    SynonymsResponse,
    TemplateListResponse,
    TemplateSummaryResponse,
    TemplateVariableResponse,
    ValidationResponse,
)

if _FASTAPI_AVAILABLE:
    from cli.context import CliContext

    app = FastAPI(
        title="Face Prompt Studio API",
        description="REST API for prompt compilation, optimization, and management",
        version="0.9.0",
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

    _ctx: CliContext | None = None

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
            version="0.9.0",
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
    def compile_prompt(prompt: str, adapter: str | None = None) -> CompileResponse:
        ctx = get_context()
        result = ctx.pipeline_manager.compile(prompt)

        adapter_output = None
        if adapter:
            adapter_output = _convert_with_adapter(result, adapter)

        return CompileResponse(
            success=result.success,
            prompt=result.prompt,
            negative=result.negative,
            tag_count=result.tag_count,
            errors=result.errors,
            adapter_output=adapter_output,
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
                )
                for p in presets
            ]
        )

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

        # 内部インデックスから重複なしのエントリリストを構築
        with dm._lock:
            raw_index: dict = dict(dm._index)

        seen: set[str] = set()
        unique_entries = []
        for entry in raw_index.values():
            if entry.key not in seen:
                seen.add(entry.key)
                unique_entries.append(entry)

        # カテゴリフィルタ
        if category:
            unique_entries = [e for e in unique_entries if e.category == category]

        # テキスト検索（key / resolved に対して部分一致）
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
        """TemplateManager をシングルトンで取得する"""
        ctx = get_context()
        if not hasattr(ctx, "_template_manager") or ctx._template_manager is None:
            import sys
            tm_path = str(_ROOT / "fps-core")
            if tm_path not in sys.path:
                sys.path.insert(0, tm_path)
            from template.manager import TemplateManager  # type: ignore[import]
            tm_data = _ROOT / "fps-data" / "templates" / "system"
            ctx._template_manager = TemplateManager(system_dir=tm_data if tm_data.exists() else None)
            ctx._template_manager.load()
        return ctx._template_manager

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

else:
    app = None  # type: ignore[assignment]
