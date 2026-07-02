"""
fps-core/user/auth.py — ユーザー認証・管理
★ v2.3 新設

シンプルな API キー方式（UUID ベース）を採用。
OAuth/JWT は v3.0 以降で導入予定。

ユーザー情報は fps-data/user/users.db (SQLite) に保存。

テーブル:
  users      — ユーザー情報
  api_keys   — API キー
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    last_active TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    metadata    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS api_keys (
    key_id      TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    key_hash    TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL DEFAULT 'default',
    created_at  TEXT NOT NULL,
    last_used   TEXT,
    expires_at  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
"""

_ANONYMOUS_USER_ID = "anonymous"


class UserInfo:
    """ユーザー情報"""
    def __init__(self, user_id: str, username: str, display_name: str,
                 created_at: str, last_active: str, is_active: bool = True) -> None:
        self.user_id      = user_id
        self.username     = username
        self.display_name = display_name
        self.created_at   = created_at
        self.last_active  = last_active
        self.is_active    = is_active

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":      self.user_id,
            "username":     self.username,
            "display_name": self.display_name,
            "created_at":   self.created_at,
            "last_active":  self.last_active,
        }


class ApiKeyInfo:
    """API キー情報"""
    def __init__(self, key_id: str, user_id: str, label: str,
                 created_at: str, last_used: str | None,
                 expires_at: str | None, is_active: bool) -> None:
        self.key_id     = key_id
        self.user_id    = user_id
        self.label      = label
        self.created_at = created_at
        self.last_used  = last_used
        self.expires_at = expires_at
        self.is_active  = is_active

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_id":     self.key_id,
            "user_id":    self.user_id,
            "label":      self.label,
            "created_at": self.created_at,
            "last_used":  self.last_used,
            "expires_at": self.expires_at,
        }


