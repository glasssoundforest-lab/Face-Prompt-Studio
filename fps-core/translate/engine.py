"""
fps-core/translate/engine.py — 日本語テキスト→タグ翻訳エンジン
★ v2.9 新設

外部API不要で動作する辞書ベースの日本語→英語タグ変換。

動作原理:
  1. 日本語辞書（japanese_tags.json）のエントリ名で前方一致検索
  2. 同義語（aliases）でもマッチング
  3. 外部翻訳API（LibreTranslate/DeepL）が設定されていれば補完

使い方:
    engine = TranslateEngine(dictionary_manager=dm)
    result = engine.translate("青い目の金髪の少女、笑顔、アニメ風")
    print(result.tags)
    # → ["blue_eyes", "blonde_hair", "1girl", "smile", "anime_style"]
"""
from __future__ import annotations

import re
import urllib.request
import urllib.error
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranslateResult:
    """翻訳結果"""
    original:    str
    tags:        list[str]              # 変換されたタグ（英語）
    unmapped:    list[str]              # 変換できなかった単語
    confidence:  float                  # 全体の変換率 0.0〜1.0
    method:      str                    # "dictionary" | "api" | "mixed"
    detail:      list[dict[str, Any]]   # 各単語の変換詳細

    def to_prompt(self, separator: str = ", ") -> str:
        return separator.join(self.tags)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original":   self.original,
            "tags":       self.tags,
            "unmapped":   self.unmapped,
            "confidence": round(self.confidence, 3),
            "method":     self.method,
            "prompt":     self.to_prompt(),
        }


