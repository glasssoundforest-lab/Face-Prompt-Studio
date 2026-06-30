"""
fps-adapters/comfyui/nodes/node_base.py — ComfyUI ノード共通基底

ComfyUI ノードの共通処理（fps-core パス設定・DictionaryManager / RuleManager 初期化）
を提供する。fps-core はここで一度だけ初期化してキャッシュする。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# fps-core / fps-adapters をパスに追加
_ROOT = Path(__file__).parents[3]
_CORE = _ROOT / "fps-core"

for _p in (str(_CORE), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger(__name__)

# ── 遅延初期化キャッシュ ─────────────────────────────────────────
_dictionary_manager = None
_rule_manager = None
_pipeline_manager = None
_category_weight_table = None


def _get_category_weight_table():
    """CategoryWeightTable をシングルトンで返す"""
    global _category_weight_table
    if _category_weight_table is None:
        try:
            from pipeline.category_weights import CategoryWeightTable

            path = _ROOT / "fps-data" / "rules" / "category_weights.json"
            _category_weight_table = CategoryWeightTable.load(path)
            logger.info("CategoryWeightTable initialized.")
        except Exception as e:
            logger.warning("CategoryWeightTable init failed: %s", e)
            _category_weight_table = None
    return _category_weight_table


def _get_dictionary_manager():
    """DictionaryManager をシングルトンで返す"""
    global _dictionary_manager
    if _dictionary_manager is None:
        try:
            from dictionary.manager import DictionaryManager

            data_root = _ROOT / "fps-data" / "dictionaries"
            _dictionary_manager = DictionaryManager(
                system_dir=data_root / "system",
                user_dir=data_root / "user",
            )
            _dictionary_manager.load()
            logger.info("DictionaryManager initialized.")
        except Exception as e:
            logger.warning("DictionaryManager init failed: %s", e)
            _dictionary_manager = None
    return _dictionary_manager


def _get_rule_manager():
    """RuleManager をシングルトンで返す"""
    global _rule_manager
    if _rule_manager is None:
        try:
            from rules.manager import RuleManager

            _rule_manager = RuleManager(rule_dir=_ROOT / "fps-data" / "rules")
            _rule_manager.load()
            logger.info("RuleManager initialized.")
        except Exception as e:
            logger.warning("RuleManager init failed: %s", e)
            _rule_manager = None
    return _rule_manager


def _get_pipeline_manager(
    blacklist: set[str] | None = None,
    whitelist: set[str] | None = None,
    max_weight: float = 3.0,
    weight_preset: str | None = None,
):
    """PipelineManager を毎回新規生成して返す（コンテキスト依存のため）"""
    try:
        from pipeline.manager import PipelineManager

        pm = PipelineManager()
        ctx: dict[str, Any] = {"max_weight": max_weight}

        dm = _get_dictionary_manager()
        if dm:
            ctx["dictionary_manager"] = dm

        rm = _get_rule_manager()
        if rm:
            ctx["rule_manager"] = rm

        table = _get_category_weight_table()
        if table:
            ctx["category_weight_table"] = table
        if weight_preset:
            ctx["weight_preset"] = weight_preset

        if blacklist:
            ctx["blacklist"] = blacklist
        if whitelist:
            ctx["whitelist"] = whitelist

        pm.set_context(**ctx)
        return pm
    except Exception as e:
        logger.error("PipelineManager init failed: %s", e)
        return None


class FPSNodeBase:
    """
    FPS ComfyUI ノード共通基底クラス。

    ComfyUI のノードクラスは以下の属性・メソッドが必要:
      - CATEGORY      : ノードメニューのカテゴリ
      - RETURN_TYPES  : 出力タプルの型
      - RETURN_NAMES  : 出力タプルの名前
      - FUNCTION      : 実行メソッド名（文字列）
      - INPUT_TYPES() : クラスメソッド / 入力仕様を返す
    """

    CATEGORY = "FacePromptStudio"

    @classmethod
    def IS_CHANGED(cls, **kwargs: Any) -> float:
        """毎回実行させる（キャッシュ無効化）"""
        return float("nan")
