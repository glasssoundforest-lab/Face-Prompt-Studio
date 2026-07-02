"""
fps-core/batch/manager.py — BatchManager
★ v2.4 新設

複数プロンプトを一括処理するバッチエンジン。
同期処理（最大 50 件）とジョブ管理を提供する。

使い方:
    bm = BatchManager(pipeline_manager, optimizer_manager)
    result = bm.compile_batch(["prompt1", "prompt2", ...])
    for item in result.items:
        print(item.prompt_out, item.negative_out)
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

_MAX_BATCH_SIZE = 50


@dataclass
class BatchItem:
    """バッチアイテム 1件の結果"""
    index:       int
    input:       str
    prompt_out:  str = ""
    negative_out: str = ""
    tag_count:   int = 0
    score:       float = 0.0
    issues:      list[str] = field(default_factory=list)
    error:       str = ""
    elapsed_ms:  float = 0.0
    success:     bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "index":       self.index,
            "input":       self.input,
            "prompt_out":  self.prompt_out,
            "negative_out": self.negative_out,
            "tag_count":   self.tag_count,
            "score":       round(self.score, 1),
            "issues":      self.issues,
            "error":       self.error,
            "elapsed_ms":  round(self.elapsed_ms, 1),
            "success":     self.success,
        }


@dataclass
class BatchResult:
    """バッチ処理全体の結果"""
    job_id:        str
    mode:          str          # "compile" | "optimize"
    total:         int
    succeeded:     int
    failed:        int
    items:         list[BatchItem]
    started_at:    str
    finished_at:   str
    total_elapsed_ms: float

    @property
    def avg_score(self) -> float:
        scores = [i.score for i in self.items if i.success and i.score > 0]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def avg_tag_count(self) -> float:
        counts = [i.tag_count for i in self.items if i.success]
        return sum(counts) / len(counts) if counts else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id":        self.job_id,
            "mode":          self.mode,
            "total":         self.total,
            "succeeded":     self.succeeded,
            "failed":        self.failed,
            "avg_score":     round(self.avg_score, 1),
            "avg_tag_count": round(self.avg_tag_count, 1),
            "started_at":    self.started_at,
            "finished_at":   self.finished_at,
            "total_elapsed_ms": round(self.total_elapsed_ms, 1),
            "items":         [i.to_dict() for i in self.items],
        }


@dataclass
class BatchJob:
    """バッチジョブのメタ情報（結果なし）"""
    job_id:     str
    mode:       str
    total:      int
    status:     str    # "pending" | "running" | "done" | "error"
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id":     self.job_id,
            "mode":       self.mode,
            "total":      self.total,
            "status":     self.status,
            "created_at": self.created_at,
        }


class BatchManager:
    """
    バッチ処理マネージャー。

    Args:
        pipeline_manager:  PipelineManager インスタンス
        optimizer_manager: OptimizerManager インスタンス（省略可）
    """

    def __init__(self, pipeline_manager: Any,
                 optimizer_manager: Any | None = None) -> None:
        self._pm  = pipeline_manager
        self._om  = optimizer_manager
        self._last_result: BatchResult | None = None

    @property
    def last_result(self) -> BatchResult | None:
        return self._last_result

    # ── バッチコンパイル ───────────────────────────────────────

    def compile_batch(
        self,
        prompts: list[str],
        apply_profile_fn: Any | None = None,
    ) -> BatchResult:
        """
        複数プロンプトを一括コンパイルする。

        Args:
            prompts:          プロンプトリスト（最大 _MAX_BATCH_SIZE 件）
            apply_profile_fn: プロファイル適用関数（省略可）
                              apply_profile_fn(tags: list[str]) -> list[str]

        Returns:
            BatchResult
        """
        if len(prompts) > _MAX_BATCH_SIZE:
            raise ValueError(f"最大 {_MAX_BATCH_SIZE} 件まで処理できます（{len(prompts)} 件指定）")

        job_id = str(uuid.uuid4())[:8]
        started = datetime.now()
        items: list[BatchItem] = []

        for i, prompt in enumerate(prompts):
            t0 = time.perf_counter()
            try:
                # プロファイル適用（オプション）
                if apply_profile_fn:
                    original = [t.strip() for t in prompt.split(",") if t.strip()]
                    applied  = apply_profile_fn(original)
                    prompt   = ", ".join(applied)

                result = self._pm.compile(prompt)
                elapsed = (time.perf_counter() - t0) * 1000
                items.append(BatchItem(
                    index=i, input=prompts[i],
                    prompt_out=result.prompt,
                    negative_out=result.negative,
                    tag_count=result.tag_count,
                    elapsed_ms=elapsed,
                    success=not bool(result.errors),
                    error=", ".join(result.errors) if result.errors else "",
                ))
            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000
                items.append(BatchItem(
                    index=i, input=prompts[i],
                    error=str(e), elapsed_ms=elapsed, success=False,
                ))

        finished = datetime.now()
        total_ms = (finished - started).total_seconds() * 1000
        succeeded = sum(1 for it in items if it.success)

        result = BatchResult(
            job_id=job_id, mode="compile",
            total=len(items), succeeded=succeeded,
            failed=len(items) - succeeded,
            items=items,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            total_elapsed_ms=total_ms,
        )
        self._last_result = result
        return result

    # ── バッチ最適化 ──────────────────────────────────────────

    def optimize_batch(self, prompts: list[str]) -> BatchResult:
        """
        複数プロンプトを一括分析してスコアと問題点を返す。

        Args:
            prompts: プロンプトリスト（最大 _MAX_BATCH_SIZE 件）
        """
        if len(prompts) > _MAX_BATCH_SIZE:
            raise ValueError(f"最大 {_MAX_BATCH_SIZE} 件まで処理できます")

        job_id = str(uuid.uuid4())[:8]
        started = datetime.now()
        items: list[BatchItem] = []

        for i, prompt in enumerate(prompts):
            t0 = time.perf_counter()
            try:
                pipeline_result = self._pm.compile(prompt)
                pos_tags = [
                    {"tag": t.tag, "category": t.category, "weight": t.weight}
                    for t in pipeline_result.tags
                ]
                issues: list[str] = []
                score = 0.0
                if self._om:
                    opt = self._om.analyze(pos_tags)
                    score = opt.score.overall_score
                    issues = [iss.message for iss in opt.issues[:5]]

                elapsed = (time.perf_counter() - t0) * 1000
                items.append(BatchItem(
                    index=i, input=prompt,
                    prompt_out=pipeline_result.prompt,
                    negative_out=pipeline_result.negative,
                    tag_count=pipeline_result.tag_count,
                    score=score, issues=issues,
                    elapsed_ms=elapsed, success=True,
                ))
            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000
                items.append(BatchItem(
                    index=i, input=prompt,
                    error=str(e), elapsed_ms=elapsed, success=False,
                ))

        finished = datetime.now()
        total_ms = (finished - started).total_seconds() * 1000
        succeeded = sum(1 for it in items if it.success)

        result = BatchResult(
            job_id=job_id, mode="optimize",
            total=len(items), succeeded=succeeded,
            failed=len(items) - succeeded,
            items=items,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            total_elapsed_ms=total_ms,
        )
        self._last_result = result
        return result
