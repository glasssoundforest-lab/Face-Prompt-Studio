"""
tokenizer.py — Stage 2: Tokenizer

LexToken を型付き ASTNode に変換する。
cat トークンは category / value / weight に分解する。
"""

from typing import List
from models import LexToken, ASTNode


def tokenizer(tokens: List[LexToken]) -> List[ASTNode]:
    nodes: List[ASTNode] = []

    for t in tokens:
        if t.token_type == "error":
            continue

        if t.token_type == "cat":
            parts = [p.strip() for p in t.inner.split(':')]
            category = parts[0] if len(parts) > 0 else ""
            value    = parts[1] if len(parts) > 1 else ""
            try:
                weight = float(parts[2]) if len(parts) > 2 else 1.0
            except ValueError:
                weight = 1.0
            nodes.append(ASTNode(
                token_type="cat",
                category=category,
                value=value,
                weight=weight,
                raw=t.raw,
            ))

        elif t.token_type == "neg":
            nodes.append(ASTNode(
                token_type="neg",
                category=None,
                value=t.inner,
                weight=1.0,
                raw=t.raw,
            ))

        elif t.token_type == "con":
            parts = [p.strip() for p in t.inner.split(':')]
            category = parts[0] if len(parts) > 0 else "constraint"
            value    = parts[1] if len(parts) > 1 else ""
            nodes.append(ASTNode(
                token_type="con",
                category=category,
                value=value,
                weight=1.0,
                raw=t.raw,
            ))

        else:  # plain
            nodes.append(ASTNode(
                token_type="plain",
                category=None,
                value=t.inner.strip(),
                weight=1.0,
                raw=t.raw,
            ))

    return nodes
