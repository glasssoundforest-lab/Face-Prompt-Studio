"""
fps-core/events/event_bus.py — EventBus

イベントの発火・購読を管理するシンプルな同期イベントバス。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from .models import Event, EventType, HandlerRegistration

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], None]


class EventBus:
    """
    FPS イベントバス。

    使い方:
        bus = EventBus()

        def on_stage_done(event: Event):
            print(f"Stage done: {event.data}")

        bus.on(EventType.STAGE_AFTER_RUN, on_stage_done)
        bus.emit(EventType.STAGE_AFTER_RUN, {"stage": "parser"})
    """

    def __init__(self) -> None:
        # event_type -> [(priority, handler, once), ...]（priority降順で実行）
        self._handlers: dict[str, list[tuple[int, EventHandler, bool]]] = {}
        self._lock = threading.RLock()
        self._wildcard_handlers: list[tuple[int, EventHandler, bool]] = []
        self._history: list[Event] = []
        self._record_history = False
        self._max_history = 200

    # ══════════════════════════════════════════════════════════════
    # Subscribe
    # ══════════════════════════════════════════════════════════════

    def on(
        self,
        event_type: EventType | str,
        handler: EventHandler,
        priority: int = 0,
        once: bool = False,
    ) -> None:
        """
        イベントハンドラーを登録する。

        Args:
            event_type: 購読するイベントタイプ（"*" で全イベント購読）
            handler:    Event を引数に取る関数
            priority:   実行優先度（高いほど先に実行）
            once:       True なら1回実行後に自動解除
        """
        key = str(event_type)
        with self._lock:
            if key == "*":
                self._wildcard_handlers.append((priority, handler, once))
                self._wildcard_handlers.sort(key=lambda x: x[0], reverse=True)
            else:
                self._handlers.setdefault(key, [])
                self._handlers[key].append((priority, handler, once))
                self._handlers[key].sort(key=lambda x: x[0], reverse=True)

        logger.debug("Event handler registered: %s (priority=%d)", key, priority)

    def once(
        self,
        event_type: EventType | str,
        handler: EventHandler,
        priority: int = 0,
    ) -> None:
        """1回限りのハンドラーを登録するショートカット"""
        self.on(event_type, handler, priority=priority, once=True)

    def off(self, event_type: EventType | str, handler: EventHandler) -> bool:
        """
        ハンドラーの登録を解除する。

        Returns:
            解除できた場合 True
        """
        key = str(event_type)
        with self._lock:
            target_list = self._wildcard_handlers if key == "*" else self._handlers.get(key, [])
            for entry in list(target_list):
                if entry[1] is handler:
                    target_list.remove(entry)
                    return True
        return False

    def off_all(self, event_type: EventType | str | None = None) -> None:
        """
        ハンドラーを一括解除する。

        Args:
            event_type: 指定すればそのイベントのみ解除、省略で全解除
        """
        with self._lock:
            if event_type is None:
                self._handlers.clear()
                self._wildcard_handlers.clear()
            else:
                key = str(event_type)
                if key == "*":
                    self._wildcard_handlers.clear()
                else:
                    self._handlers.pop(key, None)

    # ══════════════════════════════════════════════════════════════
    # Emit
    # ══════════════════════════════════════════════════════════════

    def emit(
        self,
        event_type: EventType | str,
        data: dict[str, Any] | None = None,
        source: str = "",
    ) -> Event:
        """
        イベントを発火する。登録済みハンドラーを優先度順に同期実行する。

        ハンドラー内の例外は捕捉してログ出力し、他のハンドラーの実行を妨げない。

        Args:
            event_type: 発火するイベントタイプ
            data:       イベントデータ
            source:     発火元の識別子（任意）

        Returns:
            発火された Event オブジェクト
        """
        event = Event(type=event_type, data=data or {}, source=source)
        key = str(event_type)

        if self._record_history:
            self._add_history(event)

        with self._lock:
            specific = list(self._handlers.get(key, []))
            wildcard = list(self._wildcard_handlers)

        self._dispatch(specific, key, event)
        self._dispatch(wildcard, "*", event)

        return event

    def _dispatch(
        self,
        handlers: list[tuple[int, EventHandler, bool]],
        key: str,
        event: Event,
    ) -> None:
        for _priority, handler, once in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Event handler error for '%s': %s", key, e)
            if once:
                self.off(key if key != "*" else "*", handler)

    # ══════════════════════════════════════════════════════════════
    # History
    # ══════════════════════════════════════════════════════════════

    def enable_history(self, max_history: int = 200) -> None:
        """イベント履歴の記録を有効化する（デバッグ用）"""
        self._record_history = True
        self._max_history = max_history

    def disable_history(self) -> None:
        self._record_history = False

    def get_history(self, event_type: EventType | str | None = None) -> list[Event]:
        """記録されたイベント履歴を返す"""
        with self._lock:
            if event_type is None:
                return list(self._history)
            key = str(event_type)
            return [e for e in self._history if str(e.type) == key]

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()

    def _add_history(self, event: Event) -> None:
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)

    # ══════════════════════════════════════════════════════════════
    # Introspection
    # ══════════════════════════════════════════════════════════════

    def registrations(self) -> list[HandlerRegistration]:
        """登録済みハンドラー一覧を返す（デバッグ用）"""
        result: list[HandlerRegistration] = []
        with self._lock:
            for key, handlers in self._handlers.items():
                for priority, handler, once in handlers:
                    result.append(
                        HandlerRegistration(
                            event_type=key,
                            handler_name=getattr(handler, "__name__", repr(handler)),
                            priority=priority,
                            once=once,
                        )
                    )
            for priority, handler, once in self._wildcard_handlers:
                result.append(
                    HandlerRegistration(
                        event_type="*",
                        handler_name=getattr(handler, "__name__", repr(handler)),
                        priority=priority,
                        once=once,
                    )
                )
        return result

    def handler_count(self, event_type: EventType | str | None = None) -> int:
        with self._lock:
            if event_type is None:
                return sum(len(h) for h in self._handlers.values()) + len(self._wildcard_handlers)
            key = str(event_type)
            if key == "*":
                return len(self._wildcard_handlers)
            return len(self._handlers.get(key, []))

    def __repr__(self) -> str:
        return (
            f"EventBus(event_types={list(self._handlers.keys())}, "
            f"total_handlers={self.handler_count()})"
        )
