"""
fps-tools/tests/unit/test_events.py

Event System のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_events.py -v
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from events.event_bus import EventBus
from events.handlers import StageTimingHandler, StatsCollectorHandler, logging_handler
from events.models import Event, EventType, HandlerRegistration


# ══════════════════════════════════════════════════════════════════
# models
# ══════════════════════════════════════════════════════════════════

class TestModels:
    def test_event_get_with_default(self):
        e = Event(type=EventType.CUSTOM, data={"x": 1})
        assert e.get("x") == 1
        assert e.get("y", "default") == "default"

    def test_event_default_data_empty(self):
        e = Event(type=EventType.CUSTOM)
        assert e.data == {}

    def test_handler_registration_fields(self):
        h = HandlerRegistration(event_type="test", handler_name="fn", priority=5)
        assert h.priority == 5
        assert h.once is False


# ══════════════════════════════════════════════════════════════════
# EventBus — subscribe / emit
# ══════════════════════════════════════════════════════════════════

class TestEventBusBasic:
    def test_on_and_emit(self):
        bus = EventBus()
        received = []
        bus.on("test.event", lambda e: received.append(e))
        bus.emit("test.event", {"x": 1})
        assert len(received) == 1
        assert received[0].data["x"] == 1

    def test_emit_no_handlers_no_error(self):
        bus = EventBus()
        event = bus.emit("nonexistent.event")
        assert event.type == "nonexistent.event"

    def test_multiple_handlers_same_event(self):
        bus = EventBus()
        calls = []
        bus.on("test", lambda e: calls.append("a"))
        bus.on("test", lambda e: calls.append("b"))
        bus.emit("test")
        assert calls == ["b", "a"] or calls == ["a", "b"]  # 順序は priority 依存
        assert len(calls) == 2

    def test_priority_order(self):
        bus = EventBus()
        order = []
        bus.on("test", lambda e: order.append("low"), priority=1)
        bus.on("test", lambda e: order.append("high"), priority=10)
        bus.emit("test")
        assert order == ["high", "low"]

    def test_wildcard_handler_receives_all(self):
        bus = EventBus()
        received = []
        bus.on("*", lambda e: received.append(e.type))
        bus.emit("event.a")
        bus.emit("event.b")
        assert "event.a" in received
        assert "event.b" in received

    def test_handler_exception_does_not_block_others(self):
        bus = EventBus()
        calls = []

        def bad_handler(e):
            raise RuntimeError("boom")

        bus.on("test", bad_handler, priority=10)
        bus.on("test", lambda e: calls.append("ok"), priority=1)
        bus.emit("test")
        assert calls == ["ok"]

    def test_emit_returns_event(self):
        bus = EventBus()
        event = bus.emit("test", {"a": 1}, source="unittest")
        assert event.source == "unittest"
        assert event.data["a"] == 1


# ══════════════════════════════════════════════════════════════════
# EventBus — once / off
# ══════════════════════════════════════════════════════════════════

class TestEventBusOnceOff:
    def test_once_fires_only_once(self):
        bus = EventBus()
        calls = []
        bus.once("test", lambda e: calls.append(1))
        bus.emit("test")
        bus.emit("test")
        assert len(calls) == 1

    def test_off_removes_handler(self):
        bus = EventBus()
        calls = []
        handler = lambda e: calls.append(1)
        bus.on("test", handler)
        bus.off("test", handler)
        bus.emit("test")
        assert calls == []

    def test_off_returns_false_if_not_found(self):
        bus = EventBus()
        assert bus.off("test", lambda e: None) is False

    def test_off_all_specific_event(self):
        bus = EventBus()
        calls = []
        bus.on("test", lambda e: calls.append(1))
        bus.off_all("test")
        bus.emit("test")
        assert calls == []

    def test_off_all_global(self):
        bus = EventBus()
        calls = []
        bus.on("a", lambda e: calls.append(1))
        bus.on("b", lambda e: calls.append(1))
        bus.off_all()
        bus.emit("a")
        bus.emit("b")
        assert calls == []

    def test_off_wildcard(self):
        bus = EventBus()
        calls = []
        handler = lambda e: calls.append(1)
        bus.on("*", handler)
        bus.off("*", handler)
        bus.emit("anything")
        assert calls == []


# ══════════════════════════════════════════════════════════════════
# EventBus — history
# ══════════════════════════════════════════════════════════════════

class TestEventBusHistory:
    def test_history_disabled_by_default(self):
        bus = EventBus()
        bus.emit("test")
        assert bus.get_history() == []

    def test_history_enabled_records_events(self):
        bus = EventBus()
        bus.enable_history()
        bus.emit("test1")
        bus.emit("test2")
        history = bus.get_history()
        assert len(history) == 2

    def test_history_filter_by_type(self):
        bus = EventBus()
        bus.enable_history()
        bus.emit("a")
        bus.emit("b")
        bus.emit("a")
        a_events = bus.get_history("a")
        assert len(a_events) == 2

    def test_history_max_limit(self):
        bus = EventBus()
        bus.enable_history(max_history=3)
        for i in range(5):
            bus.emit(f"event{i}")
        assert len(bus.get_history()) == 3

    def test_disable_history(self):
        bus = EventBus()
        bus.enable_history()
        bus.emit("a")
        bus.disable_history()
        bus.emit("b")
        assert len(bus.get_history()) == 1

    def test_clear_history(self):
        bus = EventBus()
        bus.enable_history()
        bus.emit("a")
        bus.clear_history()
        assert bus.get_history() == []


# ══════════════════════════════════════════════════════════════════
# EventBus — introspection
# ══════════════════════════════════════════════════════════════════

class TestEventBusIntrospection:
    def test_handler_count(self):
        bus = EventBus()
        bus.on("a", lambda e: None)
        bus.on("a", lambda e: None)
        bus.on("b", lambda e: None)
        assert bus.handler_count("a") == 2
        assert bus.handler_count("b") == 1
        assert bus.handler_count() == 3

    def test_registrations_list(self):
        bus = EventBus()

        def my_handler(e):
            pass

        bus.on("test", my_handler, priority=5)
        regs = bus.registrations()
        assert len(regs) == 1
        assert regs[0].handler_name == "my_handler"
        assert regs[0].priority == 5

    def test_repr(self):
        bus = EventBus()
        bus.on("test", lambda e: None)
        assert "EventBus" in repr(bus)


# ══════════════════════════════════════════════════════════════════
# 組み込みハンドラー
# ══════════════════════════════════════════════════════════════════

class TestBuiltinHandlers:
    def test_logging_handler_no_error(self):
        event = Event(type="test", data={"x": 1})
        logging_handler(event)  # 例外が出なければOK

    def test_stats_collector_counts(self):
        collector = StatsCollectorHandler()
        bus = EventBus()
        bus.on("*", collector)
        bus.emit("a")
        bus.emit("a")
        bus.emit("b")
        stats = collector.stats()
        assert stats["total_events"] == 3
        assert stats["by_type"]["a"] == 2

    def test_stats_collector_error_tracking(self):
        collector = StatsCollectorHandler()
        bus = EventBus()
        bus.on("*", collector)
        bus.emit("stage.error", {"msg": "fail"})
        stats = collector.stats()
        assert stats["error_count"] == 1

    def test_stats_collector_reset(self):
        collector = StatsCollectorHandler()
        bus = EventBus()
        bus.on("*", collector)
        bus.emit("a")
        collector.reset()
        assert collector.stats()["total_events"] == 0

    def test_stage_timing_handler(self):
        timing = StageTimingHandler()
        timing.on_before(Event(type="before", data={"stage": "parser"}))
        time.sleep(0.01)
        timing.on_after(Event(type="after", data={"stage": "parser"}))
        timings = timing.timings()
        assert "parser" in timings
        assert timings["parser"]["avg_ms"] > 0

    def test_stage_timing_handler_no_matching_before(self):
        timing = StageTimingHandler()
        timing.on_after(Event(type="after", data={"stage": "unknown"}))
        assert timing.timings() == {}

    def test_stage_timing_handler_reset(self):
        timing = StageTimingHandler()
        timing.on_before(Event(type="before", data={"stage": "x"}))
        timing.on_after(Event(type="after", data={"stage": "x"}))
        timing.reset()
        assert timing.timings() == {}


# ══════════════════════════════════════════════════════════════════
# PipelineManager 統合
# ══════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    def test_pipeline_emits_events(self):
        from pipeline.manager import PipelineManager

        bus = EventBus()
        received = []
        bus.on("*", lambda e: received.append(e.type))

        pm = PipelineManager(event_bus=bus)
        pm.compile("masterpiece")

        assert "pipeline.before_compile" in received
        assert "pipeline.after_compile" in received
        assert "stage.before_run" in received
        assert "stage.after_run" in received

    def test_pipeline_without_event_bus_no_error(self):
        from pipeline.manager import PipelineManager

        pm = PipelineManager()  # event_bus 未指定
        result = pm.compile("masterpiece")
        assert result.success is True

    def test_set_event_bus_after_init(self):
        from pipeline.manager import PipelineManager

        bus = EventBus()
        received = []
        bus.on("pipeline.after_compile", lambda e: received.append(e))

        pm = PipelineManager()
        pm.set_event_bus(bus)
        pm.compile("masterpiece")

        assert len(received) == 1

    def test_stage_events_have_stage_name(self):
        from pipeline.manager import PipelineManager

        bus = EventBus()
        stage_names = []
        bus.on("stage.before_run", lambda e: stage_names.append(e.get("stage")))

        pm = PipelineManager(event_bus=bus)
        pm.compile("masterpiece")

        assert "parser" in stage_names
        assert "exporter" in stage_names

    def test_collector_with_real_pipeline(self):
        from pipeline.manager import PipelineManager

        bus = EventBus()
        collector = StatsCollectorHandler()
        bus.on("*", collector)

        pm = PipelineManager(event_bus=bus)
        pm.compile("masterpiece, blue_eyes")

        stats = collector.stats()
        assert stats["total_events"] > 0
        assert stats["by_type"]["stage.before_run"] == 10  # 10ステージ

    def test_timing_with_real_pipeline(self):
        from pipeline.manager import PipelineManager

        bus = EventBus()
        timing = StageTimingHandler()
        bus.on(EventType.STAGE_BEFORE_RUN, timing.on_before)
        bus.on(EventType.STAGE_AFTER_RUN, timing.on_after)

        pm = PipelineManager(event_bus=bus)
        pm.compile("masterpiece")

        timings = timing.timings()
        assert len(timings) == 10  # 全10ステージ
        assert "parser" in timings

    def test_pipeline_error_event(self):
        """RuleEngineStage が例外を投げた場合に stage.error が発火すること"""
        from unittest.mock import MagicMock

        from pipeline.manager import PipelineManager

        bus = EventBus()
        error_events = []
        bus.on("stage.error", lambda e: error_events.append(e))

        rm = MagicMock()
        rm.apply.side_effect = RuntimeError("forced failure")

        pm = PipelineManager(event_bus=bus)
        pm.set_context(rule_manager=rm)
        pm.compile("masterpiece")

        assert len(error_events) == 1
        assert error_events[0].get("stage") == "rule_engine"
