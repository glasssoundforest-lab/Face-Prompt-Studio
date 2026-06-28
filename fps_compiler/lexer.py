"""
lexer.py — Stage 1: Lexer

文字列を構文トークンに分割する。

構文規則:
  (category:value)        カテゴリ指定     → token_type="cat"
  (category:value:1.5)    重み付き          → token_type="cat"
  (word)                  コロンなし        → token_type="plain" ★修正点
  [tag]                   ネガティブ        → token_type="neg"
  {category:value}        制約              → token_type="con"
  word                    プレーンテキスト  → token_type="plain"
"""

from typing import List
from models import LexToken


def lexer(src: str) -> List[LexToken]:
    tokens: List[LexToken] = []
    i = 0

    while i < len(src):
        ch = src[i]

        # 区切り文字はスキップ
        if ch in (' ', '\t', '\n', ','):
            i += 1
            continue

        # ( ... ) — カテゴリ指定 または plain フォールバック
        if ch == '(':
            j = src.find(')', i)
            if j == -1:
                tokens.append(LexToken(
                    raw=src[i:],
                    token_type="error",
                    error_msg="閉じ括弧 ')' がありません",
                ))
                break
            inner = src[i + 1:j]
            # ★ コロンを含む場合のみ "cat"、含まない場合は "plain" にフォールバック
            if ':' in inner:
                tokens.append(LexToken(
                    raw=src[i:j + 1],
                    token_type="cat",
                    inner=inner,
                ))
            else:
                tokens.append(LexToken(
                    raw=src[i:j + 1],
                    token_type="plain",
                    inner=inner.strip(),
                ))
            i = j + 1

        # [ ... ] — ネガティブ
        elif ch == '[':
            j = src.find(']', i)
            if j == -1:
                tokens.append(LexToken(
                    raw=src[i:],
                    token_type="error",
                    error_msg="閉じ括弧 ']' がありません",
                ))
                break
            tokens.append(LexToken(
                raw=src[i:j + 1],
                token_type="neg",
                inner=src[i + 1:j].strip(),
            ))
            i = j + 1

        # { ... } — 制約
        elif ch == '{':
            j = src.find('}', i)
            if j == -1:
                tokens.append(LexToken(
                    raw=src[i:],
                    token_type="error",
                    error_msg="閉じ括弧 '}' がありません",
                ))
                break
            tokens.append(LexToken(
                raw=src[i:j + 1],
                token_type="con",
                inner=src[i + 1:j].strip(),
            ))
            i = j + 1

        # プレーンテキスト
        else:
            j = i
            while j < len(src) and src[j] not in (',', '[', ']', '{', '}', '(', ')'):
                j += 1
            word = src[i:j].strip()
            if word:
                tokens.append(LexToken(
                    raw=word,
                    token_type="plain",
                    inner=word,
                ))
            i = j

    return tokens
