"""
fps-core/marketplace/manager.py — MarketplaceManager
★ v3.0 新設

プラグイン（辞書・ルール・テンプレート・Wildcard）の
検索・インストール・管理を担当する。

インストール先: fps-data/plugins/{type}/{id}/
マニフェスト:   fps-data/plugins/installed.json
"""
from __future__ import annotations

import hashlib
import json
import threading
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import PluginManifest, PluginSource, PluginType

# FPS 公式レジストリ（将来 CDN / GitHub Releases に切り替え予定）
_REGISTRY_URL = "https://raw.githubusercontent.com/glasssoundforest-lab/fps-plugins/main/registry.json"

# ビルトインのサンプルプラグイン（レジストリが取得できない場合のフォールバック）
_BUILTIN_REGISTRY: list[dict] = [
    {
        "id": "novelai-quality-tags",
        "name": "NovelAI Quality Tags",
        "version": "1.2.0",
        "description": "NovelAI 向けの品質タグ辞書（very aesthetic, best quality など）",
        "author": "fps-community",
        "type": "dictionary",
        "source": "registry",
        "source_url": "",
        "tags": ["novelai", "quality", "dictionary"],
        "fps_min_version": "2.0.0",
        "download_count": 1240,
        "rating": 4.7,
        "size_kb": 12.5,
    },
    {
        "id": "anime-character-presets",
        "name": "Anime Character Presets",
        "version": "2.0.0",
        "description": "人気アニメキャラクタープリセット集（50種）",
        "author": "fps-community",
        "type": "preset",
        "source": "registry",
        "source_url": "",
        "tags": ["anime", "character", "preset"],
        "fps_min_version": "2.7.0",
        "download_count": 870,
        "rating": 4.5,
        "size_kb": 48.2,
    },
    {
        "id": "photorealistic-rules",
        "name": "Photorealistic Style Rules",
        "version": "1.0.0",
        "description": "写真リアル系スタイルのルールセット",
        "author": "fps-community",
        "type": "rule",
        "source": "registry",
        "source_url": "",
        "tags": ["realistic", "photography", "rules"],
        "fps_min_version": "2.0.0",
        "download_count": 620,
        "rating": 4.3,
        "size_kb": 8.1,
    },
    {
        "id": "landscape-wildcards",
        "name": "Landscape Wildcard Pack",
        "version": "1.1.0",
        "description": "風景・背景用 Wildcard データ集（mountains/ocean/city など）",
        "author": "fps-community",
        "type": "wildcard",
        "source": "registry",
        "source_url": "",
        "tags": ["landscape", "background", "wildcard"],
        "fps_min_version": "2.6.0",
        "download_count": 430,
        "rating": 4.2,
        "size_kb": 15.7,
    },
    {
        "id": "jp-style-templates",
        "name": "Japanese Style Templates",
        "version": "1.0.0",
        "description": "日本語スタイルのプロンプトテンプレート集",
        "author": "fps-community",
        "type": "template",
        "source": "registry",
        "source_url": "",
        "tags": ["japanese", "template", "style"],
        "fps_min_version": "2.0.0",
        "download_count": 380,
        "rating": 4.4,
        "size_kb": 22.0,
    },
]


