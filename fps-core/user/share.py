"""
fps-core/user/share.py — プリセット共有 + コミュニティタグ統計
★ v2.3 新設

テーブル:
  shared_presets   — 共有プリセット（トークンベース）
  community_tags   — コミュニティタグ統計（匿名集計）
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_presets (
    token       TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    preset_id   TEXT NOT NULL,
    preset_data TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    expires_at  TEXT,
    view_count  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS community_tags (
    tag         TEXT PRIMARY KEY,
    total_count INTEGER NOT NULL DEFAULT 0,
    user_count  INTEGER NOT NULL DEFAULT 0,
    avg_score   REAL    NOT NULL DEFAULT 0.0,
    category    TEXT    NOT NULL DEFAULT '',
    last_updated TEXT   NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shared_presets_user ON shared_presets(user_id);
CREATE INDEX IF NOT EXISTS idx_community_tags_count ON community_tags(total_count DESC);
"""


class ShareToken:
    """共有プリセット情報"""
    def __init__(self, token: str, user_id: str, preset_id: str,
                 preset_data: dict, title: str, description: str,
                 created_at: str, expires_at: str | None,
                 view_count: int, is_active: bool) -> None:
        self.token       = token
        self.user_id     = user_id
        self.preset_id   = preset_id
        self.preset_data = preset_data
        self.title       = title
        self.description = description
        self.created_at  = created_at
        self.expires_at  = expires_at
        self.view_count  = view_count
        self.is_active   = is_active

    def to_dict(self) -> dict[str, Any]:
        return {
            "token":       self.token,
            "preset_id":   self.preset_id,
            "title":       self.title,
            "description": self.description,
            "created_at":  self.created_at,
            "expires_at":  self.expires_at,
            "view_count":  self.view_count,
            "preset_data": self.preset_data,
        }


class CommunityTagEntry:
    """コミュニティタグ統計エントリ"""
    def __init__(self, tag: str, total_count: int, user_count: int,
                 avg_score: float, category: str, last_updated: str) -> None:
        self.tag          = tag
        self.total_count  = total_count
        self.user_count   = user_count
        self.avg_score    = avg_score
        self.category     = category
        self.last_updated = last_updated

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag":          self.tag,
            "total_count":  self.total_count,
            "user_count":   self.user_count,
            "avg_score":    round(self.avg_score, 1),
            "category":     self.category,
            "last_updated": self.last_updated,
        }


