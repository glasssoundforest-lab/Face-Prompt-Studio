"""
fps-core/dictionary/loader.py — Dictionary Loader

JSON / YAML 辞書ファイルを DictFile オブジェクトに変換する。

ファイル形式（JSON 例）:
{
  "version": "1.0",
  "category": "quality",
  "description": "画質・品質タグ",
  "entries": [
    {
      "key": "masterpiece",
      "resolved": "Quality.High",
      "aliases": ["best quality", "best_quality"],
      "weight": 1.2,
      "tags": ["positive"]
    }
  ]
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exceptions import DictLoadError
from .models import DictEntry, DictFile, DictSource

try:
    import yaml  # noqa: F401

    _YAML_OK = True
except ImportError:
    _YAML_OK = False


def load_dict_file(path: Path, source: DictSource = DictSource.SYSTEM) -> DictFile:
    """
    辞書ファイル（JSON / YAML）を読み込んで DictFile を返す。

    Args:
        path:   辞書ファイルのパス
        source: DictSource.SYSTEM または DictSource.USER

    Raises:
        DictLoadError: ファイルが存在しない・形式不正
    """
    if not path.exists():
        raise DictLoadError(f"辞書ファイルが見つかりません: {path}")

    raw = _read_raw(path)
    return _parse(raw, path, source)


def load_dict_dir(
    directory: Path,
    source: DictSource = DictSource.SYSTEM,
    glob: str = "*.json",
) -> list[DictFile]:
    """
    ディレクトリ内の全辞書ファイルを読み込む。
    YAML も対象にする場合は glob="*.{json,yaml}" ではなく
    glob="*" として拡張子フィルタを内部で行う。
    """
    if not directory.exists():
        return []

    files: list[DictFile] = []
    patterns = ["*.json", "*.yaml", "*.yml"]

    for pattern in patterns:
        for p in sorted(directory.glob(pattern)):
            if p.name.startswith("."):
                continue
            try:
                files.append(load_dict_file(p, source))
            except DictLoadError:
                raise

    return files


# ── Private ──────────────────────────────────────────────────────────


def _read_raw(path: Path) -> dict[str, Any]:
    """ファイルを読み込んで辞書を返す"""
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise DictLoadError(f"JSON パースエラー: {path}\n{e}") from e

    if suffix in (".yaml", ".yml"):
        if not _YAML_OK:
            raise DictLoadError(
                f"PyYAML がインストールされていません: {path}\n"
                "pip install pyyaml を実行してください。"
            )
        try:
            import yaml

            data = yaml.safe_load(text)
            return data or {}
        except Exception as e:
            raise DictLoadError(f"YAML パースエラー: {path}\n{e}") from e

    raise DictLoadError(f"非対応の拡張子: {path.suffix}")


def _parse(raw: dict[str, Any], path: Path, source: DictSource) -> DictFile:
    """生辞書データを DictFile に変換する"""
    version = str(raw.get("version", "1.0"))
    category = str(raw.get("category", path.stem))
    description = str(raw.get("description", ""))
    raw_entries: list[dict[str, Any]] = raw.get("entries", [])

    if not isinstance(raw_entries, list):
        raise DictLoadError(f"'entries' はリストである必要があります: {path}")

    entries: list[DictEntry] = []
    for i, item in enumerate(raw_entries):
        if not isinstance(item, dict):
            raise DictLoadError(f"entries[{i}] が辞書型ではありません: {path}")
        if "key" not in item:
            raise DictLoadError(f"entries[{i}] に 'key' がありません: {path}")
        if "resolved" not in item:
            raise DictLoadError(f"entries[{i}] に 'resolved' がありません: {path}")

        entries.append(
            DictEntry(
                key=str(item["key"]),
                resolved=str(item["resolved"]),
                category=str(item.get("category", category)),
                aliases=list(item.get("aliases", [])),
                weight=float(item.get("weight", 1.0)),
                source=source,
                tags=list(item.get("tags", [])),
                meta=dict(item.get("meta", {})),
            )
        )

    return DictFile(
        version=version,
        category=category,
        source=source,
        entries=entries,
        description=description,
    )
