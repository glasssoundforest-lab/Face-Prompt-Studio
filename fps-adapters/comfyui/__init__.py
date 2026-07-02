"""
v2.4: FacePromptBatchNode 追加（15ノード体制）
fps-adapters/comfyui/__init__.py
ComfyUI カスタムノード エントリポイント

v2.1: FacePromptProfile / Apply / Learn ノード追加（14ノード体制）
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
from .nodes.face_prompt_template import FacePromptTemplateNode
from .nodes.face_prompt_batch import FacePromptBatchNode  # ★v2.4
from .nodes.face_prompt_profile import (  # ★v2.1
    FacePromptProfileNode,
    FacePromptProfileApplyNode,
    FacePromptProfileLearnNode,
)

NODE_CLASS_MAPPINGS = {
    # 既存 11ノード
    "FacePromptCleaner":        FacePromptCleanerNode,
    "FacePromptCompiler":       FacePromptCompilerNode,
    "FacePromptDebug":          FacePromptDebugNode,
    "FacePromptPreset":         FacePromptPresetNode,
    "FacePromptRuleEditor":     FacePromptRuleEditorNode,
    "FacePromptCategoryFilter": FacePromptCategoryFilterNode,
    "FacePromptOptimizer":      FacePromptOptimizerNode,
    "FacePromptHistory":        FacePromptHistoryNode,
    "FacePromptBackup":         FacePromptBackupNode,
    "FacePromptGroupControl":   FacePromptGroupControlNode,
    "FacePromptTemplate":       FacePromptTemplateNode,
    # ★v2.4 新設
    "FacePromptBatch":        FacePromptBatchNode,
    # ★v2.1 新設 3ノード
    "FacePromptProfile":        FacePromptProfileNode,
    "FacePromptProfileApply":   FacePromptProfileApplyNode,
    "FacePromptProfileLearn":   FacePromptProfileLearnNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FacePromptCleaner":        "🎭 Face Prompt Cleaner",
    "FacePromptCompiler":       "🎭 Face Prompt Compiler",
    "FacePromptDebug":          "🎭 Face Prompt Debug",
    "FacePromptPreset":         "🎭 Face Prompt Preset",
    "FacePromptRuleEditor":     "🎭 Face Prompt Rule Editor",
    "FacePromptCategoryFilter": "🎭 Face Prompt Category Filter",
    "FacePromptOptimizer":      "🎭 Face Prompt Optimizer",
    "FacePromptHistory":        "🎭 Face Prompt History",
    "FacePromptBackup":         "🎭 Face Prompt Backup",
    "FacePromptGroupControl":   "🎭 Face Prompt Group Control",
    "FacePromptTemplate":       "🎭 Face Prompt Template",
    # ★v2.4
    "FacePromptBatch":        "🎭 Face Prompt Batch",
    # ★v2.1
    "FacePromptProfile":        "🎭 Face Prompt Profile",
    "FacePromptProfileApply":   "🎭 Face Prompt Profile Apply",
    "FacePromptProfileLearn":   "🎭 Face Prompt Profile Learn",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
