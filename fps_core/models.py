"""
models.py — 共通データクラス定義
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LexToken:
    raw: str
    token_type: str     # "cat" | "neg" | "con" | "plain" | "error"
    inner: str = ""
    error_msg: str = ""


@dataclass
class ASTNode:
    token_type: str     # "cat" | "neg" | "con" | "plain"
    category: Optional[str]
    value: str
    weight: float = 1.0
    raw: str = ""


@dataclass
class Concept:
    id: str
    name: str
    value: str
    weight: float = 1.0
    resolved: Optional[str] = None
    token_type: str = "plain"   # "cat" | "plain"


@dataclass
class Constraint:
    type: str           # "negative" | カテゴリ名
    value: str
    weight: float = 1.0


@dataclass
class PIR:
    concepts: List[Concept] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)


@dataclass
class ComfyUIOutput:
    prompt: str
    negative_prompt: str
    constraints: List[str]
