"""
fps-core/user/storage.py — UserProfile SQLite ストレージ
★ v2.2 新設

profile.json の代わりに SQLite を使うことで
大規模履歴（10,000件以上）にも対応する。

テーブル構成:
  tag_frequencies  — タグ使用頻度
  tag_weights      — タグ重み設定
  style_rules      — スタイルルール
  score_trends     — スコアトレンド
  meta             — その他メタ情報（最終学習日時など）
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    ScoreTrendEntry,
    StyleRule,
    TagFrequencyEntry,
    TagWeight,
    UserProfile,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tag_frequencies (
    tag          TEXT PRIMARY KEY,
    count        INTEGER NOT NULL DEFAULT 0,
    total_weight REAL    NOT NULL DEFAULT 0.0,
    last_used    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS tag_weights (
    tag          TEXT PRIMARY KEY,
    weight       REAL NOT NULL DEFAULT 1.0,
    reason       TEXT NOT NULL DEFAULT 'manual',
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS style_rules (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    always_include  TEXT NOT NULL DEFAULT '[]',
    always_exclude  TEXT NOT NULL DEFAULT '[]',
    enabled         INTEGER NOT NULL DEFAULT 1,
    sort_order      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS score_trends (
    date         TEXT PRIMARY KEY,
    avg_score    REAL NOT NULL,
    entry_count  INTEGER NOT NULL,
    top_tag      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class SQLiteProfileStorage:
    """
    SQLite ベースの UserProfile ストレージ。

    UserProfileManager から透過的に利用できる。
    profile.json との互換レイヤーも提供。
    """

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # ── 接続管理 ───────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
                isolation_level=None,  # autocommit
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    # ── tag_frequencies ─────────────────────────────────────────

    def upsert_tag_frequency(self, entry: TagFrequencyEntry) -> None:
        with self._lock:
            self._connect().execute(
                """INSERT INTO tag_frequencies (tag, count, total_weight, last_used)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(tag) DO UPDATE SET
                     count        = count + excluded.count,
                     total_weight = total_weight + excluded.total_weight,
                     last_used    = excluded.last_used""",
                (entry.tag, entry.count, entry.total_weight,
                 entry.last_used.isoformat()),
            )

    def get_all_frequencies(self) -> dict[str, TagFrequencyEntry]:
        with self._lock:
            rows = self._connect().execute(
                "SELECT tag, count, total_weight, last_used FROM tag_frequencies"
            ).fetchall()
        result = {}
        for row in rows:
            result[row["tag"]] = TagFrequencyEntry(
                tag=row["tag"],
                count=row["count"],
                total_weight=row["total_weight"],
                last_used=datetime.fromisoformat(row["last_used"]),
            )
        return result

    def delete_frequency(self, tag: str) -> bool:
        with self._lock:
            cur = self._connect().execute(
                "DELETE FROM tag_frequencies WHERE tag = ?", (tag,)
            )
        return cur.rowcount > 0

    def clear_frequencies(self) -> None:
        with self._lock:
            self._connect().execute("DELETE FROM tag_frequencies")

    # ── tag_weights ──────────────────────────────────────────────

    def upsert_tag_weight(self, tw: TagWeight) -> None:
        with self._lock:
            self._connect().execute(
                """INSERT INTO tag_weights (tag, weight, reason, last_updated)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(tag) DO UPDATE SET
                     weight=excluded.weight,
                     reason=excluded.reason,
                     last_updated=excluded.last_updated""",
                (tw.tag, tw.weight, tw.reason, tw.last_updated.isoformat()),
            )

    def get_all_weights(self) -> dict[str, TagWeight]:
        with self._lock:
            rows = self._connect().execute(
                "SELECT tag, weight, reason, last_updated FROM tag_weights"
            ).fetchall()
        return {
            row["tag"]: TagWeight(
                tag=row["tag"], weight=row["weight"], reason=row["reason"],
                last_updated=datetime.fromisoformat(row["last_updated"]),
            )
            for row in rows
        }

    def delete_weight(self, tag: str) -> bool:
        with self._lock:
            cur = self._connect().execute(
                "DELETE FROM tag_weights WHERE tag = ?", (tag,)
            )
        return cur.rowcount > 0

    # ── style_rules ──────────────────────────────────────────────

    def upsert_style_rule(self, rule: StyleRule, sort_order: int = 0) -> None:
        with self._lock:
            self._connect().execute(
                """INSERT INTO style_rules
                   (id, name, always_include, always_exclude, enabled, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name,
                     always_include=excluded.always_include,
                     always_exclude=excluded.always_exclude,
                     enabled=excluded.enabled,
                     sort_order=excluded.sort_order""",
                (rule.id, rule.name,
                 json.dumps(rule.always_include, ensure_ascii=False),
                 json.dumps(rule.always_exclude, ensure_ascii=False),
                 int(rule.enabled), sort_order),
            )

    def get_all_rules(self) -> list[StyleRule]:
        with self._lock:
            rows = self._connect().execute(
                "SELECT id,name,always_include,always_exclude,enabled "
                "FROM style_rules ORDER BY sort_order, id"
            ).fetchall()
        return [
            StyleRule(
                id=row["id"], name=row["name"],
                always_include=json.loads(row["always_include"]),
                always_exclude=json.loads(row["always_exclude"]),
                enabled=bool(row["enabled"]),
            )
            for row in rows
        ]

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            cur = self._connect().execute(
                "DELETE FROM style_rules WHERE id = ?", (rule_id,)
            )
        return cur.rowcount > 0

    # ── score_trends ─────────────────────────────────────────────

    def upsert_score_trend(self, entry: ScoreTrendEntry) -> None:
        with self._lock:
            self._connect().execute(
                """INSERT INTO score_trends (date, avg_score, entry_count, top_tag)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                     avg_score=excluded.avg_score,
                     entry_count=excluded.entry_count,
                     top_tag=excluded.top_tag""",
                (entry.date, entry.avg_score, entry.entry_count, entry.top_tag),
            )

    def get_all_trends(self) -> list[ScoreTrendEntry]:
        with self._lock:
            rows = self._connect().execute(
                "SELECT date, avg_score, entry_count, top_tag "
                "FROM score_trends ORDER BY date"
            ).fetchall()
        return [
            ScoreTrendEntry(
                date=row["date"], avg_score=row["avg_score"],
                entry_count=row["entry_count"], top_tag=row["top_tag"],
            )
            for row in rows
        ]

    def clear_trends(self) -> None:
        with self._lock:
            self._connect().execute("DELETE FROM score_trends")

    # ── meta ────────────────────────────────────────────────────

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._connect().execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_meta(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self._connect().execute(
                "SELECT value FROM meta WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    # ── 全体 ─────────────────────────────────────────────────────

    def clear_all(self) -> None:
        """全テーブルをクリアする（reset() 用）"""
        with self._lock:
            for table in ("tag_frequencies", "tag_weights",
                          "style_rules", "score_trends", "meta"):
                self._connect().execute(f"DELETE FROM {table}")

    def to_profile(self) -> UserProfile:
        """SQLite の内容を UserProfile オブジェクトに変換する"""
        p = UserProfile()
        p.tag_frequencies = self.get_all_frequencies()
        p.tag_weights     = self.get_all_weights()
        p.style_rules     = self.get_all_rules()
        p.score_trends    = self.get_all_trends()
        last_learned_str  = self.get_meta("last_learned")
        if last_learned_str:
            try:
                p.last_learned = datetime.fromisoformat(last_learned_str)
            except ValueError:
                pass
        created_str = self.get_meta("created_at")
        if created_str:
            try:
                p.created_at = datetime.fromisoformat(created_str)
            except ValueError:
                pass
        return p

    def stats(self) -> dict[str, Any]:
        """統計情報を返す"""
        with self._lock:
            conn = self._connect()
            return {
                "tag_frequency_count": conn.execute(
                    "SELECT COUNT(*) FROM tag_frequencies").fetchone()[0],
                "tag_weight_count":    conn.execute(
                    "SELECT COUNT(*) FROM tag_weights").fetchone()[0],
                "style_rule_count":    conn.execute(
                    "SELECT COUNT(*) FROM style_rules").fetchone()[0],
                "score_trend_count":   conn.execute(
                    "SELECT COUNT(*) FROM score_trends").fetchone()[0],
                "db_path": str(self._path),
            }

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
