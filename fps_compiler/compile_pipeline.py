from fps_compiler.lexer import lexer
from fps_compiler.tokenizer import tokenizer
from fps_compiler.ast_builder import build_ast
from fps_compiler.pir_builder import build_pir

from fps_semantic.resolver import resolve
from fps_semantic.optimizer import optimize

from fps_adapters.comfyui.adapter import to_comfyui


def compile_prompt(prompt: str):
    tokens = lexer(prompt)
    nodes = tokenizer(tokens)
    ast = build_ast(nodes)
    pir = build_pir(ast)

    pir = resolve(pir)
    pir = optimize(pir)

    return to_comfyui(pir)