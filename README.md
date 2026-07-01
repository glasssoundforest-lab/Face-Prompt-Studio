# Face Prompt Studio

Stable Diffusion / ComfyUI 向け顔プロンプト最適化フレームワーク。

タグの正規化・矛盾検出・スコアリング・テンプレート展開をまとめて行う
プロダクションレディなプロンプト管理プラットフォームです。

ComfyUI はアダプターの一つに過ぎない、長期拡張可能な
Clean Architecture を採用しています。

---

## ステータス

**v1.7.0** — Preset エディタ Web UI 完了（2026-07-02）

| 指標 | 値 |
|---|---|
| テスト | **1152 PASS / 0 FAILED** |
| REST API | **28 エンドポイント**（+4） |
| 辞書キー総数 | **2793キー**（英語 + 日本語） |
| 日本語エントリ | **517件**（21カテゴリ） |
| ComfyUI ノード | **11種** |
| テンプレート | **5種**（組み込み） |
| Python ファイル | 132本 |

---

## v1.7.0 新機能

### ① PresetManager CRUD

```python
from preset.manager import PresetManager
from preset.models import Preset, PresetSource, PresetTag

pm = PresetManager(system_dir="fps-data/presets/system",
                   user_dir="fps-data/presets/user")
pm.load()

# 新規作成
preset = Preset(
    id="my_anime",
    name="アニメ風",
    tags=[PresetTag("anime_style"), PresetTag("colorful")],
    source=PresetSource.USER,
)
pm.save(preset)

# 部分更新（★v1.7）
pm.update("my_anime", name="アニメ風 v2",
          tags=[PresetTag("anime_style"), PresetTag("soft_light")])

# タグ追記（★v1.7）
pm.add_tags("my_anime", [PresetTag("detailed_eyes")])

# 削除
pm.delete("my_anime")
```

### ② REST API Preset CRUD（+4エンドポイント）

```
POST   /presets                    # 新規作成（201 Created）
PUT    /presets/{id}               # 部分更新
DELETE /presets/{id}               # 削除（200）
POST   /presets/{id}/tags/add      # タグ追記
```

### ③ CliContext に template_manager 統合（技術的負債4 解消）

```python
ctx = CliContext()
tm = ctx.template_manager   # 遅延初期化・スレッドセーフ
```

---

## バージョン履歴

| バージョン | 内容 |
|---|---|
| v0.5.0 | Phase 1 — Dictionary / Rule / Pipeline コア実装 |
| v0.8.0 | Phase 4 — AI Adapter Layer（A1111/NovelAI/Input/Plugin/Event） |
| v1.0.0 | 正式リリース |
| v1.1.0 | テスト完全グリーン化 / cache・backup 実装 / CI 整備 |
| v1.2.0 | Knowledge Browser 強化 / ComfyUI テンプレートノード / 日本語辞書拡充 |
| v1.5.0 | AI スコアリング強化（combination_checker / QualityScore 5スコア体制） |
| v1.6.0 | 日本語辞書大規模拡充（228 → 517件、21カテゴリ） |
| **v1.7.0** | **Preset エディタ Web UI / PresetManager CRUD / CliContext 統合** |

---

## 機能一覧

### Core（fps-core）

| モジュール | 概要 |
|---|---|
| `dictionary/` | タグ辞書管理（CRUD対応、日本語517件） |
| `preset/` | プリセット管理（★v1.7 CRUD追加） |
| `optimizer/` | 品質分析・スコアリング（5スコア体制） |
| `pipeline/` | プロンプトコンパイルパイプライン（10ステージ） |
| `template/` | プロンプトテンプレートエンジン |
| `history/` | 変換履歴・差分比較 |
| `cache/` | LRU + TTL キャッシュ |
| `backup/` | バックアップ管理 |

### REST API（28エンドポイント）

