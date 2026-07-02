"""
fps-core/ai/tagger_bridge.py — AI タガーブリッジ
★ v2.5 新設

WD14-tagger / JoyCaption / Florence2 などの画像タガーと連携して
タグ提案を生成する。タガーが利用できない場合は辞書ベースの代替を返す。

アーキテクチャ:
  - 各タガーは外部 HTTP API として呼ばれる（依存ゼロ）
  - タガー未起動の場合は辞書の頻度データで代替提案
  - ComfyUI ノード内から直接呼び出し可能
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaggerModel(str, Enum):
    WD14       = "wd14"
    JOYCAPTION = "joycaption"
    FLORENCE2  = "florence2"
    DICTIONARY = "dictionary"   # フォールバック（外部依存なし）


@dataclass
class TaggerResult:
    """タガーの実行結果"""
    model:      str
    tags:       list[dict[str, float]]   # [{"tag": str, "score": float}]
    raw_output: str  = ""
    error:      str  = ""
    success:    bool = True
    source:     str  = "ai"              # "ai" | "dictionary" | "fallback"

    def top_tags(self, n: int = 20, threshold: float = 0.35) -> list[str]:
        """スコア閾値以上のタグを上位 n 件返す"""
        filtered = [(t["tag"], t["score"])
                    for t in self.tags if t.get("score", 0) >= threshold]
        filtered.sort(key=lambda x: -x[1])
        return [tag for tag, _ in filtered[:n]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model":   self.model,
            "tags":    self.tags[:50],
            "error":   self.error,
            "success": self.success,
            "source":  self.source,
        }


class TaggerBridge:
    """
    AI タガーブリッジ。

    使い方:
        bridge = TaggerBridge(dictionary_manager=dm)

        # 外部タガーが起動していれば使用
        result = bridge.tag_image("http://example.com/image.jpg",
                                   model=TaggerModel.WD14)

        # タガー未起動でも辞書ベースで提案を返す
        result = bridge.suggest_from_context(["anime", "portrait"])
    """

    _TAGGER_ENDPOINTS = {
        TaggerModel.WD14:       "http://localhost:7860/tagger/v1/interrogate",
        TaggerModel.JOYCAPTION: "http://localhost:8080/caption",
        TaggerModel.FLORENCE2:  "http://localhost:8081/process",
    }

    def __init__(
        self,
        dictionary_manager: Any = None,
        tagger_endpoints: dict | None = None,
        timeout: int = 10,
    ) -> None:
        self._dm       = dictionary_manager
        self._timeout  = timeout
        self._endpoints = {**self._TAGGER_ENDPOINTS, **(tagger_endpoints or {})}

    # ── 外部タガー呼び出し ─────────────────────────────────────────

    def tag_image(
        self,
        image_url: str,
        model: TaggerModel = TaggerModel.WD14,
        threshold: float = 0.35,
    ) -> TaggerResult:
        """
        画像 URL を外部タガーに送り、タグリストを取得する。
        タガーが利用不可の場合はフォールバック提案を返す。
        """
        if model == TaggerModel.DICTIONARY:
            return self._dictionary_fallback([], "dictionary mode")

        endpoint = self._endpoints.get(model, "")
        if not endpoint:
            return TaggerResult(
                model=model, tags=[], success=False,
                error=f"Unknown model: {model}", source="fallback",
            )

        try:
            payload = json.dumps({"image": image_url,
                                  "model": model,
                                  "threshold": threshold}).encode()
            req = urllib.request.Request(
                endpoint, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                data = json.loads(r.read().decode())
            tags = self._normalize_tags(data, model)
            return TaggerResult(model=model, tags=tags, success=True,
                                raw_output=str(data)[:500], source="ai")
        except urllib.error.URLError:
            return self._dictionary_fallback(
                [], f"{model} tagger not running (URLError)"
            )
        except Exception as e:
            return self._dictionary_fallback([], str(e))

    def is_available(self, model: TaggerModel) -> bool:
        """タガーが利用可能か HTTP で確認する"""
        if model == TaggerModel.DICTIONARY:
            return True
        endpoint = self._endpoints.get(model, "").replace("/interrogate", "/info").replace("/caption", "/health").replace("/process", "/health")
        try:
            req = urllib.request.Request(endpoint, method="GET")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False

    def available_models(self) -> list[str]:
        """利用可能なモデル一覧を返す"""
        result = [TaggerModel.DICTIONARY]
        for m in [TaggerModel.WD14, TaggerModel.JOYCAPTION, TaggerModel.FLORENCE2]:
            if self.is_available(m):
                result.append(m)
        return [str(m) for m in result]

    # ── コンテキストベース提案（辞書・プロファイル） ────────────────

    def suggest_from_context(
        self,
        current_tags: list[str],
        n: int = 20,
        category_filter: str | None = None,
    ) -> TaggerResult:
        """
        現在のタグから辞書・カテゴリを使って次のタグを提案する。
        外部タガー不要（dictionary fallback）。
        """
        if not self._dm:
            return TaggerResult(
                model="dictionary", tags=[], success=False,
                error="DictionaryManager not available", source="fallback",
            )
        suggestions: list[dict[str, float]] = []
        seen = set(current_tags)

        # ① 現在タグのカテゴリから同カテゴリタグを提案
        categories: set[str] = set()
        for tag in current_tags[:5]:
            result = self._dm.lookup(tag)
            if result.found and result.category:
                categories.add(result.category)

        for cat in categories:
            try:
                entries = self._dm.search_by_category(cat, limit=20)
                for e in entries:
                    if e.key not in seen:
                        seen.add(e.key)
                        suggestions.append({
                            "tag": e.key,
                            "score": round(0.6 + e.weight * 0.1, 3),
                        })
            except Exception:
                pass

        # ② フィルタ適用
        if category_filter:
            suggestions = [s for s in suggestions
                           if self._get_category(s["tag"]) == category_filter]

        suggestions.sort(key=lambda x: -x["score"])
        return TaggerResult(
            model="dictionary",
            tags=suggestions[:n],
            success=True,
            source="dictionary",
        )

    # ── 内部ヘルパー ──────────────────────────────────────────────

    def _normalize_tags(self, data: Any, model: TaggerModel) -> list[dict[str, float]]:
        """各タガーのレスポンス形式を統一する"""
        tags: list[dict[str, float]] = []
        if model == TaggerModel.WD14:
            # WD14 形式: {"caption": {"tag1": score1, ...}}
            raw = data.get("caption", data) if isinstance(data, dict) else {}
            for tag, score in (raw.items() if isinstance(raw, dict) else []):
                tags.append({"tag": str(tag).lower().replace(" ", "_"),
                              "score": float(score)})
        elif model == TaggerModel.JOYCAPTION:
            # JoyCaption 形式: {"tags": ["tag1", "tag2", ...]}
            for tag in (data.get("tags", []) if isinstance(data, dict) else []):
                tags.append({"tag": str(tag).lower().replace(" ", "_"),
                              "score": 0.8})
        elif model == TaggerModel.FLORENCE2:
            # Florence2 形式: {"result": "tag1, tag2, ..."}
            raw_str = data.get("result", "") if isinstance(data, dict) else ""
            for tag in raw_str.split(","):
                tag = tag.strip().lower().replace(" ", "_")
                if tag:
                    tags.append({"tag": tag, "score": 0.75})
        tags.sort(key=lambda x: -x["score"])
        return tags[:100]

    def _dictionary_fallback(self, context: list[str], reason: str) -> TaggerResult:
        return TaggerResult(
            model="dictionary", tags=[], success=True,
            raw_output=f"Fallback: {reason}", source="fallback",
        )

    def _get_category(self, tag: str) -> str:
        if not self._dm:
            return ""
        try:
            return self._dm.lookup(tag).category or ""
        except Exception:
            return ""
