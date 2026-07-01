"""
fps-core/pipeline/manager.py — PipelineManager

Public API:
  - compile(prompt)   プロンプトをコンパイルして PipelineResult を返す
  - set_context(...)  コンテキストを設定する
  - enable_stage(name)  / disable_stage(name)  ステージ切替
  - statistics()      実行統計

キャッシュ:
  cache_manager を渡すと同一プロンプト + 同一コンテキストの
  再コンパイルをスキップしてキャッシュ結果を返す（CacheManager 連携）。
  キャッシュキーはプロンプト文字列 + 辞書/ルールのバージョン情報から
  生成され、辞書やルールが更新された場合は自動的にキャッシュミスになる。

パイプライン構成（10ステージ）:
  1  parser
  2  normalizer
  3  duplicate_cleaner
  4  blacklist
  5  whitelist
  6  categorizer
  7  rule_engine
  8  weight_engine
  9  optimizer
  10 exporter
"""

from __future__ import annotations

import copy
import logging
import threading
from typing import Any

from .models import PipelineResult, StageResult, StageStatus, TagEntry
from .stages import (
    BaseStage,
    BlacklistStage,
    CategorizerStage,
    DuplicateCleanerStage,
    ExporterStage,
    NormalizerStage,
    OptimizerStage,
    ParserStage,
    RuleEngineStage,
    WeightEngineStage,
    WhitelistStage,
)

logger = logging.getLogger(__name__)