class ShareManager:
    """
    プリセット共有 + コミュニティタグ統計管理クラス。

    使い方:
        sm = ShareManager(db_path=Path("fps-data/user/share.db"))
        token_obj = sm.create_share(user_id="alice", preset_id="my_anime",
                                    preset_data={...}, title="マイアニメプリセット")
        share_url = f"https://example.com/shared/{token_obj.token}"
    """

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._path), check_same_thread=False, isolation_level=None
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            self._connect().executescript(_SCHEMA)

    # ── プリセット共有 ─────────────────────────────────────────────

    def create_share(
        self,
        user_id:     str,
        preset_id:   str,
        preset_data: dict,
        title:       str = "",
        description: str = "",
        expires_days: int | None = 30,
    ) -> ShareToken:
        """
        共有トークンを発行する。

        Args:
            user_id:      共有者のユーザーID
            preset_id:    プリセットID
            preset_data:  プリセットの内容（辞書）
            title:        共有タイトル（省略時はプリセット名）
            description:  説明
            expires_days: 有効期限（日数, None = 無期限）

        Returns:
            ShareToken オブジェクト
        """
        token = secrets.token_urlsafe(20)
        now = datetime.now().isoformat()
        expires_at = None
        if expires_days:
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()

        with self._lock:
            self._connect().execute(
                "INSERT INTO shared_presets "
                "(token, user_id, preset_id, preset_data, title, description, "
                " created_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
                (token, user_id, preset_id,
                 json.dumps(preset_data, ensure_ascii=False),
                 title or preset_id, description, now, expires_at),
            )
        return ShareToken(token=token, user_id=user_id, preset_id=preset_id,
                          preset_data=preset_data, title=title or preset_id,
                          description=description, created_at=now,
                          expires_at=expires_at, view_count=0, is_active=True)

    def get_share(self, token: str) -> ShareToken | None:
        """
        共有トークンからプリセット情報を取得する（view_count を +1 する）。
        """
        now = datetime.now().isoformat()
        with self._lock:
            row = self._connect().execute(
                "SELECT * FROM shared_presets WHERE token = ? AND is_active = 1",
                (token,),
            ).fetchone()
        if row is None:
            return None
        # 有効期限チェック
        if row["expires_at"] and row["expires_at"] < now:
            return None
        # view_count インクリメント
        with self._lock:
            self._connect().execute(
                "UPDATE shared_presets SET view_count = view_count + 1 WHERE token = ?",
                (token,),
            )
        return ShareToken(
            token=row["token"], user_id=row["user_id"],
            preset_id=row["preset_id"],
            preset_data=json.loads(row["preset_data"]),
            title=row["title"], description=row["description"],
            created_at=row["created_at"], expires_at=row["expires_at"],
            view_count=row["view_count"] + 1, is_active=bool(row["is_active"]),
        )

    def list_user_shares(self, user_id: str) -> list[ShareToken]:
        """ユーザーの共有一覧を返す"""
        now = datetime.now().isoformat()
        with self._lock:
            rows = self._connect().execute(
                "SELECT * FROM shared_presets WHERE user_id = ? AND is_active = 1 "
                "ORDER BY created_at DESC", (user_id,)
            ).fetchall()
        result = []
        for row in rows:
            if row["expires_at"] and row["expires_at"] < now:
                continue
            result.append(ShareToken(
                token=row["token"], user_id=row["user_id"],
                preset_id=row["preset_id"],
                preset_data=json.loads(row["preset_data"]),
                title=row["title"], description=row["description"],
                created_at=row["created_at"], expires_at=row["expires_at"],
                view_count=row["view_count"], is_active=True,
            ))
        return result

    def delete_share(self, token: str, user_id: str) -> bool:
        """共有を無効化する（発行者のみ可能）"""
        with self._lock:
            cur = self._connect().execute(
                "UPDATE shared_presets SET is_active = 0 "
                "WHERE token = ? AND user_id = ?", (token, user_id)
            )
        return cur.rowcount > 0

    # ── コミュニティタグ統計 ──────────────────────────────────────

    def contribute_tags(
        self,
        tags: list[str],
        avg_score: float,
        categories: dict[str, str] | None = None,
    ) -> int:
        """
        匿名化したタグ使用データをコミュニティ統計に加算する。

        Args:
            tags:       タグリスト
            avg_score:  そのセッションの平均スコア
            categories: {tag: category} マッピング（省略可）

        Returns:
            更新されたタグ数
        """
        now = datetime.now().isoformat()
        cats = categories or {}
        with self._lock:
            for tag in tags:
                cat = cats.get(tag, "")
                self._connect().execute(
                    """INSERT INTO community_tags
                       (tag, total_count, user_count, avg_score, category, last_updated)
                       VALUES (?, 1, 1, ?, ?, ?)
                       ON CONFLICT(tag) DO UPDATE SET
                         total_count  = total_count + 1,
                         avg_score    = (avg_score * total_count + excluded.avg_score)
                                        / (total_count + 1),
                         category     = CASE WHEN excluded.category != ''
                                        THEN excluded.category ELSE category END,
                         last_updated = excluded.last_updated""",
                    (tag, avg_score, cat, now),
                )
        return len(tags)

    def get_community_tags(
        self,
        limit: int = 50,
        category: str | None = None,
        min_count: int = 1,
    ) -> list[CommunityTagEntry]:
        """コミュニティタグ統計を取得する（使用頻度順）"""
        with self._lock:
            if category:
                rows = self._connect().execute(
                    "SELECT * FROM community_tags "
                    "WHERE total_count >= ? AND category = ? "
                    "ORDER BY total_count DESC LIMIT ?",
                    (min_count, category, limit),
                ).fetchall()
            else:
                rows = self._connect().execute(
                    "SELECT * FROM community_tags WHERE total_count >= ? "
                    "ORDER BY total_count DESC LIMIT ?",
                    (min_count, limit),
                ).fetchall()
        return [
            CommunityTagEntry(
                tag=r["tag"], total_count=r["total_count"],
                user_count=r["user_count"], avg_score=r["avg_score"],
                category=r["category"], last_updated=r["last_updated"],
            )
            for r in rows
        ]

    def community_stats(self) -> dict[str, Any]:
        """コミュニティ統計のサマリーを返す"""
        with self._lock:
            conn = self._connect()
            return {
                "total_tags": conn.execute(
                    "SELECT COUNT(*) FROM community_tags").fetchone()[0],
                "total_contributions": conn.execute(
                    "SELECT SUM(total_count) FROM community_tags").fetchone()[0] or 0,
                "shared_preset_count": conn.execute(
                    "SELECT COUNT(*) FROM shared_presets WHERE is_active=1").fetchone()[0],
            }
