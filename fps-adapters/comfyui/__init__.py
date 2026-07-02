"""
fps-adapters/comfyui/__init__.py
ComfyUI カスタムノード エントリポイント

v2.7: 相対 import を修正（importlib ロード時の互換性確保）
      19ノード体制

ロード順序（root/__init__.py → ここ → 各ノードファイル）
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger("FacePromptStudio.comfyui")

# このファイルの場所: fps-adapters/comfyui/__init__.py
# nodes/ ディレクトリを sys.path に追加（node_base のインポート用）
_NODES_DIR = str(Path(__file__).resolve().parent / "nodes")
if _NODES_DIR not in sys.path:
    sys.path.insert(0, _NODES_DIR)

# ── ノードクラスのインポート（個別 try/except で部分ロードを許容）──

def _safe_import(module_path: str, class_name: str):
    """インポートに失敗してもプロセスを止めない"""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    except Exception as e:
        logger.warning("FPS: ノード '%s' のロードをスキップ: %s", class_name, e)
        return None


# 各ノードをインポート
FacePromptDebugNode          = _safe_import("debug_output",                "FacePromptDebugNode")
FacePromptBackupNode         = _safe_import("face_prompt_backup",          "FacePromptBackupNode")
FacePromptBatchNode          = _safe_import("face_prompt_batch",           "FacePromptBatchNode")
FacePromptCategoryFilterNode = _safe_import("face_prompt_category_filter", "FacePromptCategoryFilterNode")
FacePromptCleanerNode        = _safe_import("face_prompt_cleaner",         "FacePromptCleanerNode")
FacePromptCompilerNode       = _safe_import("face_prompt_compiler",        "FacePromptCompilerNode")
FacePromptConsistencyNode    = _safe_import("face_prompt_consistency",     "FacePromptConsistencyNode")
FacePromptGroupControlNode   = _safe_import("face_prompt_group_control",   "FacePromptGroupControlNode")
FacePromptHistoryNode        = _safe_import("face_prompt_history",         "FacePromptHistoryNode")
FacePromptLoraNode           = _safe_import("face_prompt_lora",            "FacePromptLoraNode")
FacePromptOptimizerNode      = _safe_import("face_prompt_optimizer",       "FacePromptOptimizerNode")
FacePromptPresetNode         = _safe_import("face_prompt_preset",          "FacePromptPresetNode")
FacePromptRuleEditorNode     = _safe_import("face_prompt_rule_editor",     "FacePromptRuleEditorNode")
FacePromptTemplateNode       = _safe_import("face_prompt_template",        "FacePromptTemplateNode")
FacePromptWildcardNode       = _safe_import("face_prompt_wildcard",        "FacePromptWildcardNode")

# Profile ノード群（1ファイルに3クラス）
try:
    from face_prompt_profile import (   # type: ignore[import]
        FacePromptProfileNode,
        FacePromptProfileApplyNode,
        FacePromptProfileLearnNode,
    )
except Exception as e:
    logger.warning("FPS: Profile ノードのロードをスキップ: %s", e)
    FacePromptProfileNode      = None
    FacePromptProfileApplyNode = None
    FacePromptProfileLearnNode = None

# AI Tagger ノード
FacePromptAITaggerNode = _safe_import("face_prompt_tagger", "FacePromptAITaggerNode")

# Character ノード（v2.7）
FacePromptCharacterNode = _safe_import("face_prompt_character", "FacePromptCharacterNode")

# ── NODE_CLASS_MAPPINGS — None のエントリを除外して登録 ──────────────
_all_nodes = {
    "FacePromptCleaner":        FacePromptCleanerNode,
    "FacePromptCompiler":       FacePromptCompilerNode,
    "FacePromptDebug":          FacePromptDebugNode,
    "FacePromptPreset":         FacePromptPresetNode,
    "FacePromptRuleEditor":     FacePromptRuleEditorNode,
    "FacePromptCategoryFilter": FacePromptCategoryFilterNode,
    "FacePromptGroupControl":   FacePromptGroupControlNode,
    "FacePromptOptimizer":      FacePromptOptimizerNode,
    "FacePromptHistory":        FacePromptHistoryNode,
    "FacePromptBackup":         FacePromptBackupNode,
    "FacePromptTemplate":       FacePromptTemplateNode,
    "FacePromptBatch":          FacePromptBatchNode,
    "FacePromptProfile":        FacePromptProfileNode,
    "FacePromptProfileApply":   FacePromptProfileApplyNode,
    "FacePromptProfileLearn":   FacePromptProfileLearnNode,
    "FacePromptLora":           FacePromptLoraNode,
    "FacePromptAITagger":       FacePromptAITaggerNode,
    "FacePromptConsistency":    FacePromptConsistencyNode,
    "FacePromptWildcard":       FacePromptWildcardNode,
    "FacePromptCharacter":      FacePromptCharacterNode,
}

NODE_CLASS_MAPPINGS = {k: v for k, v in _all_nodes.items() if v is not None}

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
    "FacePromptLora":           "🎭 Face Prompt LoRA Analyzer",
    "FacePromptAITagger":       "🎭 Face Prompt AI Tagger",
    "FacePromptConsistency":    "🎭 Face Prompt Consistency Checker",
    "FacePromptWildcard":       "🎭 Face Prompt Wildcard",
    "FacePromptCharacter":      "🎭 Face Prompt Character",
}
# ロードできなかったノードは表示名からも除外
NODE_DISPLAY_NAME_MAPPINGS = {
    k: v for k, v in NODE_DISPLAY_NAME_MAPPINGS.items()
    if k in NODE_CLASS_MAPPINGS
}

logger.info("FacePromptStudio: %d ノード登録完了", len(NODE_CLASS_MAPPINGS))
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
