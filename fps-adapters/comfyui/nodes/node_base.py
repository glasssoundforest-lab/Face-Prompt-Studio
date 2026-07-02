"""
fps-adapters/comfyui/nodes/node_base.py — ComfyUI ノード共通基底

v2.1: CliContext を経由した Manager 取得に統一
      _get_context() / _get_upm() / _get_history_manager() 追加
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).parents[3]
_CORE     = _ROOT / "fps-core"
_ADAPTERS = _ROOT / "fps-adapters"

for _p in (str(_CORE), str(_ADAPTERS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger(__name__)

# ── CliContext シングルトン（v2.1 統合） ──────────────────────────
_context = None

def _get_context():
    """CliContext をシングルトンで返す（全 Manager の起点）"""
    global _context
    if _context is None:
        try:
            from cli.context import CliContext  # type: ignore[import]
            _context = CliContext()
            logger.info("CliContext initialized for ComfyUI nodes.")
        except Exception as e:
            logger.warning("CliContext init failed: %s", e)
    return _context

def _get_pipeline_manager(
    blacklist: set[str] | None = None,
    whitelist: set[str] | None = None,
    max_weight: float = 3.0,
    weight_preset: str | None = None,
):
    """PipelineManager を返す（CliContext 経由 + オーバーライド対応）"""
    ctx = _get_context()
    if ctx is None:
        return _get_pipeline_manager_standalone(blacklist, whitelist, max_weight, weight_preset)
    try:
        pm = ctx.pipeline_manager
        extra: dict[str, Any] = {"max_weight": max_weight}
        if blacklist:    extra["blacklist"] = blacklist
        if whitelist:    extra["whitelist"] = whitelist
        if weight_preset: extra["weight_preset"] = weight_preset
        if extra:
            pm.set_context(**extra)
        return pm
    except Exception as e:
        logger.warning("PipelineManager from CliContext failed: %s", e)
        return _get_pipeline_manager_standalone(blacklist, whitelist, max_weight, weight_preset)

def _get_pipeline_manager_standalone(blacklist, whitelist, max_weight, weight_preset):
    """フォールバック用スタンドアロン初期化"""
    try:
        from pipeline.manager import PipelineManager   # type: ignore[import]
        from cache.manager import CacheManager          # type: ignore[import]
        from dictionary.manager import DictionaryManager  # type: ignore[import]
        from rules.manager import RuleManager           # type: ignore[import]

        cache = CacheManager(max_size=256, default_ttl=3600)
        pm = PipelineManager(cache_manager=cache)
        data = _ROOT / "fps-data"
        dm = DictionaryManager(system_dir=data/"dictionaries"/"system",
                               user_dir=data/"dictionaries"/"user")
        dm.load()
        rm = RuleManager(rule_dir=data/"rules")
        rm.load()
        ctx: dict[str, Any] = {
            "dictionary_manager": dm, "rule_manager": rm,
            "max_weight": max_weight,
        }
        if blacklist:     ctx["blacklist"] = blacklist
        if whitelist:     ctx["whitelist"] = whitelist
        if weight_preset: ctx["weight_preset"] = weight_preset
        pm.set_context(**ctx)
        return pm
    except Exception as e:
        logger.error("PipelineManager standalone init failed: %s", e)
        return None

def _get_upm():
    """UserProfileManager を返す（★v2.1）"""
    ctx = _get_context()
    if ctx is None: return None
    try:
        return ctx.user_profile_manager
    except Exception as e:
        logger.warning("UserProfileManager from CliContext failed: %s", e)
        return None

def _get_preset_manager():
    """PresetManager を返す"""
    ctx = _get_context()
    if ctx is None: return None
    try:
        return ctx.preset_manager
    except Exception as e:
        logger.warning("PresetManager from CliContext failed: %s", e)
        return None

def _get_history_manager():
    """HistoryManager を返す（★v2.1）"""
    ctx = _get_context()
    if ctx is None: return None
    try:
        return ctx.history_manager
    except Exception as e:
        logger.warning("HistoryManager from CliContext failed: %s", e)
        return None

def _get_optimizer_manager():
    """OptimizerManager を返す"""
    ctx = _get_context()
    if ctx is None: return None
    try:
        return ctx.optimizer_manager
    except Exception as e:
        logger.warning("OptimizerManager from CliContext failed: %s", e)
        return None

class FPSNodeBase:
    """
    FPS ComfyUI ノード共通基底クラス。

    全ノードはこのクラスを継承する。
    CliContext 経由で Manager を取得する統一インターフェースを提供。
    """
    CATEGORY = "FacePromptStudio"

    @classmethod
    def IS_CHANGED(cls, **kwargs: Any) -> float:
        return float("nan")
