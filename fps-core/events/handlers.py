"""
fps-core/events/handlers.py — 組み込みイベントハンドラー

EventBus に登録して使う実用的なハンドラー集。
"""

from __future__ import annotations

import logging
import time as _time
from typing import Any

from .models import Event

logger = logging.getLogger(__name__)


def logging_handler(event: Event) -> None:
    """イベントをそのままロガーに出力するハンドラー"""
    logger.debug("[event] %s  source=%s  data=%s", event.type, event.source, event.data)


class StatsCollectorHandler:
    """
    イベント発火回数・エラー回数を集計するハンドラー。

    使い方:
        collector = StatsCollectorHandler()
        bus.on("*", collector)
        ...
        print(collector.stats())
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._errors: list[Event] = []

    def __call__(self, event: Event) -> None:
        key = str(event.type)
        self._counts[key] = self._counts.get(key, 0) + 1
        if "error" in key:
            self._errors.append(event)

    def stats(self) -> dict[str, Any]:
        return {
            "total_events": sum(self._counts.values()),
            "by_type": dict(self._counts),
            "error_count": len(self._errors),
        }

    def reset(self) -> None:
        self._counts.clear()
        self._errors.clear()


class StageTimingHandler:
    """
    ステージ実行時間を計測するハンドラーペア。
    STAGE_BEFORE_RUN / STAGE_AFTER_RUN を組み合わせて使う想定。

    使い方:
        timing = StageTimingHandler()
        bus.on(EventType.STAGE_BEFORE_RUN, timing.on_before)
        bus.on(EventType.STAGE_AFTER_RUN, timing.on_after)
        ...
        print(timing.timings())
    """

    def __init__(self) -> None:
        self._start_times: dict[str, float] = {}
        self._durations: dict[str, list[float]] = {}

    def on_before(self, event: Event) -> None:
        stage = event.get("stage", "")
        self._start_times[stage] = _time.perf_counter()

    def on_after(self, event: Event) -> None:
        stage = event.get("stage", "")
        start = self._start_times.pop(stage, None)
        if start is not None:
            duration_ms = (_time.perf_counter() - start) * 1000
            self._durations.setdefault(stage, []).append(duration_ms)

    def timings(self) -> dict[str, dict[str, float]]:
        """ステージごとの平均・最大実行時間（ミリ秒）を返す"""
        result: dict[str, dict[str, float]] = {}
        for stage, durations in self._durations.items():
            result[stage] = {
                "avg_ms": round(sum(durations) / len(durations), 4),
                "max_ms": round(max(durations), 4),
                "count": len(durations),
            }
        return result

    def reset(self) -> None:
        self._start_times.clear()
        self._durations.clear()
