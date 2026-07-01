# Face Prompt Studio

Stable Diffusion / ComfyUI 向け顔プロンプト最適化フレームワーク。

タグの正規化・矛盾検出・スコアリング・テンプレート展開をまとめて行う
プロダクションレディなプロンプト管理プラットフォームです。

ComfyUI はアダプターの一つに過ぎない、長期拡張可能な
Clean Architecture を採用しています。

---

## ステータス

**v1.6.0** — 日本語辞書大規模拡充 完了（2026-07-01）

| 指標 | 値 |
|---|---|
| テスト | **1122 PASS / 0 FAILED** |
| REST API | **24 エンドポイント** |
| 辞書キー総数 | **2793キー**（英語 + 日本語） |
| 日本語エントリ | **517件**（21カテゴリ） |
| ComfyUI ノード | **11種** |
| テンプレート | **5種**（組み込み） |
| Python ファイル | 130本 |

---

## 機能一覧

### Core Pipeline（10ステージ）
Parser → Normalizer → Blacklist → Categorizer → RuleEngine → Optimizer → Exporter

- **顔特化辞書** — 英語1169キー + 日本語517キー（MeCab不要）
- **同義語対応** — WD14 / JoyCaption / Florence2 / Qwen2-VL 対応
- **JSON駆動ルールエンジン** — Python 修正不要

### Optimizer（v1.5 AI強化）

| スコア | 内容 | 重み |
|---|---|---|
| coverage_score | 重要カテゴリ網羅度 | 0.25 |
| balance_score | 重みバランス | 0.20 |
| redundancy_score | 非冗長性 | 0.25 |
| **combination_score** | ★スタイル一貫性 | 0.20 |
| **token_score** | ★トークンバジェット | 0.10 |

- **矛盾検出** — 18グループの排他チェック
- **スタイル組み合わせチェック** ★v1.5 — 非推奨8ペア / 推奨5ペア
- **トークンバジェット警告** ★v1.5 — CLIP 75トークン上限
- **ネガティブプロンプト最適化** — cross-conflict 検出

### 日本語辞書（v1.6 大幅拡充）★

517件、21カテゴリ完全対応。MeCab 不要のキーワードマッチ方式。

```
目(40) / スタイル(46) / ファンタジー(62) / 衣装(45) / 表情(41)
髪(38) / アクセサリー(33) / メイク(25) / 年齢(23) / 肌(22)
体型(20) / 顔型(16) / 眉(16) / 民族(16) / 口(14) / 歯(11)
品質(10) / まつ毛(10) / 鼻(10) / 眼鏡(10) / ピアス(9)
```

対応例: `「萌え」「ギャル」「VTuber風」「九尾」「天狗」「凛々しい」「中性的」`

### GUI Studio（REST API + Web UI）

- **REST API 24本** — FastAPI + Pydantic v2
- **Web UI SPA** — Editor / Optimize / Presets / Knowledge / History
- **Knowledge Browser** ★v1.2 — ユーザー辞書 CRUD（4エンドポイント）
- **History Timeline** — SVGグラフ・差分比較・お気に入り

### テンプレートエンジン

5種の組み込みテンプレート（`face_basic` / `face_detailed` / `fantasy_character` / `negative_basic` / `style_transfer`）

### ComfyUI ノード 11種 ★v1.3

`FacePromptCleaner` / `FacePromptCompiler` / `FacePromptDebug` /
`FacePromptPreset` / `FacePromptRuleEditor` / `FacePromptCategoryFilter` /
`FacePromptOptimizer` / `FacePromptHistory` / `FacePromptBackup` /
`FacePromptGroupControl` / **`FacePromptTemplate`**

---

## REST API エンドポイント（24本）

