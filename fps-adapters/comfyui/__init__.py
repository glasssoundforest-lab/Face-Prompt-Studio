"""
fps-adapters/comfyui/__init__.py
ComfyUI カスタムノード エントリポイント

ComfyUI はこのファイルを読み込んで NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS を取得する。
"""

from .nodes.debug_output import FacePromptDebugNode
from .nodes.face_prompt_backup import FacePromptBackupNode
from .nodes.face_prompt_category_filter import FacePromptCategoryFilterNode
from .nodes.face_prompt_cleaner import FacePromptCleanerNode
from .nodes.face_prompt_compiler import FacePromptCompilerNode
from .nodes.face_prompt_group_control import FacePromptGroupControlNode
from .nodes.face_prompt_history import FacePromptHistoryNode
from .nodes.face_prompt_optimizer import FacePromptOptimizerNode
from .nodes.face_prompt_preset import FacePromptPresetNode
from .nodes.face_prompt_rule_editor import FacePromptRuleEditorNode

NODE_CLASS_MAPPINGS = {
    "FacePromptCleaner": FacePromptCleanerNode,
    "FacePromptCompiler": FacePromptCompilerNode,
    "FacePromptDebug": FacePromptDebugNode,
    "FacePromptPreset": FacePromptPresetNode,
    "FacePromptRuleEditor": FacePromptRuleEditorNode,
    "FacePromptCategoryFilter": FacePromptCategoryFilterNode,
    "FacePromptOptimizer": FacePromptOptimizerNode,
    "FacePromptHistory": FacePromptHistoryNode,
    "FacePromptBackup": FacePromptBackupNode,
    "FacePromptGroupControl": FacePromptGroupControlNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FacePromptCleaner": "🎭 Face Prompt Cleaner",
    "FacePromptCompiler": "🎭 Face Prompt Compiler",
    "FacePromptDebug": "🎭 Face Prompt Debug",
    "FacePromptPreset": "🎭 Face Prompt Preset",
    "FacePromptRuleEditor": "🎭 Face Prompt Rule Editor",
    "FacePromptCategoryFilter": "🎭 Face Prompt Category Filter",
    "FacePromptOptimizer": "🎭 Face Prompt Optimizer",
    "FacePromptHistory": "🎭 Face Prompt History",
    "FacePromptBackup": "🎭 Face Prompt Backup",
    "FacePromptGroupControl": "🎭 Face Prompt Group Control",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
