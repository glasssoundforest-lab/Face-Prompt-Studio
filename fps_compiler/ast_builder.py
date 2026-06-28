"""
ast_builder.py — Stage 3: AST Builder

ASTNode を prompt / negative / constraints の3系統に分離する。
"""

from typing import List, Tuple
from models import ASTNode


def build_ast(
    nodes: List[ASTNode],
) -> Tuple[List[ASTNode], List[ASTNode], List[ASTNode]]:
    prompt:      List[ASTNode] = []
    negative:    List[ASTNode] = []
    constraints: List[ASTNode] = []

    for n in nodes:
        if n.token_type == "neg":
            negative.append(n)
        elif n.token_type == "con":
            constraints.append(n)
        else:
            prompt.append(n)

    return prompt, negative, constraints