| Method | Path | 概要 |
|---|---|---|
| GET | `/health` | ヘルスチェック |
| POST | `/compile` | プロンプトコンパイル |
| POST | `/optimize` | 最適化分析 |
| GET | `/dictionary/search` | タグ検索 |
| GET | `/dictionary/stats` | 辞書統計 |
| GET | `/dictionary/categories` | カテゴリ一覧 |
| GET | `/dictionary/entries` | エントリ検索 |
| GET | `/dictionary/synonyms` | 同義語取得 |
| GET | `/dictionary/user/entries` | ユーザー辞書一覧 |
| POST | `/dictionary/user/entries` | エントリ追加 |
| PUT | `/dictionary/user/entries/{key}` | 部分更新 |
| DELETE | `/dictionary/user/entries/{key}` | 削除 |
| GET | `/presets` | プリセット一覧 |
| **POST** | **`/presets`** | **新規作成 ★v1.7** |
| POST | `/presets/{id}/apply` | プリセット適用 |
| **PUT** | **`/presets/{id}`** | **部分更新 ★v1.7** |
| **DELETE** | **`/presets/{id}`** | **削除 ★v1.7** |
| **POST** | **`/presets/{id}/tags/add`** | **タグ追記 ★v1.7** |
| GET | `/history` | 履歴一覧 |
| GET | `/history/{id}` | 履歴詳細 |
| POST | `/history/{id}/favorite` | お気に入りトグル |
| PUT | `/history/{id}/label` | ラベル設定 |
| GET | `/history/{id1}/diff/{id2}` | 差分比較 |
| DELETE | `/history/{id}` | 削除 |
| POST | `/validate` | バリデーション |
| GET | `/templates` | テンプレート一覧 |
| POST | `/templates/{id}/render` | テンプレート展開 |
| POST | `/templates/render` | 直接展開 |

### ComfyUI ノード（11種）

| ノード | 概要 |
|---|---|
| FacePromptCleanerNode | プロンプトクリーニング |
| FacePromptCompilerNode | 辞書引きコンパイル |
| FacePromptDebugNode | デバッグ出力 |
| FacePromptPresetNode | プリセット適用 |
| FacePromptRuleEditorNode | ルール編集・適用 |
| FacePromptCategoryFilterNode | カテゴリフィルタリング |
| FacePromptOptimizerNode | 品質最適化 |
| FacePromptHistoryNode | 履歴記録・参照 |
| FacePromptBackupNode | バックアップ・リストア |
| FacePromptGroupControlNode | グループ重み一括制御 |
| FacePromptTemplateNode | テンプレート展開 |

---

## クイックスタート

```bash
# インストール
pip install -e fps-core
pip install -e "fps-adapters[rest]"

# REST API サーバー起動（ポート 8420）
uvicorn fps-adapters.rest.app:app --reload --port 8420

# Web UI
open http://localhost:8420/
```

## テスト実行

```bash
cd fps
python -m pytest fps-tools/tests/unit/ --no-cov -q
# → 1152 passed
```

---

## リポジトリ構造

```
fps/
├── fps-core/                    Pure Python core（アダプター依存ゼロ）
│   ├── cache/                   LRUCache + TTL
│   ├── backup/                  BackupManager
│   ├── config/                  ConfigManager
│   ├── dictionary/              DictionaryManager（CRUD対応）
│   ├── optimizer/               OptimizerManager + combination_checker
│   ├── preset/                  PresetManager（★v1.7 update/add_tags追加）
│   ├── pipeline/                PipelineManager（10ステージ）
│   └── template/                TemplateManager
│
├── fps-adapters/
│   ├── cli/
│   │   └── context.py           CliContext（★v1.7 template_manager追加）
│   ├── comfyui/nodes/           ComfyUI ノード（11種）
│   └── rest/
│       ├── app.py               FastAPI（★v1.7 Preset CRUD追加、28エンドポイント）
│       └── models.py            Pydantic スキーマ（★v1.7 Preset CRUD スキーマ追加）
│
├── fps-gui/web/
│   └── index.html               Web UI SPA
│
├── fps-data/
│   ├── dictionaries/system/synonyms/japanese_tags.json  （517件）
│   ├── presets/system/          組み込みプリセット
│   ├── presets/user/            ユーザープリセット（★v1.7 CRUD対象）
│   └── rules/
│
└── fps-tools/tests/unit/        1152件 PASS
```

---

## ライセンス

MIT License
