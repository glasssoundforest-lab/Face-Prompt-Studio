"""
fps-core/dictionary/watcher.py — Dictionary Watcher

辞書ディレクトリの変更を監視してホットリロードを行う。
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class DictWatcher:
    """
    辞書ディレクトリの変更を監視するウォッチャー。

    使い方:
        watcher = DictWatcher(
            paths=[system_dir, user_dir],
            callback=on_dict_changed,
            interval=5,
        )
        watcher.start()
        # ... 処理 ...
        watcher.stop()
    """

    def __init__(
        self,
        paths: list[Path],
        callback: Callable[[], None],
        interval: int = 5,
    ) -> None:
        self._paths = paths
        self._callback = callback
        self._interval = interval
        self._thread: threading.Thread | None = None
        self._running = False
        self._mtimes: dict[Path, float] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        """監視スレッドを開始する"""
        if self._running:
            return
        self._running = True
        self._snapshot()
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="fps-dict-watcher",
        )
        self._thread.start()
        logger.info("DictWatcher started (interval=%ds, paths=%s)", self._interval, self._paths)

    def stop(self) -> None:
        """監視スレッドを停止する"""
        self._running = False
        logger.info("DictWatcher stopped.")

    def is_running(self) -> bool:
        return self._running

    # ── Private ──────────────────────────────────────────────────

    def _snapshot(self) -> None:
        """現在の全辞書ファイルの mtime を記録する"""
        with self._lock:
            for path in self._paths:
                if not path.exists():
                    continue
                for f in path.rglob("*"):
                    if f.suffix in (".json", ".yaml", ".yml") and f.is_file():
                        self._mtimes[f] = f.stat().st_mtime

    def _changed(self) -> bool:
        """変更されたファイルがあれば True を返し、スナップショットを更新する"""
        new_mtimes: dict[Path, float] = {}

        for path in self._paths:
            if not path.exists():
                continue
            for f in path.rglob("*"):
                if f.suffix in (".json", ".yaml", ".yml") and f.is_file():
                    new_mtimes[f] = f.stat().st_mtime

        with self._lock:
            if new_mtimes != self._mtimes:
                self._mtimes = new_mtimes
                return True
        return False

    def _loop(self) -> None:
        while self._running:
            time.sleep(self._interval)
            try:
                if self._changed():
                    logger.info("Dictionary file changed — reloading...")
                    self._callback()
            except Exception as e:
                logger.error("DictWatcher error: %s", e)
