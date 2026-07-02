"""
fps-core/preset/version_manager.py — プリセットバージョン管理
★ v2.4 新設

プリセット編集時に自動スナップショットを保存し、
任意のバージョンにロールバックできる機能を提供する。

保存先: fps-data/presets/versions/{preset_id}/{timestamp}.json
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class PresetVersion:
    """プリセットのバージョン情報"""
    def __init__(self, version_id: str, preset_id: str,
                 snapshot: dict, created_at: str, label: str = "") -> None:
        self.version_id  = version_id
        self.preset_id   = preset_id
        self.snapshot    = snapshot
        self.created_at  = created_at
        self.label       = label

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id":  self.version_id,
            "preset_id":   self.preset_id,
            "created_at":  self.created_at,
            "label":       self.label,
            "tag_count":   len(self.snapshot.get("tags", [])),
            "neg_count":   len(self.snapshot.get("negative_tags", [])),
        }


class PresetVersionManager:
    """
    プリセットのバージョン履歴管理クラス。

    使い方:
        pvm = PresetVersionManager(versions_dir=Path("fps-data/presets/versions"))
        pvm.snapshot(preset)               # スナップショット保存
        versions = pvm.list_versions(id)   # バージョン一覧
        pvm.restore(preset_manager, id, v) # バージョンリストア
    """

    def __init__(self, versions_dir: Path, max_versions: int = 20) -> None:
        self._dir = Path(versions_dir)
        self._max = max_versions

    def _preset_dir(self, preset_id: str) -> Path:
        d = self._dir / preset_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def snapshot(self, preset: Any, label: str = "") -> PresetVersion:
        """
        プリセットの現在状態をスナップショットとして保存する。
        max_versions を超えた場合は最古を削除する。
        """
        now = datetime.now()
        version_id = now.strftime("%Y%m%d_%H%M%S_%f")[:20]
        snapshot: dict[str, Any] = {
            "id":          preset.id,
            "name":        preset.name,
            "description": getattr(preset, "description", ""),
            "version":     getattr(preset, "version", "1.0"),
            "tags":        [{"tag": t.tag, "category": t.category,
                             "weight": t.weight} for t in preset.tags],
            "negative_tags": [{"tag": t.tag, "category": t.category,
                               "weight": t.weight} for t in preset.negative_tags],
            "meta":        dict(getattr(preset, "meta", {})),
            "source":      str(getattr(preset, "source", "user")),
        }
        d = self._preset_dir(preset.id)
        path = d / f"{version_id}.json"
        path.write_text(json.dumps({
            "version_id": version_id,
            "preset_id":  preset.id,
            "label":      label,
            "created_at": now.isoformat(),
            "snapshot":   snapshot,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        # 古いバージョンを削除
        versions = sorted(d.glob("*.json"))
        while len(versions) > self._max:
            versions[0].unlink()
            versions = versions[1:]

        return PresetVersion(version_id=version_id, preset_id=preset.id,
                             snapshot=snapshot, created_at=now.isoformat(),
                             label=label)

    def list_versions(self, preset_id: str) -> list[PresetVersion]:
        """バージョン一覧を新しい順で返す"""
        d = self._dir / preset_id
        if not d.exists():
            return []
        versions = []
        for path in sorted(d.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                versions.append(PresetVersion(
                    version_id=data["version_id"],
                    preset_id=data["preset_id"],
                    snapshot=data["snapshot"],
                    created_at=data["created_at"],
                    label=data.get("label", ""),
                ))
            except Exception:
                pass
        return versions

    def get_version(self, preset_id: str, version_id: str) -> PresetVersion | None:
        """指定バージョンを取得する"""
        path = self._dir / preset_id / f"{version_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return PresetVersion(
                version_id=data["version_id"],
                preset_id=data["preset_id"],
                snapshot=data["snapshot"],
                created_at=data["created_at"],
                label=data.get("label", ""),
            )
        except Exception:
            return None

    def restore(self, preset_manager: Any, preset_id: str,
                version_id: str) -> Any:
        """
        指定バージョンをリストアして PresetManager に保存する。

        Returns:
            リストアされた Preset オブジェクト
        """
        ver = self.get_version(preset_id, version_id)
        if ver is None:
            raise KeyError(f"Version not found: {preset_id}@{version_id}")

        from .models import Preset, PresetSource, PresetTag  # type: ignore[import]
        snap = ver.snapshot
        preset = Preset(
            id=snap["id"],
            name=snap["name"],
            description=snap.get("description", ""),
            version=snap.get("version", "1.0"),
            tags=[PresetTag(tag=t["tag"], category=t.get("category", ""),
                            weight=t.get("weight", 1.0))
                  for t in snap.get("tags", [])],
            negative_tags=[PresetTag(tag=t["tag"], category=t.get("category", ""),
                                     weight=t.get("weight", 1.0))
                           for t in snap.get("negative_tags", [])],
            source=PresetSource.USER,
            meta=snap.get("meta", {}),
        )
        preset_manager.save(preset)
        # リストア後にスナップショット保存
        self.snapshot(preset, label=f"Restored from {version_id}")
        return preset

    def delete_version(self, preset_id: str, version_id: str) -> bool:
        """指定バージョンを削除する"""
        path = self._dir / preset_id / f"{version_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def delete_all_versions(self, preset_id: str) -> int:
        """プリセットの全バージョンを削除する"""
        d = self._dir / preset_id
        if not d.exists():
            return 0
        count = 0
        for path in d.glob("*.json"):
            path.unlink()
            count += 1
        return count
