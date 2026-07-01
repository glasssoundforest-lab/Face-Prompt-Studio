"""
fps-core/dictionary/manager.py — DictionaryManager

Public API:
  - load()           辞書を読み込む
  - reload()         再読み込み
  - lookup(key)      キー検索
  - lookup_alias(key) エイリアス検索
  - categories()     カテゴリ一覧
  - statistics()     統計情報
  - validate()       バリデーション実行
  - export_json()    JSON エクスポート
  - export_yaml()    YAML エクスポート
  - watch()          ホットリロード開始

優先順位: user 辞書 > system 辞書
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .exceptions import DictionaryError, DictLoadError, DictValidationError
from .loader import load_dict_dir, load_dict_file
from .merger import diff, merge
from .models import DictEntry, DictFile, DictSource, LookupResult
from .validator import validate_dict_file
from .watcher import DictWatcher

logger = logging.getLogger(__name__)

try:
    import yaml  # noqa: F401

    _YAML_OK = True
except ImportError:
    _YAML_OK = False


class DictionaryManager:
    """
    FPS 辞書管理クラス。

    使い方:
        dm = DictionaryManager(
            system_dir="fps-data/dictionaries/system",
            user_dir="fps-data/dictionaries/user",
        )
        dm.load()
        result = dm.lookup("masterpiece")
        print(result.resolved)   # "Quality.High"
    """

    def __init__(
        self,
        system_dir: str | Path | None = None,
        user_dir: str | Path | None = None,
    ) -> None:
        self._system_dir: Path | None = Path(system_dir) if system_dir else None
        self._user_dir: Path | None = Path(user_dir) if user_dir else None

        # 内部インデックス: 正規化キー → DictEntry
        self._index: dict[str, DictEntry] = {}

        # 読み込んだ DictFile リスト（バリデーション・エクスポート用）
        self._system_files: list[DictFile] = []
        self._user_files: list[DictFile] = []

        self._watcher: DictWatcher | None = None
        self._lock = threading.RLock()
        self._loaded = False

    # ══════════════════════════════════════════════════════════════
    # Load / Reload
    # ══════════════════════════════════════════════════════════════

    def load(self) -> DictionaryManager:
        """
        system / user 辞書を読み込んでインデックスを構築する。
        二重呼び出しは安全に再読み込みとして動作する。
        """
        with self._lock:
            self._system_files = self._load_dir(self._system_dir, DictSource.SYSTEM)
            self._user_files = self._load_dir(self._user_dir, DictSource.USER)
            self._build_index()
            self._loaded = True
            logger.info(
                "DictionaryManager loaded: system=%d user=%d total_keys=%d",
                sum(f.entry_count for f in self._system_files),
                sum(f.entry_count for f in self._user_files),
                len(self._index),
            )
        return self

    def load_file(
        self,
        path: str | Path,
        source: DictSource = DictSource.USER,
    ) -> DictionaryManager:
        """単一辞書ファイルを追加読み込みする"""
        p = Path(path)
        with self._lock:
            df = load_dict_file(p, source)
            validate_dict_file(df)
            if source == DictSource.USER:
                self._user_files.append(df)
            else:
                self._system_files.append(df)
            self._build_index()
            logger.info("DictionaryManager: loaded file %s (%d entries)", p, df.entry_count)
        return self

    def reload(self) -> None:
        """辞書を再読み込みする（ホットリロード用）"""
        before = dict(self._index)
        self.load()
        changes = diff(before, self._index)
        if any(changes.values()):
            logger.info(
                "Dictionary reloaded: +%d -%d ~%d",
                len(changes["added"]),
                len(changes["removed"]),
                len(changes["changed"]),
            )

    # ══════════════════════════════════════════════════════════════
    # Lookup
    # ══════════════════════════════════════════════════════════════

    def lookup(self, key: str) -> LookupResult:
        """
        キーを辞書で検索する。

        Args:
            key: 検索キー（大文字小文字・スペース・ハイフン不問）

        Returns:
            LookupResult（found=False の場合もエラーにしない）
        """
        norm = _normalize(key)
        with self._lock:
            entry = self._index.get(norm)
        if entry:
            matched = norm if norm != entry.key else None
            return LookupResult(found=True, key=norm, entry=entry, matched_alias=matched)
        return LookupResult(found=False, key=norm)

    def lookup_alias(self, alias: str) -> LookupResult:
        """エイリアスで検索する（lookup と同じ実装、意味を明示するためのラッパー）"""
        return self.lookup(alias)

    def lookup_many(self, keys: list[str]) -> list[LookupResult]:
        """複数キーを一括検索する"""
        return [self.lookup(k) for k in keys]

    # ══════════════════════════════════════════════════════════════
    # Metadata
    # ══════════════════════════════════════════════════════════════

    def categories(self) -> list[str]:
        """登録されているカテゴリ一覧を返す（重複なし・ソート済み）"""
        with self._lock:
            return sorted({e.category for e in self._index.values()})

    def statistics(self) -> dict[str, Any]:
        """辞書の統計情報を返す"""
        with self._lock:
            entries = list(self._index.values())
            by_source = {
                "system": sum(1 for e in entries if e.source == DictSource.SYSTEM),
                "user": sum(1 for e in entries if e.source == DictSource.USER),
            }
            by_category: dict[str, int] = {}
            for e in entries:
                by_category[e.category] = by_category.get(e.category, 0) + 1

            return {
                "total_keys": len(self._index),
                "total_entries": len({e.key for e in self._index.values()}),
                "by_source": by_source,
                "by_category": by_category,
                "system_files": len(self._system_files),
                "user_files": len(self._user_files),
            }

    # ══════════════════════════════════════════════════════════════
    # Validation
    # ══════════════════════════════════════════════════════════════

    def validate(self) -> list[str]:
        """
        全辞書ファイルをバリデーションしてエラーリストを返す。
        エラーがなければ空リストを返す（例外は投げない）。
        """
        errors: list[str] = []
        with self._lock:
            for df in self._system_files + self._user_files:
                try:
                    validate_dict_file(df)
                except DictValidationError as e:
                    errors.extend(e.errors)
        return errors

    # ══════════════════════════════════════════════════════════════
    # Export
    # ══════════════════════════════════════════════════════════════

    def export_json(self, path: str | Path | None = None) -> str:
        """現在のインデックスを JSON 文字列で返す。path を指定すればファイルに保存する。"""
        data = self._to_export_dict()
        text = json.dumps(data, ensure_ascii=False, indent=2)
        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    def export_yaml(self, path: str | Path | None = None) -> str:
        """現在のインデックスを YAML 文字列で返す。path を指定すればファイルに保存する。"""
        if not _YAML_OK:
            raise DictionaryError("PyYAML がインストールされていません。pip install pyyaml")
        import yaml

        data = self._to_export_dict()
        text = yaml.dump(data, allow_unicode=True, sort_keys=True)
        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    # ══════════════════════════════════════════════════════════════
    # Hot Reload
    # ══════════════════════════════════════════════════════════════

    def watch(
        self,
        callback: Callable[[], None] | None = None,
        interval: int = 5,
    ) -> None:
        """辞書ファイルの変更を監視してホットリロードを開始する"""
        paths = [p for p in [self._system_dir, self._user_dir] if p]

        def _on_change() -> None:
            self.reload()
            if callback:
                callback()

        self._watcher = DictWatcher(paths=paths, callback=_on_change, interval=interval)
        self._watcher.start()

    def unwatch(self) -> None:
        """監視を停止する"""
        if self._watcher:
            self._watcher.stop()

    # ══════════════════════════════════════════════════════════════
    # ★v1.2 User Dictionary CRUD
    # ══════════════════════════════════════════════════════════════

    def _user_custom_file(self) -> Path:
        """ユーザーカスタムエントリを保存する JSON ファイルパスを返す。"""
        if self._user_dir is None:
            raise RuntimeError("user_dir が設定されていません")
        self._user_dir.mkdir(parents=True, exist_ok=True)
        return self._user_dir / "custom.json"

    def _load_user_custom(self) -> dict:
        """custom.json を読み込む（なければ空のスキーマを返す）。"""
        path = self._user_custom_file()
        if not path.exists():
            return {"version": "1.0", "category": "user_custom", "entries": []}
        import json as _json
        return _json.loads(path.read_text(encoding="utf-8"))

    def _save_user_custom(self, data: dict) -> None:
        """custom.json に書き込む。entries が空なら削除する。"""
        import json as _json
        path = self._user_custom_file()
        if not data.get("entries"):
            # エントリが空なら削除（validator は空 entries を拒否するため）
            if path.exists():
                path.unlink()
            return
        path.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_user_entry(
        self,
        key: str,
        resolved: str,
        category: str,
        aliases: list[str] | None = None,
        weight: float = 1.0,
    ) -> None:
        """ユーザー辞書にエントリを追加する（既存キーは上書き）。"""
        import re as _re

        def _norm(s: str) -> str:
            return _re.sub(r"[\s\-]+", "_", s.strip().lower())

        norm_key = _norm(key)
        # aliases は正規化済み文字列で、key 自身との重複を除去
        norm_aliases = []
        seen = {norm_key}
        for a in (aliases or []):
            na = _norm(a)
            if na and na not in seen:
                norm_aliases.append(na)
                seen.add(na)

        with self._lock:
            data = self._load_user_custom()
            entries = data.get("entries", [])
            for e in entries:
                if e["key"] == norm_key:
                    e["resolved"] = resolved
                    e["category"] = category
                    e["aliases"] = norm_aliases
                    e["weight"] = weight
                    break
            else:
                entries.append({
                    "key": norm_key,
                    "resolved": resolved,
                    "category": category,
                    "aliases": norm_aliases,
                    "weight": weight,
                    "tags": ["user"],
                })
            data["entries"] = entries
            self._save_user_custom(data)
        self.reload()

    def update_user_entry(
        self,
        key: str,
        resolved: str | None = None,
        category: str | None = None,
        aliases: list[str] | None = None,
        weight: float | None = None,
    ) -> bool:
        """ユーザー辞書エントリを部分更新する。

        Returns:
            True = 更新成功 / False = キーが見つからない
        """
        with self._lock:
            data = self._load_user_custom()
            entries = data.get("entries", [])
            for e in entries:
                if e["key"] == key:
                    if resolved is not None:
                        e["resolved"] = resolved
                    if category is not None:
                        e["category"] = category
                    if aliases is not None:
                        e["aliases"] = aliases
                    if weight is not None:
                        e["weight"] = weight
                    data["entries"] = entries
                    self._save_user_custom(data)
                    self.reload()
                    return True
            return False

    def delete_user_entry(self, key: str) -> bool:
        """ユーザー辞書からエントリを削除する。

        Returns:
            True = 削除成功 / False = キーが見つからない
        """
        with self._lock:
            data = self._load_user_custom()
            before = len(data.get("entries", []))
            data["entries"] = [e for e in data.get("entries", []) if e["key"] != key]
            if len(data["entries"]) == before:
                return False
            self._save_user_custom(data)
        self.reload()
        return True

    def list_user_entries(self) -> list[dict]:
        """ユーザー辞書のエントリ一覧を返す。"""
        with self._lock:
            data = self._load_user_custom()
            return list(data.get("entries", []))

    # ══════════════════════════════════════════════════════════════
    # Private
    # ══════════════════════════════════════════════════════════════

    def _load_dir(self, directory: Path | None, source: DictSource) -> list[DictFile]:
        if not directory:
            return []
        try:
            files = load_dict_dir(directory, source)
            for df in files:
                validate_dict_file(df)
            return files
        except DictLoadError as e:
            logger.error("辞書読み込みエラー: %s", e)
            raise

    def _build_index(self) -> None:
        """system + user をマージしてインデックスを再構築する"""
        self._index = merge(self._system_files, self._user_files)

    def _to_export_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entries": [
                    {
                        "key": e.key,
                        "resolved": e.resolved,
                        "category": e.category,
                        "aliases": e.aliases,
                        "weight": e.weight,
                        "source": e.source.value,
                    }
                    for e in sorted(
                        {v.key: v for v in self._index.values()}.values(),
                        key=lambda x: x.key,
                    )
                ]
            }

    def __repr__(self) -> str:
        return (
            f"DictionaryManager("
            f"system={self._system_dir}, "
            f"user={self._user_dir}, "
            f"keys={len(self._index)}, "
            f"loaded={self._loaded})"
        )


def _normalize(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace("-", "_")
