"""
fps-core/session/manager.py — プロンプトセッション管理
★ v2.8 新設

セッション = 作業中の複数プロンプトをまとめた状態スナップショット。
保存先: fps-data/sessions/{id}.json

用途:
  - 作業途中の状態を保存して後で再開する
  - 複数バリエーションを1セッションとして比較する
  - セッション間の差分比較
"""
from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SessionEntry:
    """セッション内の1プロンプトエントリ"""
    index:      int
    label:      str
    pos:        str
    neg:        str = ""
    score:      float = 0.0
    metadata:   dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index, "label": self.label,
            "pos": self.pos, "neg": self.neg,
            "score": self.score, "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class PromptSession:
    """プロンプトセッション"""
    id:          str
    name:        str
    description: str = ""
    entries:     list[SessionEntry] = field(default_factory=list)
    tags:        list[str]          = field(default_factory=list)
    created_at:  str = ""
    updated_at:  str = ""
    is_pinned:   bool = False

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def best_entry(self) -> SessionEntry | None:
        if not self.entries:
            return None
        return max(self.entries, key=lambda e: e.score)

    def add_entry(self, pos: str, neg: str = "", label: str = "",
                  score: float = 0.0, metadata: dict | None = None) -> SessionEntry:
        now   = datetime.now().isoformat()
        index = len(self.entries)
        entry = SessionEntry(
            index=index,
            label=label or f"variant_{index + 1}",
            pos=pos, neg=neg, score=score,
            metadata=metadata or {},
            created_at=now,
        )
        self.entries.append(entry)
        self.updated_at = now
        return entry

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name,
            "description": self.description,
            "entries": [e.to_dict() for e in self.entries],
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_pinned": self.is_pinned,
        }


class SessionManager:
    """プロンプトセッション管理クラス"""

    def __init__(self, sessions_dir: Path, max_sessions: int = 100) -> None:
        self._dir  = Path(sessions_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max  = max_sessions
        self._lock = threading.RLock()

    # ── CRUD ──────────────────────────────────────────────────────

    def create(
        self,
        name:        str,
        description: str = "",
        tags:        list[str] | None = None,
    ) -> PromptSession:
        """新規セッションを作成する"""
        now = datetime.now().isoformat()
        sid = secrets.token_urlsafe(8)
        session = PromptSession(
            id=sid, name=name, description=description,
            tags=tags or [], created_at=now, updated_at=now,
        )
        self._save(session)
        self._prune()
        return session

    def get(self, session_id: str) -> PromptSession | None:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            return self._dict_to_session(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except Exception:
            return None

    def list_all(
        self,
        pinned_first: bool = True,
        tag_filter: str | None = None,
    ) -> list[PromptSession]:
        sessions: list[PromptSession] = []
        for path in self._dir.glob("*.json"):
            try:
                s = self._dict_to_session(
                    json.loads(path.read_text(encoding="utf-8"))
                )
                if tag_filter and tag_filter not in s.tags:
                    continue
                sessions.append(s)
            except Exception:
                pass
        sessions.sort(
            key=lambda s: (not s.is_pinned if pinned_first else True,
                           s.updated_at),
            reverse=True,
        )
        return sessions

    def add_entry(
        self,
        session_id: str,
        pos: str, neg: str = "", label: str = "",
        score: float = 0.0, metadata: dict | None = None,
    ) -> SessionEntry | None:
        """セッションにエントリを追加する"""
        session = self.get(session_id)
        if session is None:
            return None
        entry = session.add_entry(pos, neg, label, score, metadata)
        self._save(session)
        return entry

    def update(
        self,
        session_id: str,
        name:        str | None = None,
        description: str | None = None,
        tags:        list[str] | None = None,
        is_pinned:   bool | None = None,
    ) -> PromptSession | None:
        session = self.get(session_id)
        if session is None:
            return None
        if name        is not None: session.name        = name
        if description is not None: session.description = description
        if tags        is not None: session.tags        = tags
        if is_pinned   is not None: session.is_pinned   = is_pinned
        session.updated_at = datetime.now().isoformat()
        self._save(session)
        return session

    def delete(self, session_id: str) -> bool:
        path = self._dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def compare(
        self, session_id: str, idx_a: int, idx_b: int
    ) -> dict[str, Any] | None:
        """セッション内の2エントリを比較する"""
        session = self.get(session_id)
        if session is None:
            return None
        entries = session.entries
        if idx_a >= len(entries) or idx_b >= len(entries):
            return None
        a, b = entries[idx_a], entries[idx_b]
        set_a = {t.strip().lower() for t in a.pos.split(",") if t.strip()}
        set_b = {t.strip().lower() for t in b.pos.split(",") if t.strip()}
        return {
            "entry_a":  a.to_dict(),
            "entry_b":  b.to_dict(),
            "only_in_a": sorted(set_a - set_b),
            "only_in_b": sorted(set_b - set_a),
            "common":    sorted(set_a & set_b),
            "score_diff": round(b.score - a.score, 1),
        }

    def statistics(self) -> dict[str, Any]:
        sessions = self.list_all(pinned_first=False)
        return {
            "session_count":    len(sessions),
            "total_entries":    sum(s.entry_count for s in sessions),
            "pinned_count":     sum(1 for s in sessions if s.is_pinned),
        }

    # ── 内部処理 ──────────────────────────────────────────────────

    def _save(self, session: PromptSession) -> None:
        path = self._dir / f"{session.id}.json"
        path.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _prune(self) -> None:
        """セッション数が上限を超えたら古いものを削除"""
        all_sessions = self.list_all(pinned_first=False)
        if len(all_sessions) > self._max:
            unpinned = [s for s in all_sessions if not s.is_pinned]
            for s in unpinned[self._max:]:
                self.delete(s.id)

    @staticmethod
    def _dict_to_session(data: dict) -> PromptSession:
        entries = [
            SessionEntry(
                index=e["index"], label=e["label"],
                pos=e["pos"], neg=e.get("neg", ""),
                score=e.get("score", 0.0),
                metadata=e.get("metadata", {}),
                created_at=e.get("created_at", ""),
            )
            for e in data.get("entries", [])
        ]
        return PromptSession(
            id=data["id"], name=data["name"],
            description=data.get("description", ""),
            entries=entries,
            tags=data.get("tags", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            is_pinned=data.get("is_pinned", False),
        )
