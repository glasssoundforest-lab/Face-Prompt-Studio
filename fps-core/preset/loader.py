"""
fps-core/preset/loader.py — Preset Loader

JSON / YAML プリセットファイルを PresetFile オブジェクトに変換する。

ファイル形式（JSON）:
{
  "version": "1.0",
  "presets": [
    {
      "id": "anime_portrait",
      "name": "アニメポートレート",
      "description": "基本的なアニメ風ポートレート",
      "version": "1.0",
      "tags": [
        {"tag": "masterpiece", "category": "quality", "weight": 1.5},
        {"tag": "anime",       "category": "style",   "weight": 1.0}
      ],
      "negative_tags": [
        {"tag": "bad hands", "category": "negative", "weight": 1.0}
      ]
    }
  ]
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exceptions import PresetLoadError
from .models import Preset, PresetFile, PresetSource, PresetTag

try:
    import yaml  # noqa: F401

    _YAML_OK = True
except ImportError:
    _YAML_OK = False


def load_preset_file(path: Path, source: PresetSource = PresetSource.SYSTEM) -> PresetFile:
    """
    プリセットファイル（JSON / YAML）を読み込んで PresetFile を返す。

    Raises:
        PresetLoadError: ファイルが存在しない / 形式不正
    """
    if not path.exists():
        raise PresetLoadError(f"プリセットファイルが見つかりません: {path}")
    raw = _read_raw(path)
    return _parse(raw, path, source)


def load_preset_dir(
    directory: Path,
    source: PresetSource = PresetSource.SYSTEM,
) -> list[PresetFile]:
    """ディレクトリ内の全プリセットファイルを読み込む"""
    if not directory.exists():
        return []
    files: list[PresetFile] = []
    for pattern in ("*.json", "*.yaml", "*.yml"):
        for p in sorted(directory.glob(pattern)):
            if p.name.startswith("."):
                continue
            files.append(load_preset_file(p, source))
    return files


# ── Private ──────────────────────────────────────────────────────────


def _read_raw(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise PresetLoadError(f"JSON パースエラー: {path}\n{e}") from e

    if suffix in (".yaml", ".yml"):
        if not _YAML_OK:
            raise PresetLoadError("PyYAML がインストールされていません。pip install pyyaml")
        try:
            import yaml  # noqa: F401

            data = yaml.safe_load(text)
            return data or {}
        except Exception as e:
            raise PresetLoadError(f"YAML パースエラー: {path}\n{e}") from e

    raise PresetLoadError(f"非対応の拡張子: {path.suffix}")


def _parse(raw: dict[str, Any], path: Path, source: PresetSource) -> PresetFile:
    version = str(raw.get("version", "1.0"))
    raw_presets = raw.get("presets", [])

    if not isinstance(raw_presets, list):
        raise PresetLoadError(f"'presets' はリストである必要があります: {path}")

    presets: list[Preset] = []
    for i, item in enumerate(raw_presets):
        if not isinstance(item, dict):
            raise PresetLoadError(f"presets[{i}] が辞書型ではありません: {path}")
        if "id" not in item:
            raise PresetLoadError(f"presets[{i}] に 'id' がありません: {path}")
        if "name" not in item:
            raise PresetLoadError(f"presets[{i}] に 'name' がありません: {path}")

        tags = [_parse_tag(t) for t in item.get("tags", [])]
        negative_tags = [_parse_tag(t) for t in item.get("negative_tags", [])]

        presets.append(
            Preset(
                id=str(item["id"]),
                name=str(item["name"]),
                tags=tags,
                negative_tags=negative_tags,
                source=source,
                description=str(item.get("description", "")),
                version=str(item.get("version", "1.0")),
                meta=dict(item.get("meta", {})),
            )
        )

    return PresetFile(version=version, source=source, presets=presets)


def _parse_tag(raw: dict[str, Any]) -> PresetTag:
    return PresetTag(
        tag=str(raw.get("tag", "")),
        category=str(raw.get("category", "")),
        weight=float(raw.get("weight", 1.0)),
    )
