"""
fps-adapters/comfyui/__init__.py
ComfyUI カスタムノード エントリポイント

ComfyUI はこのファイルを読み込んで NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS を取得する。
"""

from .nodes.debug_output import FacePromptDebugNode
from .nodes.face_prompt_cleaner import FacePromptCleanerNode
from .nodes.face_prompt_compiler import FacePromptCompilerNode

NODE_CLASS_MAPPINGS = {
    "FacePromptCleaner": FacePromptCleanerNode,
    "FacePromptCompiler": FacePromptCompilerNode,
    "FacePromptDebug": FacePromptDebugNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FacePromptCleaner": "🎭 Face Prompt Cleaner",
    "FacePromptCompiler": "🎭 Face Prompt Compiler",
    "FacePromptDebug": "🎭 Face Prompt Debug",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
