"""
main.py — テスト実行

python main.py で全テストケースを実行する。
"""

from pipeline import compile_prompt


TEST_CASES = [
    # v0.4.0 互換 — (masterpiece) はコロンなしなので plain にフォールバック
    "(masterpiece), blue eyes, long hair, [bad hands]",
    # DSL拡張 v0.5.0
    "(quality:high), (eyes:blue:1.5), long hair, [bad hands], {style:anime}",
    # 重み複数
    "(quality:high:2.0), (hair:blonde:0.8), [bad anatomy], {style:realistic}",
    # エラーケース
    "(quality:high, [unclosed bracket",
]

for i, prompt in enumerate(TEST_CASES, 1):
    print(f"\n{'#'*54}")
    print(f"# TEST {i}")
    result = compile_prompt(prompt, verbose=True)
    print(f"\n  OUTPUT:")
    print(f"  {{")
    print(f'    "prompt":          "{result.prompt}",')
    print(f'    "negative_prompt": "{result.negative_prompt}",')
    print(f'    "constraints":     {result.constraints}')
    print(f"  }}")
