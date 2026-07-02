#!/usr/bin/env python3
"""
scripts/init_fps_data.py — FacePromptStudio データディレクトリ初期化

ComfyUI にインストール直後に実行してください:
    cd ComfyUI/custom_nodes/FacePromptStudio
    python scripts/init_fps_data.py

このスクリプトは以下を行います:
  1. fps-data/ の必要なサブディレクトリを全て作成
  2. 不足しているデフォルトルールファイルを生成
  3. 動作確認チェックを実行
"""
from __future__ import annotations
import json, sys
from datetime import datetime
from pathlib import Path

_ROOT     = Path(__file__).resolve().parents[1]
_DATA     = _ROOT / "fps-data"
_NOW      = datetime.now().isoformat()

OK = "✅"; NG = "❌"; INFO = "ℹ️"

print(f"""
╔══════════════════════════════════════════════════════════════╗
║  FacePromptStudio データディレクトリ初期化スクリプト v2.7    ║
╚══════════════════════════════════════════════════════════════╝
リポジトリルート: {_ROOT}
fps-data パス  : {_DATA}
""")

errors = 0

def mkdir(path: Path, label: str = "") -> None:
    path.mkdir(parents=True, exist_ok=True)
    print(f"  {OK} {label or path.relative_to(_ROOT)}/")

def write_json(path: Path, data: dict, label: str = "") -> None:
    if path.exists():
        print(f"  {INFO} {label or path.name} — 既存のためスキップ")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {OK} {label or path.name} — 作成しました")

# ── 1. ディレクトリ作成 ─────────────────────────────────────────
print("── 1. ディレクトリ構造を作成 ────────────────────────────────")
for d in [
    "dictionaries/system/synonyms",
    "dictionaries/user",
    "presets/system",
    "presets/user",
    "presets/versions",
    "rules",
    "templates/system",
    "user",
    "wildcards",
    "backup",
    "history",
    "characters",
]:
    mkdir(_DATA / d)

# ── 2. デフォルトルールファイル ─────────────────────────────────
print("
── 2. デフォルトルールファイルを生成 ────────────────────────")
write_json(_DATA / "rules" / "style_combinations.json", {
    "version": "1.0",
    "incompatible_pairs": [
        {"tags": ["anime_style", "photorealistic"], "reason": "スタイルが矛盾"},
        {"tags": ["soft_light", "hard_light"],      "reason": "ライティングが矛盾"},
        {"tags": ["short_hair", "long_hair"],        "reason": "髪の長さが矛盾"},
        {"tags": ["1girl", "1boy"],                  "reason": "性別が矛盾"},
    ],
    "recommended_pairs": [
        {"tags": ["masterpiece", "best_quality"],   "reason": "品質タグの組み合わせ"},
        {"tags": ["anime_style", "detailed_face"],   "reason": "アニメスタイルの定番"},
    ],
    "token_budget": {"max_tokens": 75, "warn_threshold": 0.8, "critical_threshold": 1.0},
}, "style_combinations.json")

write_json(_DATA / "rules" / "category_weights.json", {
    "version": "1.0",
    "weights": {
        "quality":    1.5,
        "style":      1.3,
        "face":       1.2,
        "eyes":       1.1,
        "hair":       1.1,
        "expression": 1.0,
        "clothing":   0.9,
        "background": 0.8,
        "pose":       0.8,
        "lighting":   0.9,
    }
}, "category_weights.json")

# ── 3. デフォルトシステムプリセット ────────────────────────────
print("
── 3. デフォルトプリセットを生成 ────────────────────────────")
presets = [
    ("anime_portrait", "アニメポートレート", [
        {"tag": "masterpiece", "category": "quality", "weight": 1.5},
        {"tag": "anime_style", "category": "style",   "weight": 1.3},
        {"tag": "detailed_face", "category": "face",  "weight": 1.2},
        {"tag": "soft_light",  "category": "lighting","weight": 1.0},
    ]),
    ("realistic_portrait", "写実ポートレート", [
        {"tag": "masterpiece",       "category": "quality",  "weight": 1.5},
        {"tag": "photorealistic",    "category": "style",    "weight": 1.3},
        {"tag": "detailed_face",     "category": "face",     "weight": 1.2},
        {"tag": "studio_lighting",   "category": "lighting", "weight": 1.0},
    ]),
    ("quality_base", "品質ベース", [
        {"tag": "masterpiece",   "category": "quality", "weight": 1.5},
        {"tag": "best_quality",  "category": "quality", "weight": 1.4},
        {"tag": "ultra_detailed","category": "quality", "weight": 1.2},
    ]),
]
for pid, name, tags in presets:
    write_json(_DATA / "presets" / "system" / f"{pid}.json", {
        "id": pid, "name": name, "description": f"デフォルトプリセット: {name}",
        "version": "1.0", "source": "system",
        "tags": tags, "negative_tags": [],
        "meta": {"created_by": "init_fps_data.py", "created_at": _NOW},
    }, f"presets/system/{pid}.json")

# ── 4. デフォルト Wildcard（存在しない場合のみ）──────────────────
print("
── 4. Wildcard データを確認 ──────────────────────────────────")
wc_dir = _DATA / "wildcards"
wc_count = len(list(wc_dir.glob("*.json")))
if wc_count > 0:
    print(f"  {OK} Wildcard: {wc_count}件 存在（スキップ）")
else:
    print(f"  {INFO} Wildcard がありません。git pull で取得してください。")

# ── 5. 動作チェック ────────────────────────────────────────────
print("
── 5. インポートチェック ─────────────────────────────────────")
for _p in [str(_ROOT / "fps-core"), str(_ROOT / "fps-adapters")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

for module, label in [
    ("dictionary.manager", "DictionaryManager"),
    ("pipeline.manager",   "PipelineManager"),
    ("wildcard.engine",    "WildcardEngine"),
    ("ai.lora_analyzer",   "LoraAnalyzer"),
]:
    try:
        __import__(module)
        print(f"  {OK} {label}")
    except Exception as e:
        print(f"  {NG} {label}: {e}")
        errors += 1

# ── 結果 ────────────────────────────────────────────────────────
print(f"""
══════════════════════════════════════════════════════════════
  初期化{"完了" if errors == 0 else "（警告あり）"}
  エラー数: {errors}
  fps-data パス: {_DATA}

  次のステップ:
    1. python scripts/verify_comfyui.py  （動作確認）
    2. ComfyUI を再起動
    3. FacePromptStudio カテゴリのノードを確認
══════════════════════════════════════════════════════════════
""")
sys.exit(0 if errors == 0 else 1)
