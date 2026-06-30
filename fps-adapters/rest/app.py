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
    CompileResponse,
    DictionaryLookupResponse,
    DictionaryStatsResponse,
    HealthResponse,
    HistoryEntryResponse,
    HistoryListResponse,
    OptimizationIssueResponse,
    OptimizeResponse,
    PresetListResponse,
    PresetSummary,
    QualityScoreResponse,
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
    def optimize_prompt(prompt: str) -> OptimizeResponse:
        ctx = get_context()
        pipeline_result = ctx.pipeline_manager.compile(prompt)
        opt_result = ctx.optimizer_manager.analyze_pipeline_result(pipeline_result)

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

else:
    app = None  # type: ignore[assignment]
