# Face Prompt Studio

Prompt Compiler Framework for Stable Diffusion / ComfyUI — 顔プロンプト
（face prompt）の最適化・クリーニング・ルールベース処理に特化した
プロフェッショナル品質のフレームワーク。

ComfyUI はアダプターの一つに過ぎない、ロングタームで拡張可能な
アーキテクチャを採用しています。

---

## ステータス

**v1.0.0** 🎉 — 正式リリース

| 指標 | 値 |
|---|---|
| 安定テスト通過数 | **843件 PASS** |
| 新規テスト（M5/M6） | +140件 |
| エンドポイント総数 | **20本**（REST API） |
| 辞書エントリ | **1169キー**（英語）+ **105キー**（日本語） |
| カテゴリ数 | 24カテゴリ |
| テンプレート | 5種（組み込み） |
| ComfyUI ノード | 10種 |

---

## 特徴

### Core Pipeline
- **顔特化辞書システム** — 24カテゴリ・1169キー（eyes / hair / expression /
  makeup / fantasy_parts / age / ethnicity など）+ 日本語105キー（MeCab不要）
- **同義語対応** — WD14 / JoyCaption / Florence2 / Qwen2-VL / InternVL /
  MiniCPM-V 主要キャプションモデルの出力タグを自動正規化
- **10ステージパイプライン** — Parser → Normalizer → Blacklist →
  Categorizer → RuleEngine → Optimizer → Exporter
- **JSON駆動ルールエンジン** — Python修正不要でタグの追加/削除/重み変更

### Optimizer（M6強化）
- **矛盾検出** — 同一排他グループ内の競合タグを自動検出（18グループ）
- **冗長検出** — 意味的に近いタグの重複を警告
- **ネガティブプロンプト最適化** ★NEW — positive/negative クロス矛盾検出
- **品質スコアリング** — coverage / balance / redundancy / negative_coverage
- **改善提案** — 不足カテゴリ・矛盾・バランス改善を自然言語で提案

### GUI Studio (M5)
- **REST API 20本** — FastAPI + Pydantic v2、OpenAPI自動生成
- **Web UI SPA** — Editor / Optimize / Presets / Knowledge / History
- **🔍 Knowledge Browser** — 24カテゴリ・タグ検索・同義語表示・エディタ連携
- **🕐 History Timeline** — スコア推移グラフ（SVG）・比較diff・お気に入り

### Templates（M6-3 NEW）
- **プロンプトテンプレートエンジン** — `{variable}` 形式の変数置換
- 組み込みテンプレート5種（基本顔・詳細顔・ファンタジー・ネガティブ・スタイル）
- `GET /templates`, `POST /templates/{id}/render`

### 多言語対応（M6-2 NEW）
- **日本語入力** — 「青い目」→ `Eyes.Blue` など105件のマッピング（MeCab不要）
- ひらがな・カタカナ・漢字キーに対応

### Platform
- **ComfyUI ノード10種** — Cleaner / Compiler / Debug / Preset / RuleEditor /
  CategoryFilter / Optimizer / History / CategoryGroup / GroupControl
- **出力アダプター** — A1111 / NovelAI / ComfyUI
- **CLI ツール** — `fps compile / optimize / history / preset / validate`
- **プラグインシステム** — 外部 `.py` からの動的ロード
- **イベントシステム** — 14種の EventType、優先度付き購読

---

## リポジトリ構造

