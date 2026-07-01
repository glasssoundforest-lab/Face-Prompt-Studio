"""
fps-core/cache/key_builder.py — キャッシュキー生成ユーティリティ

再現性のある一意キーを生成するヘルパー群。
"""

from __future__ import annotations

import hashlib
import json
import re


def build_key(namespace: str, *args: object, **kwargs: object) -> str:
    """
    名前空間 + 引数から決定論的なキャッシュキーを生成する。

    Args:
        namespace: キーの名前空間（例: "lookup", "prompt"）
        *args:     任意の位置引数
        **kwargs:  任意のキーワード引数

    Returns:
        "namespace:sha256[:8]" 形式のキー
    """
    payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{namespace}:{digest}"


def build_prompt_key(prompt: str) -> str:
    """
    プロンプト文字列用キャッシュキー。
    余分な空白を正規化して同一視する。

    Args:
        prompt: プロンプト文字列

    Returns:
        "prompt:sha256" 形式のキー
    """
    normalized = re.sub(r"\s+", " ", prompt.strip())
    return build_key("prompt", normalized)


def build_lookup_key(tag: str) -> str:
    """
    辞書ルックアップ用キャッシュキー。
    大文字小文字を正規化して同一視する。

    Args:
        tag: タグ文字列

    Returns:
        "lookup:sha256" 形式のキー
    """
    return build_key("lookup", tag.lower().strip())
