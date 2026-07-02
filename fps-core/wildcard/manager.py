"""
fps-core/wildcard/manager.py — WildcardManager
★ v2.6 新設

Wildcard ファイルの CRUD と値の提供を担当する。

保存先: fps-data/wildcards/{name}.json
  name: "style"     → fps-data/wildcards/style.json
  name: "hair/color" → fps-data/wildcards/hair/color.json

テキスト形式（.txt）のインポートにも対応。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import WildcardEntry, WildcardFile


class WildcardManager:
    """
    Wildcard ファイルの CRUD マネージャー。

    使い方:
        wm = WildcardManager(wildcard_dir=Path("fps-data/wildcards"))
        wm.create("style", ["anime_style", "photorealistic", "oil_painting"])
        values = wm.get_values("style")   # ["anime_style", ...]
    """

    def __init__(self, wildcard_dir: Path) -> None:
        self._dir  = Path(wildcard_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache: dict[str, WildcardFile] = {}

    # ── CRUD ──────────────────────────────────────────────────────

    def create(
        self,
        name:        str,
        values:      list[str],
        description: str = "",
        category:    str = "",
        weights:     list[float] | None = None,
    ) -> WildcardFile:
        """Wildcard ファイルを新規作成する"""
        now = datetime.now().isoformat()
        entries = [
            WildcardEntry(
                value=v.strip(),
                weight=(weights[i] if weights and i < len(weights) else 1.0),
            )
            for i, v in enumerate(values) if v.strip()
        ]
        wf = WildcardFile(
            name=name, entries=entries,
            description=description, category=category,
            created_at=now, updated_at=now,
        )
        self._save(wf)
        with self._lock:
            self._cache[name] = wf
        return wf

    def get(self, name: str) -> WildcardFile | None:
        """名前で Wildcard を取得する"""
        with self._lock:
            if name in self._cache:
                return self._cache[name]
        return self._load(name)

    def list_all(self, category: str | None = None) -> list[WildcardFile]:
        """全 Wildcard を一覧取得する"""
        result: list[WildcardFile] = []
        for path in sorted(self._dir.rglob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                wf = self._dict_to_wildcard(data)
                if category is None or wf.category == category:
                    result.append(wf)
            except Exception:
                pass
        return result

    def update(
        self,
        name:        str,
        values:      list[str] | None = None,
        description: str | None = None,
        category:    str | None = None,
        weights:     list[float] | None = None,
    ) -> WildcardFile | None:
        """Wildcard を部分更新する"""
        wf = self.get(name)
        if wf is None:
            return None
        if values is not None:
            wf.entries = [
                WildcardEntry(
                    value=v.strip(),
                    weight=(weights[i] if weights and i < len(weights) else 1.0),
                )
                for i, v in enumerate(values) if v.strip()
            ]
        if description is not None:
            wf.description = description
        if category is not None:
            wf.category = category
        wf.updated_at = datetime.now().isoformat()
        self._save(wf)
        with self._lock:
            self._cache[name] = wf
        return wf

    def delete(self, name: str) -> bool:
        """Wildcard を削除する"""
        path = self._path(name)
        if path.exists():
            path.unlink()
            with self._lock:
                self._cache.pop(name, None)
            return True
        return False

    # ── エンジン連携 ─────────────────────────────────────────────

    def get_values(self, name: str) -> list[str]:
        """WildcardEngine が呼ぶ値取得メソッド（重み無視）"""
        wf = self.get(name)
        if wf is None:
            return []
        return [e.value for e in wf.entries if e.value]

    def get_weighted_values(self, name: str) -> tuple[list[str], list[float]]:
        """重み付き値リストを返す"""
        wf = self.get(name)
        if wf is None:
            return [], []
        return ([e.value for e in wf.entries],
                [e.weight for e in wf.entries])

    # ── インポート ─────────────────────────────────────────────────

    def import_txt(self, name: str, text: str,
                   description: str = "") -> WildcardFile:
        """
        テキスト形式（1行1値）から Wildcard をインポートする。
        # で始まる行はコメント。空行はスキップ。
        """
        values = []
        for line in text.split("
"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            values.append(line)
        return self.create(name, values, description=description)

    def export_txt(self, name: str) -> str:
        """テキスト形式でエクスポートする"""
        wf = self.get(name)
        if wf is None:
            return ""
        lines = [f"# {wf.name}"]
        if wf.description:
            lines.append(f"# {wf.description}")
        lines.append("")
        lines.extend(e.value for e in wf.entries)
        return "
".join(lines)

    def statistics(self) -> dict[str, Any]:
        """統計情報を返す"""
        wildcards = self.list_all()
        total_entries = sum(len(wf.entries) for wf in wildcards)
        return {
            "wildcard_count": len(wildcards),
            "total_entries": total_entries,
            "categories": list({wf.category for wf in wildcards if wf.category}),
        }

    # ── 内部処理 ──────────────────────────────────────────────────

    def _path(self, name: str) -> Path:
        safe = name.replace("/", "_").replace("..", "")
        return self._dir / f"{safe}.json"

    def _save(self, wf: WildcardFile) -> None:
        path = self._path(wf.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(wf.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load(self, name: str) -> WildcardFile | None:
        path = self._path(name)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            wf = self._dict_to_wildcard(data)
            with self._lock:
                self._cache[name] = wf
            return wf
        except Exception:
            return None

    @staticmethod
    def _dict_to_wildcard(data: dict) -> WildcardFile:
        entries = [
            WildcardEntry(
                value=e["value"],
                weight=e.get("weight", 1.0),
                tags=e.get("tags", []),
                comment=e.get("comment", ""),
            )
            for e in data.get("entries", [])
        ]
        return WildcardFile(
            name=data["name"],
            entries=entries,
            description=data.get("description", ""),
            category=data.get("category", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
