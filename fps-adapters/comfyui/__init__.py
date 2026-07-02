"""
v2.6: FacePromptWildcardNode 追加（19ノード体制）
fps-adapters/comfyui/__init__.py
ComfyUI カスタムノード エントリポイント

v2.5: FacePromptLoRA / AITagger / Consistency 追加（18ノード体制）
"""

from .nodes.debug_output import FacePromptDebugNode
from .nodes.face_prompt_backup import FacePromptBackupNode
from .nodes.face_prompt_batch import FacePromptBatchNode
from .nodes.face_prompt_category_filter import FacePromptCategoryFilterNode
from .nodes.face_prompt_cleaner import FacePromptCleanerNode
from .nodes.face_prompt_compiler import FacePromptCompilerNode
from .nodes.face_prompt_consistency import FacePromptConsistencyNode   # ★v2.5
from .nodes.face_prompt_group_control import FacePromptGroupControlNode
from .nodes.face_prompt_history import FacePromptHistoryNode
from .nodes.face_prompt_lora import FacePromptLoraNode                 # ★v2.5
from .nodes.face_prompt_optimizer import FacePromptOptimizerNode
from .nodes.face_prompt_preset import FacePromptPresetNode
from .nodes.face_prompt_profile import (
    FacePromptProfileNode,
    FacePromptProfileApplyNode,
    FacePromptProfileLearnNode,
)
from .nodes.face_prompt_rule_editor import FacePromptRuleEditorNode
from .nodes.face_prompt_tagger import FacePromptAITaggerNode
from .nodes.face_prompt_wildcard import FacePromptWildcardNode  # ★v2.6           # ★v2.5
from .nodes.face_prompt_template import FacePromptTemplateNode

NODE_CLASS_MAPPINGS = {
    # ── コア 7ノード ─────────────────────────────────────────────
    "FacePromptCleaner":        FacePromptCleanerNode,
    "FacePromptCompiler":       FacePromptCompilerNode,
    "FacePromptDebug":          FacePromptDebugNode,
    "FacePromptPreset":         FacePromptPresetNode,
    "FacePromptRuleEditor":     FacePromptRuleEditorNode,
    "FacePromptCategoryFilter": FacePromptCategoryFilterNode,
    "FacePromptGroupControl":   FacePromptGroupControlNode,
    # ── 分析・最適化 ─────────────────────────────────────────────
    "FacePromptOptimizer":      FacePromptOptimizerNode,
    "FacePromptHistory":        FacePromptHistoryNode,
    "FacePromptBackup":         FacePromptBackupNode,
    "FacePromptTemplate":       FacePromptTemplateNode,
    "FacePromptBatch":          FacePromptBatchNode,
    # ── パーソナライゼーション（v2.1） ───────────────────────────
    "FacePromptProfile":        FacePromptProfileNode,
    "FacePromptProfileApply":   FacePromptProfileApplyNode,
    "FacePromptProfileLearn":   FacePromptProfileLearnNode,
    # ── Wildcard（v2.6）──────────────────────────────────────────
    "FacePromptWildcard":    FacePromptWildcardNode,
    # ── AI 強化（v2.5） ──────────────────────────────────────────
    "FacePromptWildcard":   "🎭 Face Prompt Wildcard",
    "FacePromptLora":           FacePromptLoraNode,
    "FacePromptAITagger":       FacePromptAITaggerNode,
    "FacePromptConsistency":    FacePromptConsistencyNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FacePromptCleaner":        "🎭 Face Prompt Cleaner",
    "FacePromptCompiler":       "🎭 Face Prompt Compiler",
    "FacePromptDebug":          "🎭 Face Prompt Debug",
    "FacePromptPreset":         "🎭 Face Prompt Preset",
    "FacePromptRuleEditor":     "🎭 Face Prompt Rule Editor",
    "FacePromptCategoryFilter": "🎭 Face Prompt Category Filter",
    "FacePromptGroupControl":   "🎭 Face Prompt Group Control",
    "FacePromptOptimizer":      "🎭 Face Prompt Optimizer",
    "FacePromptHistory":        "🎭 Face Prompt History",
    "FacePromptBackup":         "🎭 Face Prompt Backup",
    "FacePromptTemplate":       "🎭 Face Prompt Template",
    "FacePromptBatch":          "🎭 Face Prompt Batch",
    "FacePromptProfile":        "🎭 Face Prompt Profile",
    "FacePromptProfileApply":   "🎭 Face Prompt Profile Apply",
    "FacePromptProfileLearn":   "🎭 Face Prompt Profile Learn",
    "FacePromptWildcard":   "🎭 Face Prompt Wildcard",
    "FacePromptLora":           "🎭 Face Prompt LoRA Analyzer",
    "FacePromptAITagger":       "🎭 Face Prompt AI Tagger",
    "FacePromptConsistency":    "🎭 Face Prompt Consistency Checker",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
