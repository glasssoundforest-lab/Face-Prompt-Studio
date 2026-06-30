"""
fps-core/history/history_manager.py — HistoryManager

プロンプト変換履歴の記録・検索・お気に入り管理を行う。
JSON Lines 形式でファイル永続化する（追記が高速、壊れにくい）。

Public API:
  - record(...)        履歴を記録する
  - list_entries()      履歴一覧を返す
  - get(entry_id)        ID で履歴を取得する
  - delete(entry_id)     履歴を削除する
  - toggle_favorite(id)  お気に入り切替
  - search(query)        プロンプト内容で検索
  - compare(id1, id2)    2エントリ間の差分を取得
  - clear()              全履歴削除
  - statistics()         統計情報
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .diff_viewer import diff_entries
from .models import DiffEntry, HistoryEntry

logger = logging.getLogger(__name__)


class HistoryManager:
    """
    FPS プロンプト変換履歴管理クラス。

    使い方:
        hm = HistoryManager(history_file="history/prompt_history.jsonl", max_entries=500)
        hm.load()
        entry = hm.record(
            input_prompt="masterpiece, blue_eyes",
            output_prompt="Quality.High, Eyes.Blue",
            tag_count=2,
            overall_score=85.0,
        )
        hm.list_entries()
    """

    def __init__(
        self,
        history_file: str | Path = "logs/prompt_history.jsonl",
        max_entries: int = 500,
    ) -> None:
        self._history_file = Path(history_file)
        self._max_entries = max_entries
        self._entries: dict[str, HistoryEntry] = {}
        self._order: list[str] = []  # 挿入順（新しい順管理用）
        self._lock = threading.RLock()
        self._loaded = False

    # ══════════════════════════════════════════════════════════════
    # Load / Save
    # ══════════════════════════════════════════════════════════════

    def load(self) -> HistoryManager:
        """履歴ファイルを読み込む（存在しなければ空で開始）"""
        with self._lock:
            self._entries.clear()
            self._order.clear()

            if self._history_file.exists():
                for line in self._history_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = HistoryEntry.from_dict(data)
                        self._entries[entry.id] = entry
                        self._order.append(entry.id)
                    except Exception as e:
                        logger.warning("History entry parse failed, skipped: %s", e)

            self._loaded = True
            logger.info("HistoryManager loaded: %d entries", len(self._entries))
        return self

    def _save_all(self) -> None:
        """全履歴をファイルに書き出す（max_entries 適用後）"""
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(self._entries[eid].to_dict(), ensure_ascii=False)
            for eid in self._order
            if eid in self._entries
        ]
        self._history_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    # ══════════════════════════════════════════════════════════════
    # Record
    # ══════════════════════════════════════════════════════════════

    def record(
        self,
        input_prompt: str,
        output_prompt: str,
        output_negative: str = "",
        tag_count: int = 0,
        overall_score: float = 0.0,
        label: str = "",
        meta: dict[str, Any] | None = None,
    ) -> HistoryEntry:
        """
        プロンプト変換結果を履歴として記録する。

        Returns:
            記録された HistoryEntry
        """
        with self._lock:
            now = datetime.now()
            entry_id = now.strftime("%Y%m%d_%H%M%S_%f")

            entry = HistoryEntry(
                id=entry_id,
                input_prompt=input_prompt,
                output_prompt=output_prompt,
                output_negative=output_negative,
                tag_count=tag_count,
                overall_score=overall_score,
                created_at=now,
                label=label,
                meta=meta or {},
            )

            self._entries[entry_id] = entry
            self._order.append(entry_id)

            # max_entries を超えたら古いもの（favorite以外）から削除
            self._enforce_max_entries()
            self._save_all()

            logger.debug("History recorded: %s", entry_id)
            return entry

    def _enforce_max_entries(self) -> None:
        """max_entries を超過した古いエントリを削除する（favorite は保護）"""
        non_favorite_ids = [eid for eid in self._order if not self._entries[eid].favorite]
        total = len(self._order)
        if total <= self._max_entries:
            return

        excess = total - self._max_entries
        to_remove = non_favorite_ids[:excess]
        for eid in to_remove:
            del self._entries[eid]
            self._order.remove(eid)

    # ══════════════════════════════════════════════════════════════
    # Query
    # ══════════════════════════════════════════════════════════════

    def list_entries(self, limit: int | None = None) -> list[HistoryEntry]:
        """履歴一覧を新しい順で返す"""
        with self._lock:
            ids = list(reversed(self._order))
            if limit:
                ids = ids[:limit]
            return [self._entries[eid] for eid in ids if eid in self._entries]

    def get(self, entry_id: str) -> HistoryEntry | None:
        """ID で履歴エントリを取得する"""
        with self._lock:
            return self._entries.get(entry_id)

    def search(self, query: str) -> list[HistoryEntry]:
        """input/output プロンプトまたはラベルで部分一致検索する"""
        q = query.strip().lower()
        if not q:
            return self.list_entries()
        with self._lock:
            return [
                e
                for e in self.list_entries()
                if q in e.input_prompt.lower()
                or q in e.output_prompt.lower()
                or q in e.label.lower()
            ]

    def favorites(self) -> list[HistoryEntry]:
        """お気に入り登録された履歴のみ返す"""
        return [e for e in self.list_entries() if e.favorite]

    # ══════════════════════════════════════════════════════════════
    # Mutate
    # ══════════════════════════════════════════════════════════════

    def delete(self, entry_id: str) -> bool:
        """履歴を削除する"""
        with self._lock:
            if entry_id not in self._entries:
                return False
            del self._entries[entry_id]
            self._order.remove(entry_id)
            self._save_all()
            return True

    def toggle_favorite(self, entry_id: str) -> bool:
        """お気に入りを切替える。戻り値は切替後の状態。"""
        with self._lock:
            entry = self._entries.get(entry_id)
            if not entry:
                raise KeyError(f"history entry not found: '{entry_id}'")
            entry.favorite = not entry.favorite
            self._save_all()
            return entry.favorite

    def set_label(self, entry_id: str, label: str) -> bool:
        """履歴にラベルを設定する"""
        with self._lock:
            entry = self._entries.get(entry_id)
            if not entry:
                return False
            entry.label = label
            self._save_all()
            return True

    def clear(self, keep_favorites: bool = True) -> int:
        """
        全履歴を削除する。

        Args:
            keep_favorites: True ならお気に入りは残す

        Returns:
            削除した件数
        """
        with self._lock:
            if keep_favorites:
                to_remove = [eid for eid in self._order if not self._entries[eid].favorite]
            else:
                to_remove = list(self._order)

            for eid in to_remove:
                del self._entries[eid]
                self._order.remove(eid)

            self._save_all()
            return len(to_remove)

    # ══════════════════════════════════════════════════════════════
    # Compare
    # ══════════════════════════════════════════════════════════════

    def compare(self, entry_id_1: str, entry_id_2: str) -> DiffEntry:
        """
        2つの履歴エントリ間の差分を返す。

        Raises:
            KeyError: 指定IDが存在しない場合
        """
        e1 = self.get(entry_id_1)
        e2 = self.get(entry_id_2)
        if not e1:
            raise KeyError(f"history entry not found: '{entry_id_1}'")
        if not e2:
            raise KeyError(f"history entry not found: '{entry_id_2}'")
        return diff_entries(e1, e2)

    def compare_with_latest(self, entry_id: str) -> DiffEntry | None:
        """指定エントリと最新エントリを比較する"""
        entries = self.list_entries()
        if not entries:
            return None
        latest = entries[0]
        if latest.id == entry_id:
            return None
        return self.compare(entry_id, latest.id)

    # ══════════════════════════════════════════════════════════════
    # Statistics
    # ══════════════════════════════════════════════════════════════

    def statistics(self) -> dict[str, Any]:
        """履歴の統計情報を返す"""
        with self._lock:
            entries = list(self._entries.values())
            scores = [e.overall_score for e in entries if e.overall_score > 0]
            return {
                "total_entries": len(entries),
                "favorite_count": sum(1 for e in entries if e.favorite),
                "max_entries": self._max_entries,
                "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
                "max_score": round(max(scores), 2) if scores else 0.0,
                "min_score": round(min(scores), 2) if scores else 0.0,
            }

    def __repr__(self) -> str:
        return (
            f"HistoryManager("
            f"file={self._history_file}, "
            f"entries={len(self._entries)}, "
            f"max={self._max_entries})"
        )
