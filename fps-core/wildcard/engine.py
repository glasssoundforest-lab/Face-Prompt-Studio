"""
fps-core/wildcard/engine.py — Wildcard 展開エンジン
★ v2.6 新設

サポートする構文:
  __wildcard__         → fps-data/wildcards/{wildcard}.txt からランダム選択
  [[A|B|C]]            → A/B/C のいずれかをランダム選択（重み付き可能）
  [[A|B|C]]:n          → n 件をランダム選択して結合
  {{var:default}}      → 変数展開（variables 辞書が必要）
  {A|B|C}              → A1111 互換ランダム選択

依存: 標準ライブラリのみ（random / re）
"""
from __future__ import annotations

import random
import re
from typing import Any


class WildcardEngine:
    """
    Wildcard 展開エンジン。

    使い方:
        engine = WildcardEngine(wildcard_manager=wm)
        result = engine.expand("__style__, [[blue|green|red]] eyes, {{quality:best_quality}}")
        # → "anime_style, blue eyes, best_quality"

    seed を指定すると再現性のある展開が可能:
        engine.seed(42)
        result1 = engine.expand("[[A|B|C]]")  # 常に同じ結果
    """

    # 構文パターン
    _RE_WILDCARD    = re.compile(r'__([a-zA-Z0-9_/]+)__')
    _RE_INLINE      = re.compile(r'\[\[(.+?)\]\](?::(\d+))?')
    _RE_VARIABLE    = re.compile(r'\{\{(\w+)(?::([^}]*))?\}\}')
    _RE_A1111       = re.compile(r'\{([^{}]+)\}')

    def __init__(
        self,
        wildcard_manager: Any = None,
        seed: int | None = None,
    ) -> None:
        self._wm  = wildcard_manager
        self._rng = random.Random(seed)

    def seed(self, seed: int) -> None:
        """シードを設定して再現性を確保する"""
        self._rng.seed(seed)

    def expand(
        self,
        prompt: str,
        variables: dict[str, str] | None = None,
        max_passes: int = 5,
    ) -> str:
        """
        プロンプト内の Wildcard 構文をすべて展開する。

        Args:
            prompt:    展開対象のプロンプト
            variables: {{var}} 置換用変数辞書
            max_passes: ネスト展開の最大パス数

        Returns:
            展開済みプロンプト
        """
        text = prompt
        for _ in range(max_passes):
            prev = text
            text = self._expand_variables(text, variables or {})
            text = self._expand_wildcards(text)
            text = self._expand_inline(text)
            text = self._expand_a1111(text)
            if text == prev:
                break
        return text

    def preview_expand(
        self,
        prompt: str,
        n: int = 5,
        seed: int | None = None,
    ) -> list[str]:
        """
        同じプロンプトを n 回展開して候補リストを返す。

        Args:
            prompt: 展開対象
            n:      生成件数
            seed:   シード（指定時は再現性あり）

        Returns:
            n 件の展開結果リスト
        """
        results = []
        for i in range(n):
            s = (seed + i) if seed is not None else None
            engine = WildcardEngine(wildcard_manager=self._wm, seed=s)
            results.append(engine.expand(prompt))
        return results

    def extract_wildcards(self, prompt: str) -> list[str]:
        """プロンプト内で使われている Wildcard キー一覧を返す"""
        return self._RE_WILDCARD.findall(prompt)

    # ── 内部展開処理 ──────────────────────────────────────────────

    def _expand_wildcards(self, text: str) -> str:
        """__key__ → WildcardManager から値を取得"""
        def replace(m: re.Match) -> str:
            key = m.group(1)
            if self._wm:
                values = self._wm.get_values(key)
                if values:
                    return self._rng.choice(values)
            return m.group(0)  # 変換できなければそのまま
        return self._RE_WILDCARD.sub(replace, text)

    def _expand_inline(self, text: str) -> str:
        """[[A|B|C]] または [[A:2|B:1|C:3]] を展開"""
        def replace(m: re.Match) -> str:
            inner = m.group(1)
            n_str = m.group(2)      # [[.....]]:n の n
            n = int(n_str) if n_str else 1

            items = []
            weights = []
            for part in inner.split("|"):
                part = part.strip()
                # weight 付き書式: "value:2.0"
                if ":" in part and not part.startswith("http"):
                    val, *wt_parts = part.rsplit(":", 1)
                    try:
                        wt = float(wt_parts[0])
                        items.append(val.strip())
                        weights.append(wt)
                    except ValueError:
                        items.append(part)
                        weights.append(1.0)
                else:
                    items.append(part)
                    weights.append(1.0)

            if n == 1:
                chosen = self._rng.choices(items, weights=weights, k=1)[0]
                return chosen
            else:
                # n 件非復元抽出（n > len なら復元あり）
                if n <= len(items):
                    indices = list(range(len(items)))
                    chosen_idx = self._rng.choices(
                        indices, weights=weights, k=n
                    )
                    # 重複除去しつつ順序保持
                    seen: set[int] = set()
                    picked = []
                    for idx in chosen_idx:
                        if idx not in seen:
                            seen.add(idx)
                            picked.append(items[idx])
                    return ", ".join(picked)
                else:
                    return ", ".join(self._rng.choices(items, weights=weights, k=n))

        return self._RE_INLINE.sub(replace, text)

    def _expand_variables(self, text: str, variables: dict[str, str]) -> str:
        """{{var:default}} → variables[var] または default"""
        def replace(m: re.Match) -> str:
            key     = m.group(1)
            default = m.group(2) or ""
            return variables.get(key, default)
        return self._RE_VARIABLE.sub(replace, text)

    def _expand_a1111(self, text: str) -> str:
        """{A|B|C} → A1111 互換ランダム選択"""
        def replace(m: re.Match) -> str:
            items = [p.strip() for p in m.group(1).split("|")]
            return self._rng.choice(items) if items else ""
        return self._RE_A1111.sub(replace, text)
