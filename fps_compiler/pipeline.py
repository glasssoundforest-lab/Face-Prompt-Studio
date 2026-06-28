"""
pipeline.py — compile_prompt() エントリポイント

使い方:
  from pipeline import compile_prompt
  result = compile_prompt("(masterpiece), blue eyes, [bad hands]", verbose=True)
"""

from models import ComfyUIOutput
from lexer       import lexer
from tokenizer   import tokenizer
from ast_builder import build_ast
from pir_builder import build_pir
from resolver    import resolve
from optimizer   import optimize
from adapter     import to_comfyui


def compile_prompt(src: str, verbose: bool = False) -> ComfyUIOutput:
    if verbose:
        print(f"\n{'='*54}")
        print(f"  INPUT: {src}")
        print(f"{'='*54}")

    # Stage 1: Lexer
    lex_tokens = lexer(src)
    errors = [t for t in lex_tokens if t.token_type == "error"]
    for e in errors:
        print(f"[LEXER ERROR] {e.raw!r} → {e.error_msg}")

    if verbose:
        print("\n[1] Lexer:")
        for t in lex_tokens:
            print(f"    {t.token_type:6s}  {t.raw!r}")

    # Stage 2: Tokenizer
    ast_nodes = tokenizer(lex_tokens)

    if verbose:
        print("\n[2] Tokenizer:")
        for n in ast_nodes:
            w = f"  weight={n.weight:.1f}" if n.weight != 1.0 else ""
            print(f"    {n.token_type:6s}  category={n.category!r}  value={n.value!r}{w}")

    # Stage 3: AST Builder
    prompt_nodes, neg_nodes, con_nodes = build_ast(ast_nodes)

    if verbose:
        print("\n[3] AST Builder:")
        print(f"    prompt:      {[n.value or n.category for n in prompt_nodes]}")
        print(f"    negative:    {[n.value for n in neg_nodes]}")
        print(f"    constraints: {[f'{n.category}:{n.value}' for n in con_nodes]}")

    # Stage 4: PIR Builder
    pir = build_pir(prompt_nodes, neg_nodes, con_nodes)

    if verbose:
        print("\n[4] PIR Builder:")
        for c in pir.concepts:
            print(f"    Concept     name={c.name!r}  value={c.value!r}  weight={c.weight:.1f}")
        for c in pir.constraints:
            print(f"    Constraint  type={c.type!r}  value={c.value!r}")

    # Stage 5: Semantic Resolver
    pir = resolve(pir)

    if verbose:
        print("\n[5] Resolver:")
        for c in pir.concepts:
            status = f"→ {c.resolved}" if c.resolved else "→ (未定義・削除予定)"
            print(f"    {c.name!r:22s}  {status}")

    # Stage 6: Optimizer
    pir = optimize(pir)

    if verbose:
        print("\n[6] Optimizer:")
        for c in pir.concepts:
            w = f"  weight={c.weight:.1f}" if c.weight != 1.0 else ""
            print(f"    {c.resolved}{w}")

    # Stage 7: ComfyUI Adapter
    output = to_comfyui(pir)

    if verbose:
        print("\n[7] ComfyUI Adapter:")
        print(f"    prompt:          {output.prompt!r}")
        print(f"    negative_prompt: {output.negative_prompt!r}")
        print(f"    constraints:     {output.constraints}")
        print(f"\n{'='*54}")

    return output
