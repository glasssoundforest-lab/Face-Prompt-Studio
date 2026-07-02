"""
fps-adapters/comfyui/nodes/node_base.py — ComfyUI ノード共通基底

v2.7: data_root を絶対パスで CliContext に渡すよう修正（実稼働対応）
      ComfyUI の CWD に依存しないよう __file__ から絶対パスを解決する。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# このファイル: <repo>/fps-adapters/comfyui/nodes/node_base.py
# _ROOT       : <repo>/  （リポジトリルート）
_ROOT     = Path(__file__).resolve().parents[3]  # resolve() で symlink も解決
_CORE     = _ROOT / "fps-core"
_ADAPTERS = _ROOT / "fps-adapters"
_DATA     = _ROOT / "fps-data"

for _p in (str(_CORE), str(_ADAPTERS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger("FacePromptStudio.nodes")

# ── CliContext シングルトン ─────────────────────────────────────────
_context = None


def _get_context():
    """
    CliContext をシングルトンで返す。

    data_root を絶対パス（_DATA）で渡すことで、ComfyUI の
    カレントディレクトリに依存しないようにしている。
    """
    global _context
    if _context is None:
        try:
            from cli.context import CliContext   # type: ignore[import]
            # ★v2.7: data_root を明示的に絶対パスで渡す
            _context = CliContext(data_root=_DATA)
            logger.info("CliContext initialized. data_root=%s", _DATA)
        except Exception as e:
            logger.warning("CliContext init failed: %s", e)
    return _context


def _get_pipeline_manager(
    blacklist: set[str] | None = None,
    whitelist: set[str] | None = None,
    max_weight: float = 3.0,
    weight_preset: str | None = None,
):
    """PipelineManager を返す（CliContext 経由 + スタンドアロンフォールバック）"""
    ctx = _get_context()
    if ctx is not None:
        try:
            pm = ctx.pipeline_manager
            extra: dict[str, Any] = {"max_weight": max_weight}
            if blacklist:     extra["blacklist"] = blacklist
            if whitelist:     extra["whitelist"] = whitelist
            if weight_preset: extra["weight_preset"] = weight_preset
            if extra:
                pm.set_context(**extra)
            return pm
        except Exception as e:
            logger.warning("PipelineManager from CliContext failed: %s", e)

    # フォールバック: CliContext 無しで直接初期化
    return _get_pipeline_manager_standalone(blacklist, whitelist, max_weight, weight_preset)


def _get_pipeline_manager_standalone(blacklist, whitelist, max_weight, weight_preset):
    """CliContext が使えない場合のスタンドアロン初期化"""
    try:
        from pipeline.manager import PipelineManager       # type: ignore[import]
        from cache.manager import CacheManager             # type: ignore[import]
        from dictionary.manager import DictionaryManager  # type: ignore[import]
        from rules.manager import RuleManager             # type: ignore[import]

        cache = CacheManager(max_size=256, default_ttl=3600)
        pm    = PipelineManager(cache_manager=cache)
        dm    = DictionaryManager(
            system_dir=_DATA / "dictionaries" / "system",
            user_dir  =_DATA / "dictionaries" / "user",
        )
        dm.load()
        rm = RuleManager(rule_dir=_DATA / "rules")
        rm.load()
        ctx_dict: dict[str, Any] = {
            "dictionary_manager": dm,
            "rule_manager":       rm,
            "max_weight":         max_weight,
        }
        if blacklist:     ctx_dict["blacklist"] = blacklist
        if whitelist:     ctx_dict["whitelist"] = whitelist
        if weight_preset: ctx_dict["weight_preset"] = weight_preset
        pm.set_context(**ctx_dict)
        return pm
    except Exception as e:
        logger.error("PipelineManager standalone init failed: %s", e)
        return None


def _get_upm():
    """UserProfileManager を返す"""
    ctx = _get_context()
    if ctx is None: return None
    try:
        return ctx.user_profile_manager
    except Exception as e:
        logger.warning("UserProfileManager unavailable: %s", e)
        return None


def _get_preset_manager():
    """PresetManager を返す"""
    ctx = _get_context()
    if ctx is None: return None
    try:
        return ctx.preset_manager
    except Exception as e:
        logger.warning("PresetManager unavailable: %s", e)
        return None


def _get_history_manager():
    """HistoryManager を返す"""
    ctx = _get_context()
    if ctx is None: return None
    try:
        return ctx.history_manager
    except Exception as e:
        logger.warning("HistoryManager unavailable: %s", e)
        return None


def _get_optimizer_manager():
    """OptimizerManager を返す"""
    ctx = _get_context()
    if ctx is None: return None
    try:
        return ctx.optimizer_manager
    except Exception as e:
        logger.warning("OptimizerManager unavailable: %s", e)
        return None


class FPSNodeBase:
    """FPS ComfyUI ノード共通基底クラス"""
    CATEGORY = "FacePromptStudio"

    @classmethod
    def IS_CHANGED(cls, **kwargs: Any) -> float:
        """毎回実行させる（キャッシュ無効化）"""
        return float("nan")
