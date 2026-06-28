"""
resolver.py — Stage 5: Semantic Resolver

コンセプトをリゾルバーマップで正規化する。

- cat トークン: (category:value) → Category.Value 形式に直接変換
  リゾルバーマップに依存しないため未定義語の消失を回避できる。
- plain トークン: リゾルバーマップで解決。未定義の場合 resolved=None。
"""

from typing import Optional
from models import PIR


RESOLVER_MAP: dict[str, str] = {
    "masterpiece":  "Quality.High",
    "quality":      "Quality",
    "high":         "Quality.High",
    "medium":       "Quality.Medium",
    "low":          "Quality.Low",
    "blue":         "Eyes.Blue",
    "green":        "Eyes.Green",
    "brown":        "Eyes.Brown",
    "red":          "Eyes.Red",
    "eyes":         "Eyes.Generic",
    "hair":         "Hair.Generic",
    "long":         "Hair.Long",
    "short":        "Hair.Short",
    "blonde":       "Hair.Blonde",
    "smile":        "Expression.Smile",
    "sad":          "Expression.Sad",
    "anime":        "Style.Anime",
    "realistic":    "Style.Realistic",
    "fantasy":      "Style.Fantasy",
}


def resolve_key(key: str) -> Optional[str]:
    normalized = key.lower().replace(" ", "_")
    return RESOLVER_MAP.get(normalized) or RESOLVER_MAP.get(key.lower())


def resolve(pir: PIR) -> PIR:
    for c in pir.concepts:
        if c.token_type == "cat":
            # (category:value) → Category.Value に直接変換
            val = c.value.capitalize() if c.value else ""
            c.resolved = f"{c.name}.{val}" if val else c.name
        else:
            # plain: リゾルバーマップで解決
            c.resolved = resolve_key(c.name) or resolve_key(c.value) or None
    return pir