| Method | Path | 概要 |
|---|---|---|
| GET | `/health` | ヘルスチェック |
| POST | `/compile` | プロンプトコンパイル |
| POST | `/optimize` | 最適化（ネガティブ対応） |
| POST | `/validate` | バリデーション |
| GET | `/dictionary/search` | タグ検索 |
| GET | `/dictionary/stats` | 辞書統計 |
| GET | `/dictionary/categories` | カテゴリ一覧 |
| GET | `/dictionary/entries` | エントリ検索 |
| GET | `/dictionary/synonyms` | 同義語取得 |
| GET | `/dictionary/user/entries` | ★ユーザー辞書一覧 |
| POST | `/dictionary/user/entries` | ★ユーザー辞書追加 |
| PUT | `/dictionary/user/entries/{key}` | ★ユーザー辞書更新 |
| DELETE | `/dictionary/user/entries/{key}` | ★ユーザー辞書削除 |
| GET | `/presets` | プリセット一覧 |
| POST | `/presets/{id}/apply` | プリセット適用 |
| GET | `/history` | 履歴一覧 |
| GET | `/history/{id}` | 履歴詳細 |
| POST | `/history/{id}/favorite` | お気に入りトグル |
| PUT | `/history/{id}/label` | ラベル設定 |
| GET | `/history/{id1}/diff/{id2}` | 差分比較 |
| DELETE | `/history/{id}` | 削除 |
| GET | `/templates` | テンプレート一覧 |
| POST | `/templates/{id}/render` | テンプレート展開 |
| POST | `/templates/render` | 直接展開 |

---

## クイックスタート

```bash
# REST API サーバー起動
uvicorn fps-adapters.rest.app:app --reload --port 8420

# Web UI
open http://localhost:8420/

# 英語プロンプト
curl -X POST "http://localhost:8420/compile?prompt=masterpiece,blue_eyes,long_hair"

# 日本語プロンプト
curl -X POST "http://localhost:8420/compile?prompt=高品質,青い目,長い髪,萌え"

# スタイル組み合わせチェック付き最適化
curl -X POST "http://localhost:8420/optimize?prompt=masterpiece,anime_style,photorealistic"

# テンプレート展開
curl -X POST "http://localhost:8420/templates/face_basic/render" \
  -H "Content-Type: application/json" \
  -d '{"variables":{"quality":"masterpiece","eye_color":"blue_eyes","hair_color":"blonde","hair_length":"long","expression":"smile"}}'
```

---

## プロジェクト構造

```
fps/
├── fps-core/          Pure Python core（アダプター依存ゼロ）
│   ├── cache/         CacheManager / LRUCache          ★v1.1
│   ├── backup/        BackupManager                    ★v1.1
│   ├── config/        ConfigManager
│   ├── dictionary/    DictionaryManager（CRUD対応）    ★v1.2
│   ├── events/        EventBus（14種）
│   ├── fps_logging/   FPSLogger
│   ├── history/       HistoryManager
│   ├── optimizer/     OptimizerManager
│   │   ├── combination_checker.py  ★v1.5 スタイル/トークン
│   │   ├── conflict_detector.py
│   │   ├── quality_scorer.py       ★v1.5 5スコア体制
│   │   └── redundancy_detector.py
│   ├── pipeline/      PipelineManager（10ステージ）
│   ├── plugins/       PluginRegistry
│   ├── preset/        PresetManager
│   ├── rules/         RuleManager
│   └── template/      TemplateManager                  ★M6-3
│
├── fps-adapters/
│   ├── a1111/         AUTOMATIC1111 アダプター
│   ├── comfyui/       ComfyUI ノード 11種              ★v1.3
│   ├── novelai/       NovelAI アダプター
│   ├── input/         WD14 / JoyCaption / Florence2
│   └── rest/          FastAPI 24エンドポイント          ★v1.2
│
├── fps-gui/web/       SPA Web UI（5タブ）
│
├── fps-data/
│   ├── dictionaries/system/
│   │   ├── *.json     英語辞書（24カテゴリ）
│   │   └── synonyms/
│   │       ├── japanese_tags.json  ★v1.6 517件
│   │       └── wd14_tags.json 他
│   └── rules/
│       └── style_combinations.json  ★v1.5
│
└── fps-tools/tests/unit/   34ファイル / 1122件 PASS
```

---

## 開発

```bash
# テスト（全件）
python -m pytest fps-tools/tests/unit/ --no-cov -q

# Lint
ruff check fps-core/ fps-adapters/ fps-tools/

# 型チェック
mypy fps-core/ fps-adapters/ --ignore-missing-imports
```

---

## タグ履歴

| タグ | 内容 |
|---|---|
| v1.6.0 | 日本語辞書 228→517件（★今ここ） |
| v1.5.0 | AI スコアリング強化（スタイル/トークン） |
| v1.2.0 | KB強化+テンプレートノード+日本語228件 |
| v1.1.0 | テスト完全グリーン化（1032件） |
| v1.0.0 | 正式リリース |
| v0.9.5 | Phase 5+6 完了 |
| v0.8.0 | Phase 4 AI Adapter Layer |

---

## ライセンス

MIT License — © 2026 glasssoundforest-lab
