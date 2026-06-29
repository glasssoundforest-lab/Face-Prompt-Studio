"""
fps-core/preset/manager.py — PresetManager

Public API:
  - load()          プリセットを読み込む
  - reload()        再読み込み
  - get(id)         ID でプリセットを取得
  - list()          プリセット一覧
  - search(query)   名前・説明で検索
  - save(preset)    ユーザープリセットを保存
  - delete(id)      ユーザープリセットを削除
  - merge(ids)      複数プリセットをマージ
  - apply(id)       プリセットをタグリストに変換
  - statistics()    統計情報
  - validate()      バリデーション

優先順位: user プリセット > system プリセット
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from .exceptions import (
    PresetError,
    PresetLoadError,
    PresetNotFoundError,
    PresetSaveError,
)
from .loader import load_preset_dir
from .merger import MergeResult, merge_presets
from .models import Preset, PresetFile, PresetSource, PresetTag

logger = logging.getLogger(__name__)


class PresetManager:
    """
    FPS プリセット管理クラス。

    使い方:
        pm = PresetManager(
            system_dir="fps-data/presets/system",
            user_dir="fps-data/presets/user",
        )
        pm.load()
        preset = pm.get("anime_portrait")
        tags   = pm.apply("anime_portrait")
    """

    def __init__(
        self,
        system_dir: str | Path | None = None,
        user_dir: str | Path | None = None,
    ) -> None:
        self._system_dir: Path | None = Path(system_dir) if system_dir else None
        self._user_dir: Path | None = Path(user_dir) if user_dir else None

        # id → Preset インデックス（user が system を上書き）
        self._index: dict[str, Preset] = {}
        self._system_files: list[PresetFile] = []
        self._user_files: list[PresetFile] = []
        self._lock = threading.RLock()
        self._loaded = False

    # ══════════════════════════════════════════════════════════════
    # Load / Reload
    # ══════════════════════════════════════════════════════════════

    def load(self) -> PresetManager:
        """system / user プリセットを読み込んでインデックスを構築する"""
        with self._lock:
            self._system_files = self._load_dir(self._system_dir, PresetSource.SYSTEM)
            self._user_files = self._load_dir(self._user_dir, PresetSource.USER)
            self._build_index()
            self._loaded = True
            logger.info(
                "PresetManager loaded: system=%d user=%d total=%d",
                sum(f.preset_count for f in self._system_files),
                sum(f.preset_count for f in self._user_files),
                len(self._index),
            )
        return self

    def reload(self) -> None:
        """プリセットを再読み込みする"""
        self.load()
        logger.info("PresetManager reloaded.")

    # ══════════════════════════════════════════════════════════════
    # Get / List / Search
    # ══════════════════════════════════════════════════════════════

    def get(self, preset_id: str) -> Preset:
        """
        ID でプリセットを取得する。

        Raises:
            PresetNotFoundError: 存在しない場合
        """
        with self._lock:
            if preset_id not in self._index:
                raise PresetNotFoundError(f"プリセットが見つかりません: '{preset_id}'")
            return self._index[preset_id]

    def get_or_none(self, preset_id: str) -> Preset | None:
        """ID でプリセットを取得する（存在しない場合は None）"""
        with self._lock:
            return self._index.get(preset_id)

    def list_presets(self) -> list[Preset]:
        """全プリセット一覧を名前順で返す"""
        with self._lock:
            return sorted(self._index.values(), key=lambda p: p.name)

    def list_ids(self) -> list[str]:
        """全プリセット ID 一覧を返す"""
        with self._lock:
            return sorted(self._index.keys())

    def search(self, query: str) -> list[Preset]:
        """
        名前・説明・ID でプリセットを検索する（部分一致・大小文字不問）。
        """
        q = query.strip().lower()
        with self._lock:
            return [
                p
                for p in self._index.values()
                if q in p.name.lower() or q in p.description.lower() or q in p.id.lower()
            ]

    def exists(self, preset_id: str) -> bool:
        """プリセットが存在するか確認する"""
        with self._lock:
            return preset_id in self._index

    # ══════════════════════════════════════════════════════════════
    # Save / Delete
    # ══════════════════════════════════════════════════════════════

    def save(self, preset: Preset, filename: str | None = None) -> Path:
        """
        ユーザープリセットを JSON ファイルに保存する。

        Args:
            preset:   保存するプリセット
            filename: ファイル名（省略時は {preset.id}.json）

        Returns:
            保存したファイルのパス
        """
        if not self._user_dir:
            raise PresetSaveError("user_dir が設定されていません。")

        self._user_dir.mkdir(parents=True, exist_ok=True)
        fname = filename or f"{preset.id}.json"
        path = self._user_dir / fname

        data = _preset_to_dict(preset)
        path.write_text(
            json.dumps({"version": "1.0", "presets": [data]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # インデックスに追加
        with self._lock:
            preset_copy = Preset(
                id=preset.id,
                name=preset.name,
                tags=list(preset.tags),
                negative_tags=list(preset.negative_tags),
                source=PresetSource.USER,
                description=preset.description,
                version=preset.version,
                meta=dict(preset.meta),
            )
            self._index[preset.id] = preset_copy

        logger.info("Preset saved: %s → %s", preset.id, path)
        return path

    def delete(self, preset_id: str) -> bool:
        """
        ユーザープリセットを削除する。
        system プリセットは削除できない。

        Returns:
            削除できた場合 True
        """
        with self._lock:
            if preset_id not in self._index:
                return False
            p = self._index[preset_id]
            if p.source == PresetSource.SYSTEM:
                raise PresetError(f"システムプリセットは削除できません: '{preset_id}'")

            # インデックスから削除
            del self._index[preset_id]

            # ファイルも削除
            if self._user_dir:
                for f in self._user_dir.glob(f"{preset_id}.json"):
                    f.unlink()

        logger.info("Preset deleted: %s", preset_id)
        return True

    # ══════════════════════════════════════════════════════════════
    # Merge / Apply
    # ══════════════════════════════════════════════════════════════

    def merge(
        self,
        preset_ids: list[str],
        result_id: str = "merged",
        result_name: str = "Merged Preset",
    ) -> MergeResult:
        """
        複数プリセットをマージして新しいプリセットを返す。
        結果はインデックスには追加しない（必要なら save() で保存）。

        Args:
            preset_ids:  マージするプリセット ID リスト（後ろが優先）
            result_id:   マージ結果のプリセット ID
            result_name: マージ結果のプリセット名
        """
        presets = [self.get(pid) for pid in preset_ids]
        return merge_presets(presets, result_id=result_id, result_name=result_name)

    def apply(self, preset_id: str) -> dict[str, list[dict[str, Any]]]:
        """
        プリセットをタグリスト形式に変換する。

        Returns:
            {
              "tags":          [{"tag": str, "category": str, "weight": float}, ...],
              "negative_tags": [{"tag": str, "category": str, "weight": float}, ...]
            }
        """
        preset = self.get(preset_id)
        return {
            "tags": [_tag_to_dict(t) for t in preset.tags],
            "negative_tags": [_tag_to_dict(t) for t in preset.negative_tags],
        }

    # ══════════════════════════════════════════════════════════════
    # Validate / Statistics
    # ══════════════════════════════════════════════════════════════

    def validate(self) -> list[str]:
        """全プリセットをバリデーションしてエラーリストを返す"""
        errors: list[str] = []
        with self._lock:
            for preset in self._index.values():
                if not preset.id:
                    errors.append("id が空のプリセットがあります")
                if not preset.name:
                    errors.append(f"preset '{preset.id}': name が空です")
                for tag in preset.tags:
                    if not tag.tag:
                        errors.append(f"preset '{preset.id}': タグ名が空です")
                    if not (0.0 < tag.weight <= 3.0):
                        errors.append(
                            f"preset '{preset.id}': tag '{tag.tag}' の weight "
                            f"{tag.weight} は 0〜3.0 の範囲外"
                        )
        return errors

    def statistics(self) -> dict[str, Any]:
        """プリセットの統計情報を返す"""
        with self._lock:
            presets = list(self._index.values())
            by_source = {
                "system": sum(1 for p in presets if p.source == PresetSource.SYSTEM),
                "user": sum(1 for p in presets if p.source == PresetSource.USER),
            }
            return {
                "total_presets": len(presets),
                "by_source": by_source,
                "system_files": len(self._system_files),
                "user_files": len(self._user_files),
                "total_tags": sum(p.tag_count for p in presets),
            }

    # ══════════════════════════════════════════════════════════════
    # Private
    # ══════════════════════════════════════════════════════════════

    def _load_dir(self, directory: Path | None, source: PresetSource) -> list[PresetFile]:
        if not directory:
            return []
        try:
            return load_preset_dir(directory, source)
        except PresetLoadError:
            raise

    def _build_index(self) -> None:
        """system → user の順で上書きしてインデックスを再構築する"""
        self._index = {}
        for pf in self._system_files:
            for p in pf.presets:
                self._index[p.id] = p
        for pf in self._user_files:
            for p in pf.presets:
                self._index[p.id] = p  # user が system を上書き

    def __repr__(self) -> str:
        return (
            f"PresetManager("
            f"system={self._system_dir}, "
            f"user={self._user_dir}, "
            f"presets={len(self._index)}, "
            f"loaded={self._loaded})"
        )


# ── Helpers ──────────────────────────────────────────────────────────


def _tag_to_dict(tag: PresetTag) -> dict[str, Any]:
    return {"tag": tag.tag, "category": tag.category, "weight": tag.weight}


def _preset_to_dict(preset: Preset) -> dict[str, Any]:
    return {
        "id": preset.id,
        "name": preset.name,
        "description": preset.description,
        "version": preset.version,
        "tags": [_tag_to_dict(t) for t in preset.tags],
        "negative_tags": [_tag_to_dict(t) for t in preset.negative_tags],
        "meta": preset.meta,
    }