class UserManager:
    """
    ユーザー・API キー管理クラス。

    使い方:
        um = UserManager(db_path=Path("fps-data/user/users.db"))
        user, raw_key = um.register("alice", "Alice")
        verified_user = um.verify_api_key(raw_key)
    """

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()
        self._ensure_anonymous()

    # ── 接続 ──────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._path), check_same_thread=False, isolation_level=None
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            self._connect().executescript(_SCHEMA)

    def _ensure_anonymous(self) -> None:
        """匿名ユーザーが存在しなければ作成する"""
        if self.get_user(_ANONYMOUS_USER_ID) is None:
            now = datetime.now().isoformat()
            with self._lock:
                self._connect().execute(
                    "INSERT OR IGNORE INTO users "
                    "(user_id, username, display_name, created_at, last_active) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (_ANONYMOUS_USER_ID, "anonymous", "Anonymous", now, now),
                )

    # ── ユーザー登録・取得 ────────────────────────────────────────

    def register(
        self,
        username: str,
        display_name: str = "",
        expires_days: int | None = None,
    ) -> tuple["UserInfo", str]:
        """
        新規ユーザーを登録して API キー（平文）を返す。

        Args:
            username:     一意なユーザー名（英数字 / _ / -）
            display_name: 表示名
            expires_days: APIキー有効期限（日数、None = 無期限）

        Returns:
            (UserInfo, raw_api_key)  ← raw_api_key は登録時のみ返す（再取得不可）

        Raises:
            ValueError: username が既に存在する
        """
        if not username or not username.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"username は英数字・_・- のみ使用できます: {username!r}")

        if self.get_user_by_name(username) is not None:
            raise ValueError(f"username '{username}' は既に使用されています")

        now = datetime.now().isoformat()
        user_id = secrets.token_urlsafe(12)
        dn = display_name or username

        with self._lock:
            self._connect().execute(
                "INSERT INTO users (user_id, username, display_name, created_at, last_active) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, username, dn, now, now),
            )

        raw_key, key_info = self._create_api_key(user_id, label="default",
                                                  expires_days=expires_days)
        user = UserInfo(user_id=user_id, username=username, display_name=dn,
                        created_at=now, last_active=now)
        return user, raw_key

    def get_user(self, user_id: str) -> "UserInfo | None":
        with self._lock:
            row = self._connect().execute(
                "SELECT * FROM users WHERE user_id = ? AND is_active = 1", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return UserInfo(user_id=row["user_id"], username=row["username"],
                        display_name=row["display_name"], created_at=row["created_at"],
                        last_active=row["last_active"])

    def get_user_by_name(self, username: str) -> "UserInfo | None":
        with self._lock:
            row = self._connect().execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
            ).fetchone()
        if row is None:
            return None
        return UserInfo(user_id=row["user_id"], username=row["username"],
                        display_name=row["display_name"], created_at=row["created_at"],
                        last_active=row["last_active"])

    def list_users(self, limit: int = 100) -> list["UserInfo"]:
        with self._lock:
            rows = self._connect().execute(
                "SELECT * FROM users WHERE is_active = 1 "
                "ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [UserInfo(r["user_id"], r["username"], r["display_name"],
                         r["created_at"], r["last_active"]) for r in rows]

    # ── API キー管理 ──────────────────────────────────────────────

    def _create_api_key(
        self, user_id: str, label: str = "default",
        expires_days: int | None = None,
    ) -> tuple[str, "ApiKeyInfo"]:
        """API キーを生成して DB に保存。平文キーを返す（1回限り）"""
        raw_key = f"fps_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = secrets.token_urlsafe(8)
        now = datetime.now().isoformat()
        expires_at = None
        if expires_days:
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()

        with self._lock:
            self._connect().execute(
                "INSERT INTO api_keys (key_id, user_id, key_hash, label, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key_id, user_id, key_hash, label, now, expires_at),
            )
        info = ApiKeyInfo(key_id=key_id, user_id=user_id, label=label,
                          created_at=now, last_used=None,
                          expires_at=expires_at, is_active=True)
        return raw_key, info

    def create_api_key(
        self, user_id: str, label: str = "new key",
        expires_days: int | None = None,
    ) -> tuple[str, "ApiKeyInfo"]:
        """追加 API キーを生成する（公開メソッド）"""
        if self.get_user(user_id) is None:
            raise ValueError(f"User not found: {user_id!r}")
        return self._create_api_key(user_id, label, expires_days)

    def verify_api_key(self, raw_key: str) -> "UserInfo | None":
        """
        API キーを検証してユーザー情報を返す。

        Returns:
            UserInfo: 有効なキーの場合
            None:     無効・期限切れ・無効化済みの場合
        """
        if not raw_key or not raw_key.startswith("fps_"):
            return None
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        now = datetime.now().isoformat()
        with self._lock:
            row = self._connect().execute(
                "SELECT ak.*, u.username, u.display_name, u.last_active "
                "FROM api_keys ak JOIN users u ON ak.user_id = u.user_id "
                "WHERE ak.key_hash = ? AND ak.is_active = 1 AND u.is_active = 1",
                (key_hash,),
            ).fetchone()
        if row is None:
            return None
        # 有効期限チェック
        if row["expires_at"] and row["expires_at"] < now:
            return None
        # last_used 更新（非同期的に）
        with self._lock:
            self._connect().execute(
                "UPDATE api_keys SET last_used = ? WHERE key_hash = ?", (now, key_hash)
            )
            self._connect().execute(
                "UPDATE users SET last_active = ? WHERE user_id = ?",
                (now, row["user_id"]),
            )
        return UserInfo(user_id=row["user_id"], username=row["username"],
                        display_name=row["display_name"],
                        created_at=row["created_at"], last_active=now)

    def list_api_keys(self, user_id: str) -> list["ApiKeyInfo"]:
        with self._lock:
            rows = self._connect().execute(
                "SELECT * FROM api_keys WHERE user_id = ? AND is_active = 1 "
                "ORDER BY created_at DESC", (user_id,)
            ).fetchall()
        return [ApiKeyInfo(r["key_id"], r["user_id"], r["label"], r["created_at"],
                           r["last_used"], r["expires_at"], bool(r["is_active"]))
                for r in rows]

    def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        with self._lock:
            cur = self._connect().execute(
                "UPDATE api_keys SET is_active = 0 "
                "WHERE key_id = ? AND user_id = ?", (key_id, user_id)
            )
        return cur.rowcount > 0

    def statistics(self) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            return {
                "user_count": conn.execute(
                    "SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0],
                "api_key_count": conn.execute(
                    "SELECT COUNT(*) FROM api_keys WHERE is_active=1").fetchone()[0],
            }

    @property
    def anonymous_user_id(self) -> str:
        return _ANONYMOUS_USER_ID
