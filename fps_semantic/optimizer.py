"""
optimizer.py — Stage 6: Optimizer

未解決コンセプトの除去と重複排除を行う。
"""

from models import PIR


def optimize(pir: PIR) -> PIR:
    seen: set[str] = set()
    filtered = []

    for c in pir.concepts:
        if not c.resolved:
            continue
        if c.resolved in seen:
            continue
        seen.add(c.resolved)
        filtered.append(c)

    pir.concepts = filtered
    return pir
