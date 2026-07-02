"""
Face Prompt Studio — ComfyUI カスタムノード エントリポイント

インストール方法:
    このリポジトリを ComfyUI の custom_nodes/ 以下にクローンしてください:

    cd ComfyUI/custom_nodes
    git clone https://github.com/glasssoundforest-lab/Face-Prompt-Studio.git FacePromptStudio

    # 依存ライブラリのインストール（ComfyUI の Python 環境で実行）
    pip install -r FacePromptStudio/requirements.txt

ComfyUI はこのファイル（リポジトリルートの __init__.py）を
カスタムノードのエントリポイントとして読み込みます。
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── パス設定 ──────────────────────────────────────────────────────
# このファイルの場所: ComfyUI/custom_nodes/FacePromptStudio/__init__.py
_HERE     = Path(__file__).parent                    # FacePromptStudio/
_FPS_CORE = _HERE / "fps-core"
_FPS_ADP  = _HERE / "fps-adapters"

for _p in (str(_FPS_CORE), str(_FPS_ADP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
        logger.debug("FPS: added to sys.path: %s", _p)

# ── ComfyUI ノードのロード ─────────────────────────────────────────
try:
    from fps_adapters.comfyui import (   # type: ignore[import]
        NODE_CLASS_MAPPINGS,
        NODE_DISPLAY_NAME_MAPPINGS,
    )
    logger.info("FacePromptStudio: %d nodes loaded.", len(NODE_CLASS_MAPPINGS))
except ImportError:
    # ハイフン版パス（fps-adapters）からロードを試みる
    try:
        import importlib.util, os
        _init = _HERE / "fps-adapters" / "comfyui" / "__init__.py"
        _spec = importlib.util.spec_from_file_location("fps_comfyui_nodes", str(_init))
        _mod  = importlib.util.module_from_spec(_spec)      # type: ignore[arg-type]
        _spec.loader.exec_module(_mod)                       # type: ignore[union-attr]
        NODE_CLASS_MAPPINGS         = _mod.NODE_CLASS_MAPPINGS
        NODE_DISPLAY_NAME_MAPPINGS  = _mod.NODE_DISPLAY_NAME_MAPPINGS
        logger.info("FacePromptStudio: %d nodes loaded (fallback).", len(NODE_CLASS_MAPPINGS))
    except Exception as e:
        logger.error("FacePromptStudio: node load failed: %s", e)
        NODE_CLASS_MAPPINGS        = {}
        NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
