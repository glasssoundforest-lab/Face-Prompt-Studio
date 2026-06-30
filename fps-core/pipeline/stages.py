"""
fps-core/pipeline/stages.py — 10ステージ実装

Stage 1 : Parser          DSL 構文解析
Stage 2 : Normalizer      表記揺れ統一
Stage 3 : DuplicateCleaner 重複除去
Stage 4 : Blacklist       禁止タグフィルタ
Stage 5 : Whitelist       許可タグのみ通過（モード切替式）
Stage 6 : Categorizer     DictionaryManager でカテゴリ付与
Stage 7 : RuleEngine      RuleManager でルール適用
Stage 8 : WeightEngine    重み正規化
Stage 9 : Optimizer       最終最適化・ソート
Stage 10: Exporter        アダプター向けフォーマット変換
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from .models import StageResult, StageStatus, TagEntry

# ══════════════════════════════════════════════════════════════════
# Base Stage
# ══════════════════════════════════════════════════════════════════


class BaseStage(ABC):
    """パイプラインステージの基底クラス"""

    name: str = "base"

    def __init__(self, enabled: bool = True, **kwargs: Any) -> None:
        self.enabled = enabled
        self._kwargs = kwargs

    def run(
        self,
        tags: list[TagEntry],
        context: dict[str, Any],
    ) -> tuple[list[TagEntry], StageResult]:
        if not self.enabled:
            return tags, StageResult(
                stage=self.name, status=StageStatus.SKIPPED, tags_in=len(tags), tags_out=len(tags)
            )
        try:
            result_tags = self.process(tags, context)
            return result_tags, StageResult(
                stage=self.name,
                status=StageStatus.DONE,
                tags_in=len(tags),
                tags_out=len(result_tags),
            )
        except Exception as e:
            return tags, StageResult(
                stage=self.name,
                status=StageStatus.ERROR,
                tags_in=len(tags),
                error=str(e),
            )

    @abstractmethod
    def process(
        self,
        tags: list[TagEntry],
        context: dict[str, Any],
    ) -> list[TagEntry]: ...


# ══════════════════════════════════════════════════════════════════
# Stage 1: Parser
# ══════════════════════════════════════════════════════════════════

_CAT_WEIGHT = re.compile(r"^\(([^:]+):([^:]+)(?::([0-9.]+))?\)$")
_NEGATIVE = re.compile(r"^\[(.+)\]$")
_CONSTRAINT = re.compile(r"^\{([^:]+):(.+)\}$")
_PLAIN_PAREN = re.compile(r"^\(([^:]+)\)$")


class ParserStage(BaseStage):
    """Stage 1: DSL テキスト → TagEntry リスト"""

    name = "parser"

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        src = context.get("input", "")
        result: list[TagEntry] = []

        for token in _tokenize(src):
            token = token.strip()
            if not token:
                continue

            # (category:value:weight) or (category:value)
            m = _CAT_WEIGHT.match(token)
            if m:
                cat, val, w = m.groups()
                result.append(
                    TagEntry(
                        tag=val.strip().lower().replace(" ", "_"),
                        category=cat.strip().lower(),
                        weight=float(w) if w else 1.0,
                    )
                )
                continue

            # [negative]
            m = _NEGATIVE.match(token)
            if m:
                result.append(
                    TagEntry(
                        tag=m.group(1).strip().lower().replace(" ", "_"),
                        category="negative",
                        negative=True,
                    )
                )
                continue

            # {constraint:value} → plain tag
            m = _CONSTRAINT.match(token)
            if m:
                result.append(
                    TagEntry(
                        tag=m.group(2).strip().lower().replace(" ", "_"),
                        category=m.group(1).strip().lower(),
                    )
                )
                continue

            # (plain) — コロンなし括弧はプレーンにフォールバック
            m = _PLAIN_PAREN.match(token)
            if m:
                result.append(
                    TagEntry(
                        tag=m.group(1).strip().lower().replace(" ", "_"),
                        category="",
                    )
                )
                continue

            # plain word
            result.append(
                TagEntry(
                    tag=token.lower().replace(" ", "_"),
                    category="",
                )
            )

        return result


def _tokenize(src: str) -> list[str]:
    """括弧・カンマを考慮してトークン分割する"""
    tokens: list[str] = []
    i = depth = 0
    start = 0
    openers = {"(": ")", "[": "]", "{": "}"}
    closers = set(openers.values())

    while i < len(src):
        ch = src[i]
        if ch in openers:
            depth += 1
        elif ch in closers:
            depth -= 1
        elif ch == "," and depth == 0:
            t = src[start:i].strip()
            if t:
                tokens.append(t)
            start = i + 1
        i += 1

    t = src[start:].strip()
    if t:
        tokens.append(t)
    return tokens


# ══════════════════════════════════════════════════════════════════
# Stage 2: Normalizer
# ══════════════════════════════════════════════════════════════════


class NormalizerStage(BaseStage):
    """Stage 2: 表記揺れ統一"""

    name = "normalizer"

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        for t in tags:
            t.tag = t.tag.strip().lower().replace("-", "_").replace(" ", "_")
        return tags


# ══════════════════════════════════════════════════════════════════
# Stage 3: DuplicateCleaner
# ══════════════════════════════════════════════════════════════════


class DuplicateCleanerStage(BaseStage):
    """Stage 3: 重複タグを除去する（後勝ち）"""

    name = "duplicate_cleaner"

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        seen: dict[str, TagEntry] = {}
        for t in tags:
            seen[t.tag] = t  # 後勝ち
        return list(seen.values())


# ══════════════════════════════════════════════════════════════════
# Stage 4: Blacklist
# ══════════════════════════════════════════════════════════════════


class BlacklistStage(BaseStage):
    """Stage 4: 禁止タグを除去する"""

    name = "blacklist"

    def __init__(self, blacklist: set[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._blacklist: set[str] = blacklist or set()

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        bl = self._blacklist | set(context.get("blacklist", []))
        return [t for t in tags if t.tag not in bl]


# ══════════════════════════════════════════════════════════════════
# Stage 5: Whitelist
# ══════════════════════════════════════════════════════════════════


class WhitelistStage(BaseStage):
    """Stage 5: ホワイトリストモード時は許可タグのみ通過"""

    name = "whitelist"

    def __init__(self, whitelist: set[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._whitelist: set[str] = whitelist or set()

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        wl = self._whitelist | set(context.get("whitelist", []))
        if not wl:
            return tags  # ホワイトリストが空なら全通過
        return [t for t in tags if t.tag in wl]


# ══════════════════════════════════════════════════════════════════
# Stage 6: Categorizer
# ══════════════════════════════════════════════════════════════════


class CategorizerStage(BaseStage):
    """Stage 6: DictionaryManager でカテゴリ・resolved を付与する"""

    name = "categorizer"

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        dm = context.get("dictionary_manager")
        if not dm:
            return tags

        for t in tags:
            if t.negative:
                continue
            result = dm.lookup(t.tag)
            if result.found and result.entry:
                if not t.category:
                    t.category = result.entry.category
                # resolved を meta に保存
                t.meta["resolved"] = result.resolved
                if t.weight == 1.0 and result.weight != 1.0:
                    t.weight = result.weight
        return tags


# ══════════════════════════════════════════════════════════════════
# Stage 7: RuleEngine
# ══════════════════════════════════════════════════════════════════


class RuleEngineStage(BaseStage):
    """Stage 7: RuleManager でルールを適用する"""

    name = "rule_engine"

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        rm = context.get("rule_manager")
        if not rm:
            return tags

        tag_dicts = [t.to_dict() for t in tags if not t.negative]
        applied, rule_results = rm.apply(tag_dicts)

        # 適用結果を context に記録（デバッグ用）
        context["applied_rule_results"] = rule_results

        # 結果を TagEntry に戻す
        neg_tags = [t for t in tags if t.negative]
        result = [
            TagEntry(
                tag=d["tag"],
                category=d.get("category", ""),
                weight=d.get("weight", 1.0),
                negative=False,
            )
            for d in applied
        ]
        return result + neg_tags


# ══════════════════════════════════════════════════════════════════
# Stage 8: WeightEngine
# ══════════════════════════════════════════════════════════════════


class WeightEngineStage(BaseStage):
    """
    Stage 8: 重みを正規化する。

    処理順序:
      1. context["category_weight_table"] があればカテゴリ別重み倍率を適用
      2. 0.01〜max_weight の範囲にクランプ
    """

    name = "weight_engine"

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        max_weight = float(context.get("max_weight", 3.0))
        table = context.get("category_weight_table")
        preset = context.get("weight_preset")

        for t in tags:
            if table is not None and t.category:
                scale = table.get_weight(t.category, preset=preset)
                t.weight = round(t.weight * scale, 3)
            t.weight = max(0.01, min(t.weight, max_weight))
        return tags


# ══════════════════════════════════════════════════════════════════
# Stage 9: Optimizer
# ══════════════════════════════════════════════════════════════════


class OptimizerStage(BaseStage):
    """Stage 9: 重み降順でソート・空タグを除去"""

    name = "optimizer"

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        # 空タグを除去
        tags = [t for t in tags if t.tag]
        # ネガティブと通常タグを分離してそれぞれ重み降順にソート
        pos = sorted([t for t in tags if not t.negative], key=lambda t: t.weight, reverse=True)
        neg = sorted([t for t in tags if t.negative], key=lambda t: t.weight, reverse=True)
        return pos + neg


# ══════════════════════════════════════════════════════════════════
# Stage 10: Exporter
# ══════════════════════════════════════════════════════════════════


class ExporterStage(BaseStage):
    """Stage 10: アダプター向けのフォーマットに変換する"""

    name = "exporter"

    def process(self, tags: list[TagEntry], context: dict[str, Any]) -> list[TagEntry]:
        # context に出力を書き込む（タグリスト自体は変更しない）
        pos = [t for t in tags if not t.negative]
        neg = [t for t in tags if t.negative]

        def _fmt(t: TagEntry) -> str:
            resolved = t.meta.get("resolved") or t.tag
            if t.weight != 1.0:
                return f"{resolved}:{t.weight:.1f}"
            return resolved

        context["output_prompt"] = ", ".join(_fmt(t) for t in pos)
        context["output_negative"] = ", ".join(t.tag for t in neg)
        context["output_tags"] = [t.to_dict() for t in pos]
        context["output_neg_tags"] = [t.to_dict() for t in neg]
        return tags
