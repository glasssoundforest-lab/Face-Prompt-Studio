"""
pir_builder.py — Stage 4: PIR Builder

ASTNode を PIR の Concept / Constraint オブジェクトに変換する。
"""

import uuid
from typing import List
from models import ASTNode, Concept, Constraint, PIR


def build_pir(
    prompt:      List[ASTNode],
    negative:    List[ASTNode],
    constraints: List[ASTNode],
) -> PIR:
    concepts = [
        Concept(
            id=str(uuid.uuid4())[:8],
            name=n.category or n.value,
            value=n.value or n.category or "",
            weight=n.weight,
            token_type=n.token_type,
        )
        for n in prompt
    ]

    cons = [
        Constraint(type="negative", value=n.value, weight=n.weight)
        for n in negative
    ] + [
        Constraint(type=n.category or "constraint", value=n.value, weight=n.weight)
        for n in constraints
    ]

    return PIR(concepts=concepts, constraints=cons)
