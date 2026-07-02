#!/usr/bin/env python3
"""
scripts/verify_comfyui.py — FacePromptStudio ComfyUI 動作確認スクリプト

使い方:
    # ComfyUI/custom_nodes/FacePromptStudio/ で実行
    python scripts/verify_comfyui.py

    # または ComfyUI の Python 環境で実行
    /path/to/comfyui/python_embeded/python.exe scripts/verify_comfyui.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# このスクリプトの場所から _ROOT を解決
_SCRIPT = Path(__file__).resolve()
_ROOT   = _SCRIPT.parents[1]      # FacePromptStudio/

print(f"""
╔══════════════════════════════════════════════════════════╗
║  FacePromptStudio ComfyUI 動作確認スクリプト v2.7        ║
╚══════════════════════════════════════════════════════════╝

リポジトリルート: {_ROOT}
Python バージョン: {sys.version.split()[0]}
""")

OK = "✅"; NG = "❌"; WARN = "⚠️"

def check(label: str, fn, warn_only=False):
    try:
        result = fn()
        status = OK
        detail = str(result)[:80] if result else ""
        print(f"  {status} {label}  {detail}")
        return True
    except Exception as e:
        status = WARN if warn_only else NG
        print(f"  {status} {label}")
        print(f"       → {e}")
        if not warn_only:
            traceback.print_exc()
        return warn_only

results = []
print("── 1. ディレクトリ構造 ─────────────────────────────────────")
for d in ["fps-core", "fps-adapters", "fps-data",
          "fps-data/dictionaries", "fps-data/wildcards",
          "fps-adapters/comfyui", "fps-adapters/cli"]:
    p = _ROOT / d
    results.append(check(d, lambda p=p: p.is_dir() and p or (_ for _ in ()).throw(FileNotFoundError(f"存在しない: {p}"))))

print("
── 2. sys.path 設定 ────────────────────────────────────────")
fps_core = str(_ROOT / "fps-core")
fps_adp  = str(_ROOT / "fps-adapters")
for p in [fps_core, fps_adp]:
    if p not in sys.path:
        sys.path.insert(0, p)
print(f"  {OK} fps-core / fps-adapters を sys.path に追加")

print("
── 3. fps-core モジュールのインポート ──────────────────────")
results.append(check("dictionary.manager", lambda: __import__("dictionary.manager")))
results.append(check("pipeline.manager",   lambda: __import__("pipeline.manager")))
results.append(check("preset.manager",     lambda: __import__("preset.manager")))
results.append(check("wildcard.engine",    lambda: __import__("wildcard.engine")))
results.append(check("ai.lora_analyzer",   lambda: __import__("ai.lora_analyzer")))

print("
── 4. CliContext の初期化 ───────────────────────────────────")
def check_cli():
    from cli.context import CliContext
    ctx = CliContext(data_root=_ROOT / "fps-data")
    dm = ctx.dictionary_manager
    return f"辞書キー数: {len(getattr(dm, '_index', {}))}"
results.append(check("CliContext + DictionaryManager", check_cli))

print("
── 5. ComfyUI ノードのロード ────────────────────────────────")
def check_nodes():
    import importlib.util
    init_path = _ROOT / "fps-adapters" / "comfyui" / "__init__.py"
    nodes_dir = str(_ROOT / "fps-adapters" / "comfyui" / "nodes")
    if nodes_dir not in sys.path:
        sys.path.insert(0, nodes_dir)
    spec = importlib.util.spec_from_file_location(
        "_fps_verify_nodes", str(init_path),
        submodule_search_locations=[str(init_path.parent)]
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    n = len(mod.NODE_CLASS_MAPPINGS)
    return f"{n} ノード登録済み: {list(mod.NODE_CLASS_MAPPINGS.keys())[:5]}..."
results.append(check("NODE_CLASS_MAPPINGS", check_nodes))

print("
── 6. Wildcard エンジン ─────────────────────────────────────")
def check_wc():
    from wildcard.engine import WildcardEngine
    from wildcard.manager import WildcardManager
    wm = WildcardManager(_ROOT / "fps-data" / "wildcards")
    engine = WildcardEngine(wildcard_manager=wm, seed=42)
    result = engine.expand("[[anime|realistic]], {{quality:best_quality}}")
    return f"展開結果: {result}"
results.append(check("WildcardEngine.expand()", check_wc))

print("
── 7. root/__init__.py のロード ─────────────────────────────")
def check_root():
    import importlib.util
    root_init = _ROOT / "__init__.py"
    spec = importlib.util.spec_from_file_location("_fps_root", str(root_init))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    n = len(mod.NODE_CLASS_MAPPINGS)
    return f"{n} ノード = OK"
results.append(check("root/__init__.py", check_root))

# 結果サマリー
passed = sum(1 for r in results if r)
total  = len(results)
print(f"""
══════════════════════════════════════════════════════════
  結果: {passed}/{total} PASS
{"  ✅ ComfyUI で正常に動作します！" if passed == total else "  ⚠️ 上記の問題を修正してください"}
══════════════════════════════════════════════════════════
""")
sys.exit(0 if passed == total else 1)
