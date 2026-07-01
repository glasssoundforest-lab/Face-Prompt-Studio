# Face Prompt Studio

**Stable Diffusion / ComfyUI 向け顔プロンプト最適化・管理フレームワーク**

[![CI](https://github.com/glasssoundforest-lab/Face-Prompt-Studio/actions/workflows/ci.yml/badge.svg)](https://github.com/glasssoundforest-lab/Face-Prompt-Studio/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![Version](https://img.shields.io/badge/version-2.0.0-brightgreen)
![Tests](https://img.shields.io/badge/tests-1250%20PASS-brightgreen)

---

## 概要

Face Prompt Studio（FPS）は Stable Diffusion / ComfyUI 向けの顔プロンプト最適化・管理フレームワークです。

**設計方針:**
- **Clean Architecture** — `fps-core` はアダプター依存ゼロ
- **ComfyUI はアダプターの一つ**（差し替え可能）
- **辞書・ルールはすべて JSON で定義**（Python 修正不要）
- **WebSocket リアルタイム更新**（v1.9〜）
- **パーソナライゼーション基盤**（v2.0〜）

---

## 現在のバージョン: v2.0.0

**v2.0.0** — パーソナライゼーション基盤 完了（2026-07-02）

| 指標 | 値 |
|---|---|
| テスト | **1250 PASS / 0 FAILED** |
| REST API | **48 エンドポイント**（HTTP 39 + WS 4 + Profile 9） |
| 辞書キー総数 | **2793キー**（英語 + 日本語） |
| 日本語エントリ | **1002件**（41カテゴリ） |
| ComfyUI ノード | **11種** |
| テンプレート | **5種**（組み込み） |
| Python ファイル | **145本** |
| Web UI タブ | **7タブ**（Editor/Optimize/Presets/History/Backup/Profile/Dashboard） |

---

## バージョン履歴

| バージョン | 内容 |
|---|---|
| v0.5.0 | Phase 1 — Dictionary / Rule / Pipeline コア実装 |
| v0.8.0 | Phase 4 — AI Adapter Layer（A1111/NovelAI/Input/Plugin/Event） |
| v1.0.0 | 正式リリース |
| v1.1.0 | テスト完全グリーン化 / cache・backup 実装 / CI 整備 |
| v1.2.0 | Knowledge Browser 強化 / ComfyUI テンプレートノード |
| v1.5.0 | AI スコアリング強化（combination_checker / QualityScore 5スコア体制） |
| v1.6.0 | 日本語辞書大規模拡充（228 → 517件、21カテゴリ） |
| v1.7.0 | Preset エディタ Web UI / PresetManager CRUD / CliContext 統合 |
| v1.8.0 | バックアップ Web UI / History 強化 / ダッシュボード |
| v1.9.0 | WebSocket リアルタイム更新（pipeline / history / events 3チャンネル） |
| **v2.0.0** | **パーソナライゼーション基盤（UserProfileManager / 推奨 / スコアトレンド）** |

---

## v2.0.0 新機能

### ① UserProfileManager（`fps-core/user/` 新設）

```python
from user.manager import UserProfileManager

upm = UserProfileManager(profile_dir=Path("fps-data/user"))
upm.load()

# 履歴から学習
upm.learn(history_entries)

# 推奨タグ Top20
recs = upm.recommend(20)

# プロファイルをタグリストに適用
result_tags = upm.apply_profile(["masterpiece", "bad_quality", "soft_light"])

# タグ重み設定（0.0 = 除外, 2.0 = 強調）
upm.set_tag_weight("watermark", weight=0.0)
upm.set_tag_weight("soft_light", weight=2.0)
```

### ② REST API — `/profile` エンドポイント（+9本）

```
GET    /profile                    # プロファイル概要
POST   /profile/learn              # 履歴から学習
GET    /profile/recommendations    # 推奨タグ
GET    /profile/score-trend        # スコアトレンド（グラフ用）
PUT    /profile/tags/{tag}/weight  # タグ重み設定
DELETE /profile/tags/{tag}/weight  # タグ重み削除
POST   /profile/rules              # スタイルルール追加
DELETE /profile/rules/{id}         # スタイルルール削除
DELETE /profile/reset              # プロファイルリセット
```

### ③ WebSocket 3チャンネル（v1.9〜）

```javascript
// コンパイル進捗リアルタイム受信
const ws = new WebSocket("ws://localhost:8420/ws/pipeline");
ws.onmessage = (e) => {
  const { type, data } = JSON.parse(e.data);
  if (type === "stage.after_run") console.log("✓", data.stage);
};

// 新規履歴を自動受信
const wsH = new WebSocket("ws://localhost:8420/ws/history");
wsH.onmessage = (e) => {
  if (JSON.parse(e.data).type === "history.recorded") refreshList();
};
```

---

## クイックスタート

```bash
# インストール
pip install -e fps-core
pip install -e "fps-adapters[rest]"

# REST API + WebSocket サーバー起動
uvicorn fps-adapters.rest.app:app --reload --port 8420

# Web UI（7タブ）
open http://localhost:8420/
```

## テスト実行

```bash
python -m pytest fps-tools/tests/unit/ --no-cov -q
# → 1250 passed
```

---

## リポジトリ構造

```
fps/
├── fps-core/                    Pure Python core（アダプター依存ゼロ）
│   ├── cache/                   LRUCache + TTL
│   ├── backup/                  BackupManager
│   ├── dictionary/              DictionaryManager（日本語1002件/41カテゴリ）
│   ├── events/                  EventBus（WebSocket統合）
│   ├── history/                 HistoryManager
│   ├── optimizer/               OptimizerManager（5スコア体制）
│   ├── pipeline/                PipelineManager（10ステージ）
│   ├── preset/                  PresetManager（CRUD）
│   ├── template/                TemplateManager
│   └── user/                    ★v2.0 UserProfileManager
│
├── fps-adapters/
│   ├── cli/context.py           CliContext（全Manager統合）
│   ├── comfyui/nodes/           ComfyUI ノード（11種）
│   └── rest/
│       ├── app.py               FastAPI（48エンドポイント）
│       └── ws.py                WebSocket ブリッジ（v1.9）
│
├── fps-gui/web/index.html       SPA（7タブ）
│
└── fps-data/
    ├── dictionaries/            辞書（英語+日本語1002件）
    ├── presets/                 プリセット（system/user）
    ├── rules/                   ルール定義
    └── user/profile.json        ★v2.0 パーソナルプロファイル
```

---

## ライセンス

MIT License