class TranslateEngine:
    """
    日本語テキスト→英語タグ変換エンジン。

    優先順位:
      1. 辞書の日本語エントリ名 → 完全一致・前方一致
      2. 辞書の日本語エイリアス（synonyms）→ 完全一致
      3. 内蔵変換テーブル（頻出表現）
      4. 外部翻訳API（オプション）→ API 経由で翻訳後、辞書で検索
    """

    # ── 内蔵変換テーブル（辞書にない頻出表現） ──────────────────
    _BUILTIN: dict[str, str] = {
        # 品質
        "傑作":         "masterpiece",
        "最高品質":     "best_quality",
        "高品質":       "high_quality",
        "超詳細":       "ultra_detailed",
        # キャラクター
        "少女":         "1girl",
        "女の子":       "1girl",
        "男の子":       "1boy",
        "少年":         "1boy",
        "女性":         "1girl",
        "男性":         "1boy",
        "2人の少女":    "2girls",
        # 目の色
        "青い目":       "blue_eyes",
        "緑の目":       "green_eyes",
        "茶色の目":     "brown_eyes",
        "赤い目":       "red_eyes",
        "金色の目":     "gold_eyes",
        # 髪の色
        "金髪":         "blonde_hair",
        "黒髪":         "black_hair",
        "茶髪":         "brown_hair",
        "赤髪":         "red_hair",
        "銀髪":         "silver_hair",
        "白髪":         "white_hair",
        "青い髪":       "blue_hair",
        "ピンクの髪":   "pink_hair",
        # 髪型
        "ツインテール": "twintails",
        "ポニーテール": "ponytail",
        "ショートヘア": "short_hair",
        "ロングヘア":   "long_hair",
        # 表情
        "笑顔":         "smile",
        "笑っている":   "laughing",
        "泣いている":   "crying",
        "怒っている":   "angry",
        "恥ずかしい":   "blush",
        "驚いている":   "surprised",
        # スタイル
        "アニメ風":     "anime_style",
        "写実的":       "photorealistic",
        "水彩画":       "watercolor",
        "油絵":         "oil_painting",
        "イラスト":     "illustration",
        # ライティング
        "柔らかい光":   "soft_light",
        "逆光":         "backlight",
        "自然光":       "natural_light",
        "夕焼け":       "sunset",
        "夜":           "night",
        "昼":           "day",
        # 背景
        "白背景":       "white_background",
        "シンプルな背景": "simple_background",
        "屋外":         "outdoors",
        "屋内":         "indoors",
        "森":           "forest",
        "海":           "ocean",
        "空":           "sky",
        # 服装
        "制服":         "school_uniform",
        "スーツ":       "suit",
        "ドレス":       "dress",
        "着物":         "kimono",
        # カメラ
        "上半身":       "upper_body",
        "全身":         "full_body",
        "アップ":       "close-up",
        "横顔":         "profile",
        # その他
        "複数":         "multiple_girls",
        "かわいい":     "cute",
        "美しい":       "beautiful",
    }

    # 分割に使う日本語区切り文字
    _DELIMITERS = re.compile(r'[、。，,\s・]+')

    def __init__(
        self,
        dictionary_manager: Any = None,
        api_url:   str | None = None,  # LibreTranslate URL
        api_key:   str | None = None,
        timeout:   int = 5,
    ) -> None:
        self._dm      = dictionary_manager
        self._api_url = api_url
        self._api_key = api_key
        self._timeout = timeout
        # 辞書から日本語エントリのインデックスを構築
        self._jp_index: dict[str, str] = {}
        if self._dm:
            self._build_jp_index()

    def _build_jp_index(self) -> None:
        """辞書の日本語エントリをインデックス化する"""
        try:
            # japanese_tags.json から読み込み
            entries = getattr(self._dm, "_jp_entries", None)
            if entries is None:
                return
            for entry in entries:
                jp_name = entry.get("jp_name", "")
                eng_key = entry.get("key", "")
                if jp_name and eng_key:
                    self._jp_index[jp_name] = eng_key
                for alias in entry.get("aliases", []):
                    if alias:
                        self._jp_index[alias] = eng_key
        except Exception:
            pass

    def translate(
        self,
        text: str,
        max_tags: int = 30,
        use_api: bool = False,
    ) -> TranslateResult:
        """
        日本語テキストをタグリストに変換する。

        Args:
            text:     日本語テキスト（「青い目の金髪の少女」など）
            max_tags: 最大タグ数
            use_api:  外部翻訳API を使うか

        Returns:
            TranslateResult
        """
        if not text.strip():
            return TranslateResult(
                original=text, tags=[], unmapped=[],
                confidence=0.0, method="dictionary", detail=[],
            )

        # 入力を単語に分割
        words = [w.strip() for w in self._DELIMITERS.split(text) if w.strip()]
        tags: list[str]     = []
        unmapped: list[str] = []
        detail: list[dict]  = []
        seen: set[str]      = set()
        method = "dictionary"

        for word in words:
            tag, src = self._lookup(word)
            if tag and tag not in seen:
                seen.add(tag)
                tags.append(tag)
                detail.append({"word": word, "tag": tag, "source": src})
            elif not tag:
                # 部分一致を試みる（「青い目の」→「青い目」→ blue_eyes）
                sub_tag, sub_src = self._partial_lookup(word)
                if sub_tag and sub_tag not in seen:
                    seen.add(sub_tag)
                    tags.append(sub_tag)
                    detail.append({"word": word, "tag": sub_tag, "source": sub_src})
                else:
                    unmapped.append(word)

        # 外部APIで補完（オプション）
        if use_api and unmapped and self._api_url:
            api_tags, api_detail = self._translate_via_api(unmapped)
            for t, d in zip(api_tags, api_detail):
                if t not in seen:
                    seen.add(t)
                    tags.append(t)
            detail.extend(api_detail)
            # 変換できたものを unmapped から除外
            api_mapped = {d["word"] for d in api_detail if d.get("tag")}
            unmapped = [w for w in unmapped if w not in api_mapped]
            method = "mixed" if tags else "api"

        mapped = len(words) - len(unmapped)
        confidence = mapped / len(words) if words else 0.0

        return TranslateResult(
            original=text,
            tags=tags[:max_tags],
            unmapped=unmapped,
            confidence=confidence,
            method=method,
            detail=detail,
        )

    def translate_batch(
        self, texts: list[str], use_api: bool = False
    ) -> list[TranslateResult]:
        """複数テキストを一括変換する"""
        return [self.translate(t, use_api=use_api) for t in texts]

    def detect_language(self, text: str) -> str:
        """テキストの言語を簡易検出する（"ja" / "en" / "mixed" / "unknown"）"""
        if not text.strip():
            return "unknown"
        # 日本語文字（ひらがな・カタカナ・漢字）の比率
        jp_chars = sum(1 for c in text
                       if "぀" <= c <= "鿿" or "＀" <= c <= "￯")
        en_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        total    = jp_chars + en_chars
        if total == 0:
            return "unknown"
        jp_ratio = jp_chars / total
        if jp_ratio > 0.7:
            return "ja"
        elif jp_ratio < 0.2:
            return "en"
        return "mixed"

    # ── 内部処理 ──────────────────────────────────────────────────

    def _lookup(self, word: str) -> tuple[str, str]:
        """1単語を辞書・内蔵テーブルで検索する"""
        # 1. 内蔵テーブル（完全一致）
        if word in self._BUILTIN:
            return self._BUILTIN[word], "builtin"
        # 2. 辞書の日本語インデックス（完全一致）
        if word in self._jp_index:
            return self._jp_index[word], "dictionary"
        # 3. 辞書マネージャーの lookup（英語キーとして）
        if self._dm:
            try:
                result = self._dm.lookup(word)
                if result.found:
                    return result.resolved or word, "dictionary"
            except Exception:
                pass
        return "", ""

    def _partial_lookup(self, word: str) -> tuple[str, str]:
        """前方一致・後方一致で検索する"""
        # 内蔵テーブルの前方一致
        for jp, en in self._BUILTIN.items():
            if word.startswith(jp) or jp.startswith(word):
                if len(jp) >= 2:  # 1文字マッチは除外
                    return en, "builtin_partial"
        # 辞書インデックスの前方一致
        for jp, en in self._jp_index.items():
            if word.startswith(jp) or jp.startswith(word):
                if len(jp) >= 2:
                    return en, "dictionary_partial"
        return "", ""

    def _translate_via_api(
        self, words: list[str]
    ) -> tuple[list[str], list[dict]]:
        """外部翻訳API（LibreTranslate 互換）で翻訳して辞書で検索する"""
        tags: list[str] = []
        detail: list[dict] = []
        text = "、".join(words)
        try:
            payload = json.dumps({
                "q": text, "source": "ja", "target": "en",
                "format": "text",
                **({"api_key": self._api_key} if self._api_key else {}),
            }).encode()
            req = urllib.request.Request(
                f"{self._api_url.rstrip('/')}/translate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                data = json.loads(r.read().decode())
            translated = data.get("translatedText", "")
            # 翻訳結果をタグとして処理
            en_words = [w.strip().lower().replace(" ", "_")
                        for w in re.split(r"[,、\s]+", translated) if w.strip()]
            for i, (orig, en) in enumerate(zip(words, en_words)):
                if en:
                    detail.append({"word": orig, "tag": en, "source": "api"})
                    tags.append(en)
        except Exception:
            pass
        return tags, detail
