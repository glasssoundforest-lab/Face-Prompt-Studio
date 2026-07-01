"""
fps-adapters/rest/ws.py — WebSocket ブリッジ
★ v1.9 新設

EventBus と WebSocket クライアントを橋渡しする。
FastAPI の WebSocket エンドポイントから利用する。

チャンネル:
  /ws/pipeline  — pipeline.* / stage.* イベントをリアルタイム配信
  /ws/history   — history.recorded イベントで新規エントリを即時プッシュ
  /ws/events    — 全イベントをサブスクライブ（type フィルタ可能）
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# ConnectionManager — WebSocket 接続の一元管理
# ──────────────────────────────────────────────────────────────

class ConnectionManager:
    """
    WebSocket 接続を channel 単位で管理する。

    使い方:
        manager = ConnectionManager()
        await manager.connect(ws, channel="pipeline")
        await manager.broadcast({"type": "stage.done"}, channel="pipeline")
        manager.disconnect(ws, channel="pipeline")
    """

    def __init__(self) -> None:
        # channel → set of WebSocket
        self._connections: dict[str, set] = {}
        self._lock = threading.Lock()

    async def connect(self, websocket: Any, channel: str) -> None:
        await websocket.accept()
        with self._lock:
            self._connections.setdefault(channel, set()).add(websocket)
        logger.debug("WS connect: channel=%s total=%d", channel,
                     len(self._connections.get(channel, set())))

    def disconnect(self, websocket: Any, channel: str) -> None:
        with self._lock:
            self._connections.get(channel, set()).discard(websocket)
        logger.debug("WS disconnect: channel=%s", channel)

    async def send(self, websocket: Any, data: dict) -> None:
        """1クライアントに送信。失敗しても例外を上に投げない。"""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.debug("WS send failed: %s", e)

    async def broadcast(self, data: dict, channel: str) -> None:
        """チャンネル内の全クライアントにブロードキャスト。"""
        with self._lock:
            targets = set(self._connections.get(channel, set()))
        dead: list = []
        for ws in targets:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        if dead:
            with self._lock:
                ch = self._connections.get(channel, set())
                for ws in dead:
                    ch.discard(ws)

    def connection_count(self, channel: str | None = None) -> int:
        with self._lock:
            if channel:
                return len(self._connections.get(channel, set()))
            return sum(len(s) for s in self._connections.values())

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {ch: len(s) for ch, s in self._connections.items() if s}


# シングルトン
manager = ConnectionManager()


# ──────────────────────────────────────────────────────────────
# EventBus → WebSocket ブリッジのセットアップ
# ──────────────────────────────────────────────────────────────

def _get_loop() -> asyncio.AbstractEventLoop | None:
    """現在の asyncio ループを安全に取得する。"""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        return None


def _schedule_broadcast(data: dict, channel: str) -> None:
    """
    同期コンテキスト（EventBus ハンドラ）から非同期ブロードキャストをスケジュールする。
    asyncio ループが動いていれば call_soon_threadsafe を使う。
    """
    loop = _get_loop()
    if loop and loop.is_running():
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(manager.broadcast(data, channel))
        )


def setup_event_bridge(event_bus: Any) -> None:
    """
    EventBus のハンドラを登録し、イベントを WebSocket へブリッジする。
    CliContext や app.startup 時に一度だけ呼ぶ。
    """

    # ── /ws/pipeline チャンネル ──────────────────────────────
    pipeline_events = {
        "pipeline.before_compile",
        "pipeline.after_compile",
        "pipeline.error",
        "pipeline.cache_hit",
        "stage.before_run",
        "stage.after_run",
        "stage.error",
        "optimizer.analyzed",
    }

    def on_pipeline_event(event: Any) -> None:
        payload = {
            "channel": "pipeline",
            "type": str(event.type),
            "data": _serialize(event.data),
            "ts": event.created_at.isoformat() if hasattr(event, "created_at") else None,
        }
        _schedule_broadcast(payload, "pipeline")

    for et in pipeline_events:
        try:
            event_bus.on(et, on_pipeline_event)
        except Exception:
            pass

    # ── /ws/history チャンネル ───────────────────────────────
    def on_history_recorded(event: Any) -> None:
        payload = {
            "channel": "history",
            "type": "history.recorded",
            "data": _serialize(event.data),
            "ts": event.created_at.isoformat() if hasattr(event, "created_at") else None,
        }
        _schedule_broadcast(payload, "history")

    def on_history_deleted(event: Any) -> None:
        payload = {
            "channel": "history",
            "type": "history.deleted",
            "data": _serialize(event.data),
            "ts": event.created_at.isoformat() if hasattr(event, "created_at") else None,
        }
        _schedule_broadcast(payload, "history")

    try:
        event_bus.on("history.recorded", on_history_recorded)
        event_bus.on("history.deleted",  on_history_deleted)
    except Exception:
        pass

    # ── /ws/events チャンネル（全イベント） ─────────────────
    def on_any_event(event: Any) -> None:
        payload = {
            "channel": "events",
            "type": str(event.type),
            "source": getattr(event, "source", ""),
            "data": _serialize(event.data),
            "ts": event.created_at.isoformat() if hasattr(event, "created_at") else None,
        }
        _schedule_broadcast(payload, "events")

    # 全イベントをキャッチするには各タイプを登録する
    all_event_types = [
        "pipeline.before_compile", "pipeline.after_compile", "pipeline.error",
        "pipeline.cache_hit", "stage.before_run", "stage.after_run", "stage.error",
        "dictionary.loaded", "dictionary.reloaded", "dictionary.lookup_miss",
        "dictionary.before_save", "dictionary.after_save",
        "rule.applied", "rule.before_save", "rule.after_save",
        "preset.before_save", "preset.after_save",
        "backup.created", "backup.restored", "backup.failed",
        "history.recorded", "history.deleted",
        "optimizer.analyzed",
    ]
    for et in all_event_types:
        try:
            event_bus.on(et, on_any_event)
        except Exception:
            pass

    logger.info("WS event bridge registered: %d event types", len(all_event_types))


def _serialize(data: Any) -> Any:
    """dict/list を JSON 安全な形式に変換する（Path や datetime を str に）。"""
    if isinstance(data, dict):
        return {k: _serialize(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_serialize(v) for v in data]
    try:
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return str(data)