class PipelineManager:
    """
    FPS パイプライン管理クラス。

    使い方:
        pm = PipelineManager()
        pm.set_context(
            dictionary_manager=dm,
            rule_manager=rm,
        )
        result = pm.compile("(masterpiece), blue_eyes, [bad hands]")
        print(result.prompt)
    """

    def __init__(
        self,
        abort_on_error: bool = False,
        event_bus: Any = None,
        cache_manager: Any = None,
        **stage_kwargs: Any,
    ) -> None:
        self._abort_on_error = abort_on_error
        self._context: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._cache_manager = cache_manager
        self._cache_hits = 0
        self._cache_misses = 0

        # デフォルトステージ構成
        self._stages: list[BaseStage] = [
            ParserStage(),
            NormalizerStage(),
            DuplicateCleanerStage(),
            BlacklistStage(),
            WhitelistStage(),
            CategorizerStage(),
            RuleEngineStage(),
            WeightEngineStage(),
            OptimizerStage(),
            ExporterStage(),
        ]

        self._run_count = 0
        self._error_count = 0

    # ══════════════════════════════════════════════════════════════
    # Compile
    # ══════════════════════════════════════════════════════════════

    def compile(self, prompt: str) -> PipelineResult:
        """
        プロンプトをパイプラインでコンパイルする。
        cache_manager が設定されていれば、同一プロンプト + 同一コンテキスト
        構成での再コンパイル結果をキャッシュから返す。

        Args:
            prompt: DSL 形式のプロンプト文字列

        Returns:
            PipelineResult（キャッシュヒット時はディープコピーを返す）
        """
        cache_key = self._build_cache_key(prompt) if self._cache_manager else None

        if cache_key is not None:
            cached = self._cache_manager.get("pipeline_compile", cache_key)
            if cached is not None:
                self._cache_hits += 1
                self._emit("pipeline.cache_hit", {"prompt": prompt})
                return copy.deepcopy(cached)
            self._cache_misses += 1

        with self._lock:
            ctx = dict(self._context)
            ctx["input"] = prompt

            self._emit("pipeline.before_compile", {"prompt": prompt})

            tags: list[TagEntry] = []
            stage_results: list[StageResult] = []
            errors: list[str] = []

            for stage in self._stages:
                self._emit("stage.before_run", {"stage": stage.name})
                tags, sr = stage.run(tags, ctx)
                stage_results.append(sr)
                self._emit(
                    "stage.after_run",
                    {"stage": stage.name, "status": str(sr.status), "tags_out": sr.tags_out},
                )

                if sr.status == StageStatus.ERROR:
                    errors.append(f"[{sr.stage}] {sr.error}")
                    self._error_count += 1
                    self._emit("stage.error", {"stage": stage.name, "error": sr.error})
                    if self._abort_on_error:
                        break

            self._run_count += 1
            pos = [t for t in tags if not t.negative]
            neg = [t for t in tags if t.negative]

            result = PipelineResult(
                success=len(errors) == 0,
                prompt=ctx.get("output_prompt", ""),
                negative=ctx.get("output_negative", ""),
                tags=pos,
                negative_tags=neg,
                stage_results=stage_results,
                errors=errors,
                meta={
                    "applied_rules": ctx.get("applied_rule_results", []),
                },
            )

            logger.debug(
                "Pipeline compiled: '%s' → prompt='%s' negative='%s'",
                prompt[:40],
                result.prompt[:40],
                result.negative[:40],
            )
            self._emit(
                "pipeline.after_compile",
                {"prompt": prompt, "success": result.success, "tag_count": result.tag_count},
            )
            if not result.success:
                self._emit("pipeline.error", {"prompt": prompt, "errors": errors})

            if cache_key is not None and result.success:
                self._cache_manager.set("pipeline_compile", cache_key, copy.deepcopy(result))

            return result

    # ══════════════════════════════════════════════════════════════
    # Context
    # ══════════════════════════════════════════════════════════════

    def set_context(self, **kwargs: Any) -> PipelineManager:
        """
        パイプラインコンテキストを設定する。

        引数例:
            dictionary_manager = dm
            rule_manager       = rm
            blacklist          = {"bad_hands", "low_quality"}
            whitelist          = set()
            max_weight         = 2.0
        """
        with self._lock:
            self._context.update(kwargs)
        return self

    def get_context(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._context.get(key, default)

    def set_event_bus(self, event_bus: Any) -> PipelineManager:
        """EventBus を設定する（後付け可能）"""
        self._event_bus = event_bus
        return self

    def set_cache_manager(self, cache_manager: Any) -> PipelineManager:
        """CacheManager を設定する（後付け可能）"""
        self._cache_manager = cache_manager
        return self

    def cache_statistics(self) -> dict[str, Any]:
        """キャッシュヒット率の統計を返す"""
        total = self._cache_hits + self._cache_misses
        return {
            "enabled": self._cache_manager is not None,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": round(self._cache_hits / total, 4) if total > 0 else 0.0,
        }

    # ══════════════════════════════════════════════════════════════
    # Stage Control
    # ══════════════════════════════════════════════════════════════

    def enable_stage(self, name: str) -> bool:
        return self._set_stage_enabled(name, True)

    def disable_stage(self, name: str) -> bool:
        return self._set_stage_enabled(name, False)

    def get_stage(self, name: str) -> BaseStage | None:
        return next((s for s in self._stages if s.name == name), None)

    def stage_names(self) -> list[str]:
        return [s.name for s in self._stages]

    def set_blacklist(self, tags: set[str]) -> None:
        stage = self.get_stage("blacklist")
        if stage and isinstance(stage, BlacklistStage):
            stage._blacklist = tags

    def set_whitelist(self, tags: set[str]) -> None:
        stage = self.get_stage("whitelist")
        if stage and isinstance(stage, WhitelistStage):
            stage._whitelist = tags

    # ══════════════════════════════════════════════════════════════
    # Statistics
    # ══════════════════════════════════════════════════════════════

    def statistics(self) -> dict[str, Any]:
        return {
            "run_count": self._run_count,
            "error_count": self._error_count,
            "abort_on_error": self._abort_on_error,
            "stages": self.stage_names(),
            "enabled_stages": [s.name for s in self._stages if s.enabled],
            "disabled_stages": [s.name for s in self._stages if not s.enabled],
        }

    # ══════════════════════════════════════════════════════════════
    # Private
    # ══════════════════════════════════════════════════════════════

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """イベントバスが設定されていればイベントを発火する（未設定なら何もしない）"""
        if self._event_bus is not None:
            try:
                self._event_bus.emit(event_type, data, source="PipelineManager")
            except Exception as e:
                logger.error("Event emit failed for '%s': %s", event_type, e)

    def _build_cache_key(self, prompt: str) -> str:
        """
        キャッシュキーを生成する。
        プロンプト文字列 + 辞書/ルールの内容ハッシュ(統計から代用)を含めることで、
        辞書やルールが更新された場合に自動的にキャッシュミスとなるようにする。
        """
        import hashlib
        import json

        dm = self._context.get("dictionary_manager")
        rm = self._context.get("rule_manager")
        weight_table = self._context.get("category_weight_table")

        version_parts: dict[str, Any] = {}
        if dm is not None:
            try:
                version_parts["dict_keys"] = dm.statistics().get("total_keys", 0)
            except Exception:
                pass
        if rm is not None:
            try:
                version_parts["rule_count"] = rm.statistics().get("total_rules", 0)
            except Exception:
                pass
        if weight_table is not None:
            try:
                version_parts["weight_cats"] = len(weight_table.categories())
            except Exception:
                pass

        version_parts["blacklist"] = sorted(self._context.get("blacklist", set()) or [])
        version_parts["whitelist"] = sorted(self._context.get("whitelist", set()) or [])
        version_parts["max_weight"] = self._context.get("max_weight", 3.0)
        version_parts["weight_preset"] = self._context.get("weight_preset")

        payload = json.dumps(
            {"prompt": prompt, "version": version_parts}, sort_keys=True, default=str
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:24]

    def _set_stage_enabled(self, name: str, enabled: bool) -> bool:
        stage = self.get_stage(name)
        if stage:
            stage.enabled = enabled
            return True
        return False

    def __repr__(self) -> str:
        return (
            f"PipelineManager("
            f"stages={len(self._stages)}, "
            f"runs={self._run_count}, "
            f"abort_on_error={self._abort_on_error})"
        )
