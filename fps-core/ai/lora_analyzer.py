"""
fps-core/ai/lora_analyzer.py — LoRA メタデータ分析・タグ候補生成
★ v2.5 新設

SafeTensors / CivitAI メタデータから LoRA のトリガーワード・
学習タグを抽出し、辞書候補として登録する。

依存:
  標準ライブラリのみ（struct / json）。
  torch / safetensors は不要（メタデータのみ読む）。
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LoraTagCandidate:
    """LoRA から抽出したタグ候補"""
    tag:         str
    source:      str          # "trigger" | "training" | "description" | "manual"
    confidence:  float = 1.0  # 0.0〜1.0
    category:    str   = ""
    weight:      float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag":        self.tag,
            "source":     self.source,
            "confidence": round(self.confidence, 3),
            "category":   self.category,
            "weight":     self.weight,
        }


@dataclass
class LoraInfo:
    """LoRA ファイルの分析結果"""
    file_path:    str
    file_name:    str
    model_name:   str = ""
    base_model:   str = ""
    description:  str = ""
    trigger_words: list[str] = field(default_factory=list)
    training_tags: list[str] = field(default_factory=list)
    tag_candidates: list[LoraTagCandidate] = field(default_factory=list)
    metadata_raw:  dict = field(default_factory=dict)
    error:        str = ""
    success:      bool = True

    @property
    def total_tags(self) -> int:
        return len(self.tag_candidates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name":    self.file_name,
            "model_name":   self.model_name,
            "base_model":   self.base_model,
            "description":  self.description,
            "trigger_words": self.trigger_words,
            "training_tags": self.training_tags,
            "total_tags":   self.total_tags,
            "error":        self.error,
            "success":      self.success,
            "tag_candidates": [t.to_dict() for t in self.tag_candidates],
        }


class LoraAnalyzer:
    """
    LoRA ファイル分析クラス。

    SafeTensors ファイルのメタデータ JSON を読み取り、
    トリガーワード・学習タグを抽出する。
    torch / safetensors ライブラリ不要（メタデータのみ解析）。

    使い方:
        analyzer = LoraAnalyzer()
        info = analyzer.analyze("/path/to/my_lora.safetensors")
        for tag in info.tag_candidates:
            print(tag.tag, tag.source)
    """

    # よく使われる LoRA メタデータキー
    _TRIGGER_KEYS = [
        "ss_tag_frequency", "trigger_words", "trigger_phrase",
        "activation_text", "activator_word", "training_comment",
    ]
    _MODEL_KEYS   = ["ss_base_model_version", "modelspec.architecture",
                     "ss_sd_model_name"]
    _DESC_KEYS    = ["description", "notes", "comment", "modelspec.description"]
    _NAME_KEYS    = ["name", "modelspec.title", "ss_output_name"]

    def __init__(self, dictionary_manager: Any = None) -> None:
        """
        Args:
            dictionary_manager: DictionaryManager インスタンス（省略可）。
                                 提供されると抽出タグの辞書引きを行う。
        """
        self._dm = dictionary_manager

    # ── 公開 API ──────────────────────────────────────────────────

    def analyze(self, file_path: str | Path) -> LoraInfo:
        """
        SafeTensors ファイルを分析して LoraInfo を返す。

        Args:
            file_path: .safetensors ファイルのパス

        Returns:
            LoraInfo（エラー時も success=False で返す）
        """
        path = Path(file_path)
        info = LoraInfo(
            file_path=str(path),
            file_name=path.name,
        )

        if not path.exists():
            info.error = f"ファイルが見つかりません: {path}"
            info.success = False
            return info

        try:
            meta = self._read_safetensors_metadata(path)
            info.metadata_raw = meta
            self._extract_info(info, meta)
            self._build_candidates(info)
        except Exception as e:
            info.error = f"分析エラー: {e}"
            info.success = False

        return info

    def analyze_from_metadata(
        self, metadata: dict, file_name: str = "unknown.safetensors"
    ) -> LoraInfo:
        """
        メタデータ辞書から直接 LoraInfo を生成する（ファイル不要）。
        CivitAI API レスポンス等に使用。
        """
        info = LoraInfo(
            file_path="",
            file_name=file_name,
            metadata_raw=metadata,
        )
        self._extract_info(info, metadata)
        self._build_candidates(info)
        return info

    def register_to_dictionary(
        self,
        info: LoraInfo,
        dictionary_manager: Any,
        category: str = "lora",
        overwrite: bool = False,
    ) -> int:
        """
        抽出したタグ候補を DictionaryManager に登録する。

        Returns:
            登録したタグ数
        """
        count = 0
        for cand in info.tag_candidates:
            if cand.confidence < 0.5:
                continue
            try:
                existing = dictionary_manager.lookup(cand.tag)
                if existing.found and not overwrite:
                    continue
                dictionary_manager.add_user_entry(
                    key=cand.tag,
                    resolved=cand.tag.replace("_", " "),
                    category=category,
                    aliases=[],
                    weight=cand.weight,
                )
                count += 1
            except Exception:
                pass
        return count

    # ── 内部処理 ──────────────────────────────────────────────────

    @staticmethod
    def _read_safetensors_metadata(path: Path) -> dict:
        """
        SafeTensors ファイルのヘッダーからメタデータを読み取る。

        SafeTensors 形式:
          [8バイト: ヘッダーサイズ (little-endian uint64)]
          [ヘッダーサイズ バイト: JSON]
          [テンソルデータ]
        """
        with open(path, "rb") as f:
            header_size_bytes = f.read(8)
            if len(header_size_bytes) < 8:
                return {}
            header_size = struct.unpack("<Q", header_size_bytes)[0]
            if header_size > 100 * 1024 * 1024:  # 100MB 超はスキップ
                return {}
            header_bytes = f.read(header_size)
        try:
            header = json.loads(header_bytes.decode("utf-8"))
            return header.get("__metadata__", {})
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _extract_info(self, info: LoraInfo, meta: dict) -> None:
        """メタデータから基本情報を抽出"""
        # モデル名
        for key in self._NAME_KEYS:
            if meta.get(key):
                info.model_name = str(meta[key])
                break

        # ベースモデル
        for key in self._MODEL_KEYS:
            if meta.get(key):
                info.base_model = str(meta[key])
                break

        # 説明文
        for key in self._DESC_KEYS:
            if meta.get(key):
                info.description = str(meta[key])[:500]
                break

        # トリガーワード
        triggers: list[str] = []
        for key in self._TRIGGER_KEYS:
            val = meta.get(key, "")
            if not val:
                continue
            if isinstance(val, str):
                # JSON 文字列の可能性あり
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        # ss_tag_frequency 形式: {"tag": count, ...}
                        tags = sorted(parsed.items(), key=lambda x: -x[1])
                        triggers.extend([t for t, _ in tags[:50]])
                    elif isinstance(parsed, list):
                        triggers.extend([str(t) for t in parsed])
                except (json.JSONDecodeError, ValueError):
                    # カンマ区切りまたはスペース区切り
                    for sep in [",", " ", ";"]:
                        parts = [p.strip() for p in val.split(sep) if p.strip()]
                        if len(parts) > 1:
                            triggers.extend(parts[:50])
                            break
                    else:
                        if val.strip():
                            triggers.append(val.strip())
            elif isinstance(val, (list, tuple)):
                triggers.extend([str(t) for t in val])
            elif isinstance(val, dict):
                tags = sorted(val.items(), key=lambda x: -x[1])
                triggers.extend([t for t, _ in tags[:50]])

        info.trigger_words = list(dict.fromkeys(
            t.strip().lower().replace(" ", "_")
            for t in triggers if t.strip()
        ))[:50]

        # ss_dataset_dirs, ss_caption_dropout_rate などからの学習タグ
        training_str = meta.get("ss_tag_frequency", "")
        if training_str and isinstance(training_str, str):
            try:
                tag_freq = json.loads(training_str)
                if isinstance(tag_freq, dict):
                    # {"category": {"tag": count}} 形式
                    for cat_val in tag_freq.values():
                        if isinstance(cat_val, dict):
                            sorted_tags = sorted(cat_val.items(), key=lambda x: -x[1])
                            info.training_tags.extend([t for t, _ in sorted_tags[:30]])
            except (json.JSONDecodeError, ValueError):
                pass

        info.training_tags = list(dict.fromkeys(
            t.strip().lower().replace(" ", "_")
            for t in info.training_tags if t.strip()
        ))[:100]

    def _build_candidates(self, info: LoraInfo) -> None:
        """タグ候補リストを構築する"""
        seen: set[str] = set()

        # トリガーワード（信頼度高い）
        for tag in info.trigger_words:
            if tag not in seen:
                seen.add(tag)
                cat = self._lookup_category(tag)
                info.tag_candidates.append(LoraTagCandidate(
                    tag=tag, source="trigger",
                    confidence=0.95, category=cat, weight=1.2,
                ))

        # 学習タグ（信頼度中程度）
        for tag in info.training_tags[:50]:
            if tag not in seen:
                seen.add(tag)
                cat = self._lookup_category(tag)
                info.tag_candidates.append(LoraTagCandidate(
                    tag=tag, source="training",
                    confidence=0.70, category=cat, weight=1.0,
                ))

        # 説明文からタグを抽出（信頼度低い）
        if info.description:
            desc_tags = self._extract_tags_from_text(info.description)
            for tag in desc_tags:
                if tag not in seen:
                    seen.add(tag)
                    info.tag_candidates.append(LoraTagCandidate(
                        tag=tag, source="description",
                        confidence=0.40, category="", weight=1.0,
                    ))

    def _lookup_category(self, tag: str) -> str:
        """辞書マネージャーでカテゴリを検索する"""
        if self._dm is None:
            return ""
        try:
            result = self._dm.lookup(tag)
            return result.category or ""
        except Exception:
            return ""

    @staticmethod
    def _extract_tags_from_text(text: str) -> list[str]:
        """説明文からタグっぽい単語を抽出する"""
        import re
        # アンダースコアで繋がれた単語、または括弧内の単語
        patterns = [
            r'([a-z][a-z0-9_]{2,30})',
        ]
        candidates: list[str] = []
        for pat in patterns:
            for m in re.finditer(pat, text.lower()):
                word = m.group(1)
                if "_" in word or len(word) >= 5:
                    candidates.append(word)
        return list(dict.fromkeys(candidates))[:20]
