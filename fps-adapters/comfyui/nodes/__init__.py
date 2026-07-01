"""fps-adapters/comfyui/nodes — ComfyUI ノードパッケージ"""

from .debug_output import FacePromptDebugNode
from .face_prompt_backup import FacePromptBackupNode
from .face_prompt_category_filter import FacePromptCategoryFilterNode
from .face_prompt_cleaner import FacePromptCleanerNode
from .face_prompt_compiler import FacePromptCompilerNode
from .face_prompt_group_control import FacePromptGroupControlNode
from .face_prompt_history import FacePromptHistoryNode
from .face_prompt_optimizer import FacePromptOptimizerNode
from .face_prompt_preset import FacePromptPresetNode
from .face_prompt_rule_editor import FacePromptRuleEditorNode
from .face_prompt_template import FacePromptTemplateNode  # ★v1.3 NEW

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
    "FacePromptTemplate": FacePromptTemplateNode,  # ★v1.3 NEW
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
    "FacePromptTemplate": "🎭 Face Prompt Template",  # ★v1.3 NEW
}

__all__ = list(NODE_CLASS_MAPPINGS.keys())
