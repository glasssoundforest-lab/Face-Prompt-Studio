"""
Face Prompt Studio — ComfyUI カスタムノード エントリポイント v2.7

インストール:
    cd ComfyUI/custom_nodes
    git clone https://github.com/glasssoundforest-lab/Face-Prompt-Studio.git FacePromptStudio
    # ComfyUI 再起動で FacePromptStudio カテゴリにノードが出現

注意: fps-core は外部ライブラリ不要（標準ライブラリのみ）。
      REST API を使う場合のみ: pip install fastapi uvicorn pydantic
"""
from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger("FacePromptStudio")

# ── パス設定（絶対パスで固定）──────────────────────────────────────
# このファイルの場所:
#   ComfyUI/custom_nodes/FacePromptStudio/__init__.py
_HERE     = Path(__file__).resolve().parent   # FacePromptStudio/
_FPS_CORE = _HERE / "fps-core"               # fps-core/
_FPS_ADP  = _HERE / "fps-adapters"           # fps-adapters/
_FPS_DATA = _HERE / "fps-data"               # fps-data/

# sys.path に追加（ハイフン含むディレクトリは直接 import できないが
# その中のサブパッケージは追加したパス経由でインポートできる）
for _p in [str(_FPS_CORE), str(_FPS_ADP)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# fps-data が存在しなければ最低限のディレクトリだけ作成
for _d in ["wildcards", "presets/user", "dictionaries/user", "user", "rules"]:
    (_FPS_DATA / _d).mkdir(parents=True, exist_ok=True)


def _load_comfyui_nodes() -> tuple[dict, dict]:
    """
    fps-adapters/comfyui/__init__.py を importlib で直接ロードする。
    ハイフンを含むパス（fps-adapters）は通常の import 文では使えないため、
    spec_from_file_location を使って絶対パスでロードする。
    """
    comfyui_init = _FPS_ADP / "comfyui" / "__init__.py"

    if not comfyui_init.exists():
        logger.error("FPS: ComfyUI __init__.py not found: %s", comfyui_init)
        return {}, {}

    # パッケージとしてロードするため fps-adapters/comfyui/ を sys.path に追加
    comfyui_dir = str(_FPS_ADP / "comfyui")
    if comfyui_dir not in sys.path:
        sys.path.insert(0, comfyui_dir)

    # fps-adapters/comfyui/__init__.py を "fps_comfyui_pkg" という名前でロード
    spec = importlib.util.spec_from_file_location(
        "fps_comfyui_pkg",
        str(comfyui_init),
        submodule_search_locations=[str(_FPS_ADP / "comfyui")],
    )
    if spec is None or spec.loader is None:
        logger.error("FPS: spec_from_file_location failed for %s", comfyui_init)
        return {}, {}

    mod = importlib.util.module_from_spec(spec)
    # sys.modules に登録してから exec（相対 import が機能するように）
    sys.modules["fps_comfyui_pkg"] = mod
    sys.modules["fps_comfyui_pkg.nodes"] = mod  # フォールバック
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        logger.error("FPS: exec_module failed: %s", e, exc_info=True)
        return {}, {}

    return (
        getattr(mod, "NODE_CLASS_MAPPINGS", {}),
        getattr(mod, "NODE_DISPLAY_NAME_MAPPINGS", {}),
    )


# ── ノードロード実行 ────────────────────────────────────────────────
try:
    NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = _load_comfyui_nodes()
    if NODE_CLASS_MAPPINGS:
        logger.info(
            "FacePromptStudio v2.7: %d ノードをロードしました。 "
            "FacePromptStudio カテゴリを確認してください。",
            len(NODE_CLASS_MAPPINGS),
        )
    else:
        logger.warning(
            "FacePromptStudio: ノードのロードに失敗しました。"
            " ComfyUI コンソールログを確認してください。"
            " パス: %s", _HERE,
        )
except Exception as _e:
    logger.error("FacePromptStudio: 起動エラー: %s", _e, exc_info=True)
    NODE_CLASS_MAPPINGS        = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