```
fps/
├── fps-core/              Pure Python core（アダプター依存ゼロ）
│   ├── config/            ConfigManager
│   ├── fps_logging/       FPSLogger
│   ├── dictionary/        DictionaryManager（英語1169 + 日本語105）
│   ├── rules/             RuleManager
│   ├── pipeline/          PipelineManager（10ステージ）
│   ├── optimizer/         OptimizerManager（M6: ネガティブ対応）
│   ├── history/           HistoryManager（M5-0）
│   ├── template/          TemplateManager（M6-3）★NEW
│   ├── presets/           PresetManager
│   ├── plugins/           PluginRegistry
│   └── events/            EventBus（14種）
│
├── fps-adapters/          外部システム連携
│   ├── rest/              FastAPI REST API（20エンドポイント）
│   ├── comfyui/           ComfyUI ノード（10種）
│   ├── a1111/             AUTOMATIC1111 WebUI
│   ├── novelai/           NovelAI
│   └── input/             WD14 / JoyCaption / Florence2
│
├── fps-gui/
│   └── web/               index.html（SPA: Editor/Optimize/Presets/Knowledge/History）
│
├── fps-data/
│   ├── dictionaries/
│   │   ├── system/        英語辞書24ファイル + 日本語synonyms★NEW
│   │   └── user/          ユーザー辞書
│   └── templates/         テンプレートJSON★NEW
│
└── fps-tools/
    ├── cli/               fps CLI
    └── tests/unit/        843件以上のユニットテスト
```

---

## クイックスタート

```bash
# REST APIサーバー起動
uvicorn fps-adapters.rest.app:app --reload --port 8420

# 基本的なプロンプト処理
curl -X POST "http://localhost:8420/compile?prompt=masterpiece,blue_eyes,long_hair"

# 日本語でも動作
curl -X POST "http://localhost:8420/compile?prompt=高品質,青い目,長い髪"

# ネガティブプロンプト最適化
curl -X POST "http://localhost:8420/optimize?prompt=masterpiece&negative_prompt=low_quality,bad_anatomy"

# テンプレート展開
curl -X POST "http://localhost:8420/templates/face_basic/render" \
  -H "Content-Type: application/json" \
  -d '{"variables": {"quality": "masterpiece", "eye_color": "blue_eyes", "hair_color": "blonde", "hair_length": "long", "expression": "smile"}}'

# CLI
python -m fps compile "masterpiece, blue_eyes, long_hair"
python -m fps history list
```

---

## REST API エンドポイント一覧

| Method | Path | 説明 |
|---|---|---|
| POST | `/compile` | プロンプトコンパイル |
| POST | `/optimize?negative_prompt=` | 最適化分析（ネガティブ対応） |
| GET | `/dictionary/search` | タグ検索 |
| GET | `/dictionary/stats` | 辞書統計 |
| GET | `/dictionary/categories` | カテゴリ一覧 |
| GET | `/dictionary/entries` | エントリ検索 |
| GET | `/dictionary/synonyms` | 同義語取得 |
| GET | `/history` | 履歴一覧 |
| GET | `/history/{id}` | 履歴詳細 |
| POST | `/history/{id}/favorite` | お気に入りトグル |
| PUT | `/history/{id}/label` | ラベル設定 |
| GET | `/history/{id1}/diff/{id2}` | 差分比較 |
| DELETE | `/history/{id}` | 削除 |
| GET | `/presets` | プリセット一覧 |
| POST | `/presets/{id}/apply` | プリセット適用 |
| GET | `/templates` | テンプレート一覧 |
| POST | `/templates/{id}/render` | テンプレート展開 |
| POST | `/templates/render` | 直接展開 |
| POST | `/validate` | バリデーション |
| GET | `/health` | ヘルスチェック |

---

## 開発

```bash
# テスト実行（安定テスト）
python -m pytest fps-tools/tests/unit/ \
  --ignore=fps-tools/tests/unit/test_backup.py \
  --ignore=fps-tools/tests/unit/test_auto_backup.py \
  --ignore=fps-tools/tests/unit/test_cache.py \
  --ignore=fps-tools/tests/unit/test_pipeline_cache.py \
  --ignore=fps-tools/tests/unit/test_python_facade.py \
  --no-cov -q

# Lint
ruff check fps-core/ fps-adapters/ fps-tools/

# 型チェック
mypy fps-core/ fps-adapters/
```

---

## ライセンス

MIT License — © 2026 glasssoundforest-lab