class MarketplaceManager:
    """
    プラグインマーケットプレイス管理クラス。

    使い方:
        mm = MarketplaceManager(plugins_dir=Path("fps-data/plugins"))
        plugins = mm.search("anime")
        mm.install(plugins[0])
    """

    def __init__(
        self,
        plugins_dir: Path,
        registry_url: str = _REGISTRY_URL,
        timeout: int = 10,
    ) -> None:
        self._dir     = Path(plugins_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._reg_url = registry_url
        self._timeout = timeout
        self._lock    = threading.RLock()
        self._installed_path = self._dir / "installed.json"
        self._installed: dict[str, dict] = self._load_installed()

    # ── レジストリ取得 ─────────────────────────────────────────────

    def fetch_registry(self) -> list[PluginManifest]:
        """公式レジストリからプラグイン一覧を取得する"""
        try:
            req = urllib.request.Request(self._reg_url)
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                data = json.loads(r.read().decode())
                entries = data if isinstance(data, list) else data.get("plugins", [])
        except Exception:
            entries = _BUILTIN_REGISTRY

        result = []
        for e in entries:
            m = self._dict_to_manifest(e)
            m.installed = e["id"] in self._installed
            result.append(m)
        return result

    def search(
        self,
        query: str = "",
        plugin_type: str | None = None,
        limit: int = 20,
    ) -> list[PluginManifest]:
        """プラグインを検索する"""
        plugins = self.fetch_registry()
        ql = query.strip().lower()
        if ql:
            plugins = [
                p for p in plugins
                if ql in p.name.lower()
                or ql in p.description.lower()
                or any(ql in t for t in p.tags)
            ]
        if plugin_type:
            plugins = [p for p in plugins if p.type == plugin_type]
        plugins.sort(key=lambda p: (-p.rating, -p.download_count))
        return plugins[:limit]

    # ── インストール ─────────────────────────────────────────────────

    def install(
        self,
        manifest: PluginManifest | dict,
        data_root: Path | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        プラグインをインストールする。

        Args:
            manifest:  プラグインマニフェスト
            data_root: fps-data ルート（省略時は plugins_dir の親）
            force:     既存の場合でも再インストールするか

        Returns:
            インストール結果辞書
        """
        if isinstance(manifest, dict):
            manifest = self._dict_to_manifest(manifest)

        if manifest.id in self._installed and not force:
            return {
                "success": False,
                "plugin_id": manifest.id,
                "message": f"'{manifest.id}' は既にインストール済みです（force=true で再インストール）",
            }

        now = datetime.now().isoformat()
        install_dir = self._dir / manifest.type / manifest.id
        install_dir.mkdir(parents=True, exist_ok=True)

        # ソースからダウンロード（URL/GitHub）or サンプルデータを配置
        result = {"success": True, "plugin_id": manifest.id,
                  "message": "", "files": []}

        if manifest.source_url and manifest.source != PluginSource.REGISTRY:
            try:
                downloaded = self._download(manifest.source_url)
                dest = install_dir / "data.json"
                dest.write_bytes(downloaded)
                result["files"].append(str(dest))
            except Exception as e:
                return {"success": False, "plugin_id": manifest.id,
                        "message": f"ダウンロード失敗: {e}"}
        else:
            # レジストリプラグイン → サンプルプレースホルダーを配置
            placeholder = {
                "plugin_id":   manifest.id,
                "plugin_name": manifest.name,
                "version":     manifest.version,
                "type":        manifest.type,
                "installed_at": now,
                "note": "レジストリからのインストール（サンプル）",
            }
            dest = install_dir / "manifest.json"
            dest.write_text(json.dumps(placeholder, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            result["files"].append(str(dest))

        # インストール記録を更新
        manifest.installed    = True
        manifest.installed_at = now
        with self._lock:
            self._installed[manifest.id] = manifest.to_dict()
            self._save_installed()

        result["message"] = f"✅ '{manifest.name}' v{manifest.version} をインストールしました"
        return result

    def install_from_url(self, url: str, plugin_type: str = "dictionary",
                         plugin_id: str = "") -> dict[str, Any]:
        """URL からプラグインを直接インストールする"""
        pid = plugin_id or url.rstrip("/").split("/")[-1].replace(".json", "")
        manifest = PluginManifest(
            id=pid, name=pid, type=PluginType(plugin_type),
            source=PluginSource.URL, source_url=url,
        )
        return self.install(manifest, force=True)

    def uninstall(self, plugin_id: str) -> dict[str, Any]:
        """プラグインをアンインストールする"""
        if plugin_id not in self._installed:
            return {"success": False, "plugin_id": plugin_id,
                    "message": f"'{plugin_id}' はインストールされていません"}
        plugin_type = self._installed[plugin_id].get("type", "dictionary")
        install_dir = self._dir / plugin_type / plugin_id
        if install_dir.exists():
            import shutil
            shutil.rmtree(install_dir)
        with self._lock:
            del self._installed[plugin_id]
            self._save_installed()
        return {"success": True, "plugin_id": plugin_id,
                "message": f"✅ '{plugin_id}' をアンインストールしました"}

    # ── インストール済み ───────────────────────────────────────────

    def list_installed(self) -> list[PluginManifest]:
        """インストール済みプラグイン一覧を返す"""
        return [self._dict_to_manifest({**v, "installed": True})
                for v in self._installed.values()]

    def is_installed(self, plugin_id: str) -> bool:
        return plugin_id in self._installed

    def statistics(self) -> dict[str, Any]:
        return {
            "installed_count":  len(self._installed),
            "by_type": {t: sum(1 for v in self._installed.values()
                               if v.get("type") == t)
                        for t in [e.value for e in PluginType]},
        }

    # ── 内部処理 ──────────────────────────────────────────────────

    def _load_installed(self) -> dict[str, dict]:
        if self._installed_path.exists():
            try:
                return json.loads(self._installed_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_installed(self) -> None:
        self._installed_path.write_text(
            json.dumps(self._installed, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _download(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "FPS/3.0"})
        with urllib.request.urlopen(req, timeout=self._timeout) as r:
            return r.read()

    @staticmethod
    def _dict_to_manifest(data: dict) -> PluginManifest:
        return PluginManifest(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            type=PluginType(data.get("type", "dictionary")),
            source=PluginSource(data.get("source", "registry")),
            source_url=data.get("source_url", ""),
            tags=data.get("tags", []),
            fps_min_version=data.get("fps_min_version", "2.0.0"),
            installed=data.get("installed", False),
            installed_at=data.get("installed_at", ""),
            size_kb=data.get("size_kb", 0.0),
            download_count=data.get("download_count", 0),
            rating=data.get("rating", 0.0),
            homepage=data.get("homepage", ""),
        )
