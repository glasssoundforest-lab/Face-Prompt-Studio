"""
adapter.py — Stage 7: ComfyUI Adapter

PIR を ComfyUI JSON 形式に変換する。
重みが 1.0 以外の場合は "resolved:weight" 形式で出力する。
"""

from models import PIR, ComfyUIOutput


def to_comfyui(pir: PIR) -> ComfyUIOutput:
    prompt_parts = [
        f"{c.resolved}:{c.weight:.1f}" if c.weight != 1.0 else c.resolved
        for c in pir.concepts
        if c.resolved
    ]
    negative_parts = [
        c.value.replace(" ", "_")
        for c in pir.constraints
        if c.type == "negative"
    ]
    constraint_parts = [
        f"{c.type}.{c.value}"
        for c in pir.constraints
        if c.type != "negative"
    ]

    return ComfyUIOutput(
        prompt=", ".join(prompt_parts),
        negative_prompt=", ".join(negative_parts),
        constraints=constraint_parts,
    )
