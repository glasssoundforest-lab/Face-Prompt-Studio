"""
fps-core/pipeline/manager.py — PipelineManager

Public API:
  - compile(prompt)   プロンプトをコンパイルして PipelineResult を返す
  - set_context(...)  コンテキストを設定する
  - enable_stage(name)  / disable_stage(name)  ステージ切替
  - statistics()      実行統計

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
        **stage_kwargs: Any,
    ) -> None:
        self._abort_on_error = abort_on_error
        self._context: dict[str, Any] = {}
        self._lock = threading.RLock()

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

        Args:
            prompt: DSL 形式のプロンプト文字列

        Returns:
            PipelineResult
        """
        with self._lock:
            ctx = dict(self._context)
            ctx["input"] = prompt

            tags: list[TagEntry] = []
            stage_results: list[StageResult] = []
            errors: list[str] = []

            for stage in self._stages:
                tags, sr = stage.run(tags, ctx)
                stage_results.append(sr)

                if sr.status == StageStatus.ERROR:
                    errors.append(f"[{sr.stage}] {sr.error}")
                    self._error_count += 1
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
