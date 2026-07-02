"""
fps-core/character/manager.py — CharacterManager ★v2.7
キャラクターシートの CRUD とプリセット変換を管理する。
保存先: fps-data/characters/{id}.json
"""
from __future__ import annotations
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from .models import CharacterFeature, CharacterProfile


class CharacterManager:
    """キャラクターシート管理クラス"""

    def __init__(self, characters_dir: Path) -> None:
        self._dir  = Path(characters_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ── CRUD ──────────────────────────────────────────────────────

    def create(
        self,
        id:          str,
        name:        str,
        description: str = "",
        features:    list[dict] | None = None,
        neg_features: list[dict] | None = None,
        tags:        list[str] | None = None,
    ) -> CharacterProfile:
        """キャラクターシートを新規作成する"""
        now = datetime.now().isoformat()
        char = CharacterProfile(
            id=id, name=name, description=description,
            features=[CharacterFeature(**f) for f in (features or [])],
            neg_features=[CharacterFeature(**f) for f in (neg_features or [])],
            tags=tags or [],
            created_at=now, updated_at=now,
        )
        self._save(char)
        return char

    def get(self, id: str) -> CharacterProfile | None:
        path = self._dir / f"{id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return self._dict_to_profile(data)
        except Exception:
            return None

    def list_all(self) -> list[CharacterProfile]:
        result = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                result.append(self._dict_to_profile(data))
            except Exception:
                pass
        return result

    def update(
        self,
        id:          str,
        name:        str | None = None,
        description: str | None = None,
        features:    list[dict] | None = None,
        neg_features: list[dict] | None = None,
        tags:        list[str] | None = None,
    ) -> CharacterProfile | None:
        char = self.get(id)
        if char is None:
            return None
        if name is not None:        char.name = name
        if description is not None: char.description = description
        if features is not None:
            char.features = [CharacterFeature(**f) for f in features]
        if neg_features is not None:
            char.neg_features = [CharacterFeature(**f) for f in neg_features]
        if tags is not None:        char.tags = tags
        char.updated_at = datetime.now().isoformat()
        self._save(char)
        return char

    def delete(self, id: str) -> bool:
        path = self._dir / f"{id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    # ── プリセット変換 ─────────────────────────────────────────────

    def to_preset(
        self,
        id: str,
        preset_manager: Any,
        preset_id: str | None = None,
    ) -> Any | None:
        """
        キャラクターシートをプリセットに変換して保存する。

        Returns:
            Preset オブジェクト or None
        """
        char = self.get(id)
        if char is None:
            return None

        from preset.models import Preset, PresetSource, PresetTag  # type: ignore
        pid = preset_id or f"char_{id}"
        preset = Preset(
            id=pid,
            name=f"[キャラ] {char.name}",
            description=char.description or f"{char.name} のキャラクターシートから自動生成",
            tags=[
                PresetTag(tag=f.tag, category=f.category, weight=f.weight)
                for f in char.features
            ] + [
                PresetTag(tag=t, category="", weight=1.0)
                for t in char.tags
            ],
            negative_tags=[
                PresetTag(tag=f.tag, category=f.category, weight=f.weight)
                for f in char.neg_features
            ],
            source=PresetSource.USER,
        )
        preset_manager.save(preset)
        return preset

    def statistics(self) -> dict[str, Any]:
        chars = self.list_all()
        return {
            "character_count": len(chars),
            "total_features":  sum(len(c.features) for c in chars),
        }

    # ── 内部 ──────────────────────────────────────────────────────

    def _save(self, char: CharacterProfile) -> None:
        path = self._dir / f"{char.id}.json"
        path.write_text(
            json.dumps(char.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _dict_to_profile(data: dict) -> CharacterProfile:
        return CharacterProfile(
            id=data["id"], name=data["name"],
            description=data.get("description", ""),
            features=[
                CharacterFeature(tag=f["tag"], weight=f.get("weight", 1.0),
                                 category=f.get("category", ""), note=f.get("note", ""))
                for f in data.get("features", [])
            ],
            neg_features=[
                CharacterFeature(tag=f["tag"], weight=f.get("weight", 1.0),
                                 category=f.get("category", ""), note=f.get("note", ""))
                for f in data.get("neg_features", [])
            ],
            tags=data.get("tags", []),
            meta=data.get("meta", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
