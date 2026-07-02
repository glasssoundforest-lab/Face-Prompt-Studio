# Face Prompt Studio

**Stable Diffusion / ComfyUI 向け顔プロンプト最適化・管理フレームワーク**

[![CI](https://github.com/glasssoundforest-lab/Face-Prompt-Studio/actions/workflows/ci.yml/badge.svg)](https://github.com/glasssoundforest-lab/Face-Prompt-Studio/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![Version](https://img.shields.io/badge/version-2.0.0-brightgreen)
![Tests](https://img.shields.io/badge/tests-1250%20PASS-brightgreen)

---

## 概要

Face Prompt Studio（FPS）は Stable Diffusion / ComfyUI 向けの顔プロンプト（face prompt）最適化・管理フレームワークです。

**設計方針:**
- **Clean Architecture** — `fps-core` はアダプター依存ゼロ
- **ComfyUI はアダプターの一つ**（差し替え可能）
- **辞書・ルールはすべて JSON で定義**（Python 修正不要）
- **WebSocket リアルタイム更新**（v1.9〜）
- **パーソナライゼーション基盤**（v2.0〜）

---

## 現在のバージョン: v2.0.0

**v2.6.0** — Wildcard エンジン / プロンプトマクロ / サーバーメトリクス（2026-07-02）

| 指標 | 値 |
|---|---|
| テスト | **1640 PASS / 0 FAILED** |
| REST API | **98 エンドポイント**（+6 v2.7 追加） |
| 辞書キー総数 | **2793キー**（英語 + 日本語） |
| 日本語エントリ | **1002件**（41カテゴリ） |
| ComfyUI ノード | **20種** |
| テンプレート | **5種**（組み込み） |
| Python ファイル | **145本** |
| Web UI タブ | **12タブ**（+Wildcard） |

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
| v1.8.0 | バックアップ Web UI / History 強化（検索・エクスポート・統計）/ ダッシュボード |
| v1.9.0 | WebSocket リアルタイム更新（pipeline / history / events 3チャンネル） |
| **v2.0.0** | **パーソナライゼーション基盤（UserProfileManager / 推奨 / スコアトレンド）** |
| **v2.1.0** | **compile × Profile 統合 / 自動学習 / 重みスライダー UI / pos・neg に直接反映** |
| **v2.2.0** | **ComfyUI 統合強化（14ノード）/ SQLite 移行 / 高度タグ検索 / History 全文検索** |
| **v2.3.0** | **多ユーザー対応（APIキー認証）/ プリセット共有 / コミュニティタグ統計** |
| **v2.4.0** | **バッチ処理 / タグ補完 / プロファイル Export/Import / プリセットバージョン管理** |
| **v2.5.0** | **AI 強化 / LoRA 統合 / スタイル一貫性チェック / Negative 学習** |
| **v2.6.0** | **Wildcard エンジン / プロンプトマクロ / ComfyUI バリエーション生成 / メトリクス** |
| **v2.7.0** | **ComfyUI 実稼働対応（importlib修正）/ キャラクターシート / 初期化スクリプト** |

---

## v2.7.0 新機能

### ① ComfyUI 実稼働対応（🔴 重要修正）

**修正された問題:**

| 問題 | 修正内容 |
|---|---|
| `fps-adapters`（ハイフン名）が `import` できない | `root/__init__.py` を `importlib.util` ベースに書き直し |
| `data_root` が相対パスで ComfyUI 実行時に fps-data が見つからない | `node_base.py` / `CliContext` で `Path(__file__).resolve()` による絶対パスに変更 |
| ノード1つのロード失敗で全ノードが使えなくなる | 個別 `try/except` で部分ロード対応 |

**インストール後の確認:**

```bash
cd ComfyUI/custom_nodes/FacePromptStudio

# Step 1: データディレクトリを初期化
python scripts/init_fps_data.py

# Step 2: 動作確認
python scripts/verify_comfyui.py
# → 全チェック PASS なら ComfyUI を再起動
```

### ② キャラクターシート（fps-core/character/ 新設）

```bash
# キャラクター作成
POST /characters
{
  "id": "alice",
  "name": "Alice",
  "features": [
    {"tag": "blue_eyes",    "category": "eyes", "weight": 1.2},
    {"tag": "blonde_hair",  "category": "hair", "weight": 1.2},
    {"tag": "fair_skin",    "category": "skin", "weight": 1.0}
  ],
  "neg_features": [{"tag": "brown_eyes", "weight": 1.0}]
}

# pos/neg プロンプトを取得
GET /characters/alice
# → {"pos_prompt": "(blue_eyes:1.2), (blonde_hair:1.2), fair_skin", "neg_prompt": "brown_eyes", ...}

# プリセットに変換
POST /characters/alice/to-preset  → presets/user/char_alice.json
```

### ③ 🎭 Face Prompt Character ノード（ComfyUI 20ノード目）

```
[character_id: "alice"]
[extra_tags: "__style__, masterpiece"]  ← Wildcard 構文も使用可
         ↓
[🎭 Face Prompt Character]
  apply_wildcard: true
         ↓
  pos_prompt → [🎭 Face Prompt Compiler] → KSampler
  neg_prompt → KSampler (negative)
```

### ④ デフォルト Wildcard データ（8種）

`fps-data/wildcards/` に以下が同梱:
`style` / `quality` / `lighting` / `hair_color` / `eye_color` / `background` / `emotion` / `pose`

---

## v2.6.0 新機能

### ① fps-core/wildcard/ — Wildcard エンジン（新設）

```python
from wildcard.engine import WildcardEngine
from wildcard.manager import WildcardManager

wm = WildcardManager(wildcard_dir=Path("fps-data/wildcards"))
wm.create("style", ["anime_style", "photorealistic", "oil_painting"])
wm.create("lighting", ["soft_light", "hard_light", "golden_hour"])

engine = WildcardEngine(wildcard_manager=wm)

# 毎回異なる展開結果
result = engine.expand("__style__, __lighting__, [[detailed|simple]] background")
# → "anime_style, golden_hour, detailed background"

# 5パターンのプレビュー生成
variants = engine.preview_expand("__style__, [[blue|red|green]] eyes", n=5)
```

**サポート構文:**

| 構文 | 説明 | 例 |
|---|---|---|
| `__name__` | Wildcard ファイルからランダム選択 | `__style__` |
| `[[A\|B\|C]]` | インラインランダム選択 | `[[anime\|realistic]]` |
| `[[A\|B\|C]]:2` | n件ランダム選択 | `[[red\|blue\|green]]:2` |
| `[[A:2\|B:1]]` | 重み付きランダム | 2:1の比率で選択 |
| `{{var:default}}` | 変数展開 | `{{quality:masterpiece}}` |
| `{A\|B\|C}` | A1111 互換 | `{soft\|hard} light` |

### ② REST API +9本（Wildcard CRUD + メトリクス）

```
GET    /wildcards                  Wildcard 一覧
POST   /wildcards                  新規作成
GET    /wildcards/{name}           取得（エントリ含む）
PUT    /wildcards/{name}           更新
DELETE /wildcards/{name}           削除
POST   /wildcards/expand           展開プレビュー（n件生成）
POST   /wildcards/{name}/import    テキスト形式インポート
GET    /metrics                    JSON 形式メトリクス
GET    /metrics/prometheus         Prometheus テキスト形式
```

### ③ 🎭 Face Prompt Wildcard ノード（ComfyUI 19ノード目）

```
[プロンプトテンプレート]
  "__style__, [[detailed|simple]] background, {{quality:masterpiece}}"
         ↓
[🎭 Face Prompt Wildcard]  seed=-1（毎回ランダム）
         ↓
  expanded_prompt → [🎭 Face Prompt Compiler] → KSampler
  all_variants    → 5パターンのテキスト表示（比較用）
```

### ④ Web UI — Wildcard タブ（12タブ目）

- **Wildcard 一覧** — サイドバーに全Wildcard を表示
- **展開プレビュー** — プロンプトを n パターン即座にプレビュー
- **Wildcard 作成** — 名前・値リスト・説明でワンクリック作成
- **構文リファレンス** — 全構文を常時表示

---

## v2.5.0 新機能

### ① fps-core/ai/ — AI 強化モジュール（新設）

| ファイル | クラス | 概要 |
|---|---|---|
| `lora_analyzer.py` | `LoraAnalyzer` | SafeTensors メタデータ解析・タグ候補抽出（torch 不要） |
| `tagger_bridge.py` | `TaggerBridge` | WD14/JoyCaption/Florence2 HTTP 連携 + 辞書フォールバック |
| `consistency_checker.py` | `ConsistencyChecker` | 複数プロンプト間の一貫性スコア・矛盾検出 |
| `negative_learner.py` | `NegativeLearner` | ネガティブ/低スコア履歴からの除外タグ学習 |

### ② REST API +8本（計84本）

```
POST /lora/analyze         LoRA ファイル分析（SafeTensors メタデータ解析）
GET  /lora/list            LoRA ファイル一覧スキャン
GET  /ai/status            AI タガーの利用可能状態確認
POST /ai/tag               AI タグ提案（モデル指定 or 辞書フォールバック）
POST /ai/negative-learn    履歴からネガティブタグを学習
GET  /ai/negative-suggest  ネガティブタグ推奨リスト
POST /consistency/check    スタイル一貫性チェック（2〜20プロンプト）
```

```bash
# 一貫性チェック例
POST /consistency/check
{
  "prompts": [
    "masterpiece, 1girl, blue_eyes, blonde_hair",
    "masterpiece, 1girl, green_eyes, blonde_hair"   # 目の色が矛盾！
  ]
}
# → {"overall_score": 62.0, "inconsistent_tags": ["blue_eyes","green_eyes"],
#    "recommendations": ["矛盾するタグを統一してください: blue_eyes、green_eyes"]}
```

### ③ ComfyUI 18ノード体制（+3種）

| ノード | 概要 |
|---|---|
| 🎭 Face Prompt LoRA Analyzer | SafeTensors 解析・トリガーワード抽出 |
| 🎭 Face Prompt AI Tagger | WD14/JoyCaption/Florence2 タグ提案 |
| 🎭 Face Prompt Consistency Checker | 複数プロンプト一貫性スコア |

**LoRA + Compiler ワークフロー例:**
```
[LoRA ファイルパス] → [🎭 Face Prompt LoRA Analyzer]
                           trigger_tags ↓
                      [🎭 Face Prompt Compiler]
                           prompt_out → [KSampler]
```

**一貫性チェックワークフロー:**
```
[複数プロンプト（1行1件）] → [🎭 Face Prompt Consistency Checker]
  overall_score → [閾値判定]  passed → [条件分岐]
  recommendations → [テキスト表示]
```

### ④ Web UI — AI タブ（11タブ目）

- **AI タガー状態** — WD14/JoyCaption/Florence2 の起動状況をリアルタイム確認
- **AIタグ提案** — 画像URLまたは現在タグから次のタグを提案（モデル選択可）
- **LoRAアナライザー** — ファイルパスを入力してトリガーワードをワンクリック挿入
- **スタイル一貫性チェック** — 複数プロンプトを入力してスコアと矛盾タグを表示
- **Negative推奨** — 学習データから neg に追加すべきタグを提案

---

## v2.4.0 新機能

### ① バッチ処理（最大50件）

```bash
# 複数プロンプトを一括コンパイル
POST /batch/compile
{"prompts": ["prompt1","prompt2",...], "apply_profile": true}
→ {"job_id":"xxx","total":5,"succeeded":5,"avg_score":82.1,"items":[...]}

# 一括最適化分析
POST /batch/optimize {"prompts": [...]}

# 最後のバッチ結果サマリー
GET /batch/status
```

### ② タグ補完 API

```bash
# プレフィックス補完（エディタ入力補完用）
GET /dictionary/autocomplete?q=anime&limit=15

# 現在タグからの次タグ提案
GET /dictionary/suggest?tags=masterpiece,soft_light&n=10
```

### ③ プロファイル エクスポート/インポート

```bash
GET  /profile/export         # JSON全データエクスポート
POST /profile/import         # JSON インポート（merge=true/false）
```

### ④ プリセットバージョン管理

```bash
GET    /presets/{id}/versions                  # バージョン一覧（最大20件）
POST   /presets/{id}/versions/{v}/restore      # 指定バージョンにリストア
DELETE /presets/{id}/versions/{v}              # バージョン削除
```

### ⑤ FacePromptBatchNode（ComfyUI / 15ノード目）

1行1プロンプトで複数入力 → 一括コンパイル → 最高スコアの pos/neg を出力

### ⑥ Web UI 強化（10タブ）

- **Batch タブ**: 複数プロンプトの一括処理・スコア比較・CSV エクスポート・結果をエディタに送信
- **Editor タブ**: タグ入力補完（2文字以上で候補ドロップダウン表示）
- **Profile タブ**: エクスポート/インポートボタン追加

---

## v2.3.0 新機能

### ① APIキー認証 + マルチユーザー（`fps-core/user/auth.py` 新設）

```bash
# 新規登録（APIキーを取得）
POST /users/register  {"username": "alice", "display_name": "Alice"}
→ {"user": {...}, "api_key": "fps_xxxxxxxx"}

# 認証が必要なリクエストはヘッダーに追加
X-Api-Key: fps_xxxxxxxx
```

| エンドポイント | 概要 |
|---|---|
| POST /users/register | 新規ユーザー登録 + APIキー発行 |
| GET /users/me | 自分のユーザー情報 |
| GET /users/{id} | 他ユーザー情報 |
| POST /users/me/api-keys | 追加 API キー発行 |
| DELETE /users/me/api-keys/{id} | API キー無効化 |

### ② プリセット共有（`fps-core/user/share.py` 新設）

```bash
# 共有リンク発行（30日間有効）
POST /presets/my_anime/share  {"title": "アニメ風プリセット", "expires_days": 30}
→ {"token": "xxx", "share_url": "/shared/presets/xxx"}

# 共有プリセットを取得（認証不要）
GET /shared/presets/xxx
→ {"preset_data": {"tags": [...], "negative_tags": [...]}}
```

| エンドポイント | 概要 |
|---|---|
| POST /presets/{id}/share | 共有リンク発行（認証任意） |
| GET /shared/presets/{token} | 共有プリセット取得（認証不要） |
| GET /shared/presets | 自分の共有一覧 |
| DELETE /shared/presets/{token} | 共有無効化 |

### ③ コミュニティタグ統計

```bash
# コミュニティ統計を取得
GET /community/tags?limit=50

# タグデータを匿名で投稿（任意）
POST /community/contribute  {"tags": ["masterpiece", "soft_light"], "avg_score": 82.5}
```

### ④ Web UI — Community・User タブ（+2タブ）

- **Community タブ**: 人気タグ棒グラフ / 匿名投稿ボタン / コントリビューション数
- **User タブ**: ユーザー登録・ログイン / APIキー管理 / 共有リンク一覧
- **Presets タブ**: 各プリセットに「🔗 共有」ボタン追加

---

## v2.2.0 新機能

### ① ComfyUI 統合強化（11 → 14ノード）

**新設 3ノード（v2.1対応）:**

| ノード | クラス | 概要 |
|---|---|---|
| 🎭 Face Prompt Profile | `FacePromptProfileNode` | 推奨タグ・除外タグを STRING で出力 |
| 🎭 Face Prompt Profile Apply | `FacePromptProfileApplyNode` | prompt/neg にプロファイルを適用 |
| 🎭 Face Prompt Profile Learn | `FacePromptProfileLearnNode` | 履歴から自動学習を実行 |

**既存ノード更新:**
- `FacePromptCompilerNode` — `apply_profile` / `negative_profile` BOOLEAN 入力追加、`profile_info` STRING 出力追加

**推奨 ComfyUI ワークフロー:**
```
[FacePromptProfileLearn] → (trigger) → [FacePromptProfile]
                                              ↓ recommended
[テキスト入力] → [FacePromptProfileApply] → [FacePromptCompiler] → KSampler
                         ↑ prompt/neg                   ↑ apply_profile=true
```

### ② UserProfile SQLite 移行

`fps-core/user/storage.py` 新設:
- `SQLiteProfileStorage` — WAL モード・スレッドセーフ
- テーブル: `tag_frequencies / tag_weights / style_rules / score_trends / meta`
- `upm.use_sqlite()` を呼ぶだけで既存 JSON データを自動移行
- `GET /profile/storage` で現在のストレージ状態を確認

### ③ 高度タグ検索（+1エンドポイント）

```
GET /dictionary/related/{tag}?n=20
```

- プロファイル学習データからの共起スコア算出
- フォールバック: 辞書カテゴリ一致

### ④ History 全文検索強化（+1エンドポイント）

```
GET /history/search?q=&tag=&date_from=&date_to=&score_min=&score_max=&favorite_only=
```

7項目の複合フィルタで最大1000件から絞り込み

### ⑤ プリセット v2 — プロファイルから自動生成（+1エンドポイント）

```
POST /profile/save-as-preset
  → 推奨タグ Top N + always_include をユーザープリセットとして保存
```

---

## v2.1.0 新機能

### ① `POST /compile` — Profile 直接統合

```bash
# プロファイルを適用してコンパイル（pos/neg に直接反映）
POST /compile?prompt=masterpiece,bad_quality,watermark&apply_profile=true&negative_profile=true
```

```json
{
  "success": true,
  "prompt":   "best_quality, masterpiece, soft_light",
  "negative": "bad_quality, low_res, watermark, blurry",
  "tag_count": 3,
  "profile_applied": true,
  "excluded_tags": ["bad_quality", "watermark"],
  "added_tags":    ["best_quality"],
  "auto_learned":  false
}
```

| パラメータ | 効果 |
|---|---|
| `apply_profile=true` | style_rules.always_include を pos に追加 / 除外設定タグを pos から除去 |
| `negative_profile=true` | style_rules.always_exclude を neg に自動追加 |

### ② 自動学習モード

- `PUT /profile/settings` で `auto_learn=true` に設定
- compile が `auto_learn_interval`（デフォルト10）件ごとに自動学習を実行
- 学習完了後 `profile.auto_learned` イベントを EventBus / WS に emit
- Web UI にバナー通知 + Profile タブのグラフが自動更新

### ③ `/profile/settings` エンドポイント（+2本）

```
GET /profile/settings  # 現在の設定取得
PUT /profile/settings  # 設定更新
```

設定項目:
- `auto_learn`: bool — 自動学習モード
- `auto_learn_interval`: int — 学習実行間隔（件数）
- `apply_profile_default`: bool — compile 時のデフォルト適用状態
- `recommendation_threshold`: int — 推奨タグの最低出現回数

### ④ Web UI 強化

- **Editor タブ**: `Profile を適用して compile` トグルスイッチ / `Neg にも反映` チェック
- **compile 結果パネル**: 追加されたタグ（🟢）/ 除外されたタグ（🔴）を色分け表示
- **Profile タブ**: タグ重みスライダー（0.0〜3.0）/ 🚫ボタンで即座に除外設定
- **自動学習バナー**: 学習実行時に画面上部に通知

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
for r in recs:
    print(f"{r.tag}: {r.count}回 (重み{r.avg_weight:.2f})")

# プロファイルをタグリストに適用（除外・強調を自動反映）
result_tags = upm.apply_profile(["masterpiece", "bad_quality", "soft_light"])

# スタイルルール追加（常に除外/追加するタグ）
from user.models import StyleRule
upm.add_style_rule(StyleRule(
    id="my_quality",
    name="品質重視",
    always_include=["masterpiece", "best_quality"],
    always_exclude=["bad_quality", "low_res"],
))

# タグ重み設定（0.0 = 除外, 1.0 = 標準, 3.0 = 最大強調）
upm.set_tag_weight("watermark", weight=0.0)   # 常に除外
upm.set_tag_weight("soft_light", weight=2.0)  # 強調

# スコアトレンド（日別集計）
trends = upm.build_score_trends(history_entries, days=30)
```

### ② REST API — Profile エンドポイント（+9本）

| Method | Path | 内容 |
|---|---|---|
| GET | `/profile` | プロファイル概要・頻出タグ・スタイルルール |
| POST | `/profile/learn` | 履歴から学習 + スコアトレンド更新 |
| GET | `/profile/recommendations` | 推奨タグリスト |
| GET | `/profile/score-trend` | スコア傾向（日別グラフデータ） |
| PUT | `/profile/tags/{tag}/weight` | タグ重み設定 |
| DELETE | `/profile/tags/{tag}/weight` | タグ重み削除 |
| POST | `/profile/rules` | スタイルルール追加 |
| DELETE | `/profile/rules/{id}` | スタイルルール削除 |
| DELETE | `/profile/reset` | プロファイル完全リセット |
| GET | `/profile/settings` | 設定取得 ★v2.1 |
| PUT | `/profile/settings` | 設定更新 ★v2.1 |

### ③ Web UI — Profile タブ（新設）

- **推奨タグ Top20** — 頻度・重みスコアリングで選出。クリックでエディタに挿入
- **スコアトレンドグラフ** — 日別平均スコアの折れ線グラフ（14/30/60/90日選択）
- **スタイルルール管理** — 常時 include/exclude ルールの追加・削除
- **タグ重み一覧** — 手動設定された重み・除外タグの確認
- **「履歴から学習」ボタン** — ワンクリックで全履歴を学習

---

## v1.9.0 新機能（WebSocket リアルタイム更新）

### WebSocket 3チャンネル

| チャンネル | URL | 配信内容 |
|---|---|---|
| pipeline | `WS /ws/pipeline` | ステージ進捗・完了・エラー・キャッシュヒット |
| history | `WS /ws/history` | 新規履歴エントリのリアルタイムプッシュ |
| events | `WS /ws/events` | 全 EventBus イベント（type フィルタ可） |

```javascript
const ws = new WebSocket("ws://localhost:8420/ws/pipeline");
ws.onmessage = (e) => {
  const { type, data } = JSON.parse(e.data);
  if (type === "stage.after_run") console.log("✓", data.stage);
  if (type === "pipeline.after_compile") console.log("完了");
};
```

Web UI に自動統合済み：接続インジケーター・進捗バー・ステージトースト・History 自動更新

---


---

## ComfyUI へのインストール

```bash
# ComfyUI の custom_nodes ディレクトリにクローン
cd ComfyUI/custom_nodes
git clone https://github.com/glasssoundforest-lab/Face-Prompt-Studio.git FacePromptStudio

# REST API を使う場合のみ（ノードだけなら不要）
pip install fastapi uvicorn pydantic
```

ComfyUI を再起動すると **FacePromptStudio** カテゴリにノードが表示されます。

詳細は [INSTALL_COMFYUI.md](INSTALL_COMFYUI.md) を参照してください。

## クイックスタート（REST API サーバー）

```bash
# インストール
pip install -e fps-core
pip install -e "fps-adapters[rest]"

# REST API サーバー起動（WebSocket 対応）
uvicorn fps-adapters.rest.app:app --reload --port 8420

# Web UI（7タブ）
open http://localhost:8420/
```

## テスト実行

```bash
cd fps
python -m pytest fps-tools/tests/unit/ --no-cov -q
# → 1250 passed
```

---

## REST API 全エンドポイント（48本）

### コア

| Method | Path | 概要 |
|---|---|---|
| GET | `/health` | ヘルスチェック（v2.0.0） |
| POST | `/compile` | コンパイル（★v2.1 apply_profile/negative_profile 対応）|
| POST | `/optimize` | 最適化分析 + optimizer.analyzed emit |
| POST | `/validate` | 辞書/ルール/プリセット検証 |
| GET | `/dashboard` | 全統計ダッシュボード |

### 辞書（9本）

| Method | Path | 概要 |
|---|---|---|
| GET | `/dictionary/search` | タグ検索 |
| GET | `/dictionary/stats` | 辞書統計 |
| GET | `/dictionary/categories` | カテゴリ一覧 |
| GET | `/dictionary/entries` | エントリ検索 |
| GET | `/dictionary/synonyms` | 同義語取得 |
| GET | `/dictionary/user/entries` | ユーザー辞書一覧 |
| POST | `/dictionary/user/entries` | エントリ追加 |
| PUT | `/dictionary/user/entries/{key}` | 部分更新 |
| DELETE | `/dictionary/user/entries/{key}` | 削除 |

### プリセット（5本）

| Method | Path | 概要 |
|---|---|---|
| GET | `/presets` | 一覧（source フィールド付き） |
| POST | `/presets` | 新規作成（201） |
| POST | `/presets/{id}/apply` | 適用 |
| PUT | `/presets/{id}` | 部分更新 |
| DELETE | `/presets/{id}` | 削除 |
| POST | `/presets/{id}/tags/add` | タグ追記 |

### 履歴（8本）

| Method | Path | 概要 |
|---|---|---|
| GET | `/history` | 一覧 |
| GET | `/history/stats` | 統計（頻出タグ・スコア分布） |
| GET | `/history/export` | CSV/JSONエクスポート |
| GET | `/history/{id}` | 詳細 |
| POST | `/history/{id}/favorite` | お気に入りトグル |
| PUT | `/history/{id}/label` | ラベル設定 |
| GET | `/history/{id1}/diff/{id2}` | 差分比較 |
| DELETE | `/history/{id}` | 削除 |

### バックアップ（4本）

| Method | Path | 概要 |
|---|---|---|
| POST | `/backup` | バックアップ作成 |
| GET | `/backup` | 一覧 |
| DELETE | `/backup/{id}` | 削除 |
| POST | `/backup/{id}/restore` | リストア |

### テンプレート（3本）

| Method | Path | 概要 |
|---|---|---|
| GET | `/templates` | 一覧 |
| POST | `/templates/{id}/render` | テンプレート展開 |
| POST | `/templates/render` | 直接展開 |

### プロファイル（9本 ★v2.0）

| Method | Path | 概要 |
|---|---|---|
| GET | `/profile` | プロファイル概要 |
| POST | `/profile/learn` | 履歴から学習 |
| GET | `/profile/recommendations` | 推奨タグ |
| GET | `/profile/score-trend` | スコアトレンド |
| PUT | `/profile/tags/{tag}/weight` | タグ重み設定 |
| DELETE | `/profile/tags/{tag}/weight` | タグ重み削除 |
| POST | `/profile/rules` | スタイルルール追加 |
| DELETE | `/profile/rules/{id}` | スタイルルール削除 |
| DELETE | `/profile/reset` | プロファイルリセット |

### WebSocket（3本 + 1本 ★v1.9）

| Method | Path | 概要 |
|---|---|---|
| WS | `/ws/pipeline` | コンパイル進捗ストリーム |
| WS | `/ws/history` | 新規履歴プッシュ |
| WS | `/ws/events` | 全イベントサブスクライブ |
| GET | `/ws/stats` | WS 接続数確認 |

---

## リポジトリ構造

```
fps/
├── fps-core/                    Pure Python core（アダプター依存ゼロ）
│   ├── cache/                   LRUCache + TTL（v1.1）
│   ├── backup/                  BackupManager（v1.1）
│   ├── config/                  ConfigManager
│   ├── dictionary/              DictionaryManager（CRUD, 日本語1002件）
│   ├── events/                  EventBus（14種 EventType + v1.9/v2.0 追加）
│   ├── history/                 HistoryManager（CRUD + diff）
│   ├── optimizer/               OptimizerManager + combination_checker（v1.5）
│   ├── pipeline/                PipelineManager（10ステージ + EventBus統合）
│   ├── preset/                  PresetManager（CRUD, v1.7）
│   ├── rules/                   RuleManager
│   ├── template/                TemplateManager
│   └── user/                    ★v2.0 UserProfileManager（学習/推奨/スタイルルール）
│
├── fps-adapters/
│   ├── cli/
│   │   └── context.py           CliContext（全 Manager + event_bus + user_profile）
│   ├── comfyui/nodes/           ComfyUI ノード（11種）
│   └── rest/
│       ├── app.py               FastAPI（48エンドポイント）
│       ├── models.py            Pydantic スキーマ（全バージョン累積）
│       └── ws.py                ★v1.9 WebSocket ブリッジ
│
├── fps-gui/web/
│   └── index.html               SPA（7タブ: Editor/Optimize/Presets/History/Backup/Profile/Dashboard）
│
├── fps-data/
│   ├── dictionaries/system/synonyms/japanese_tags.json  （1002件/41カテゴリ）
│   ├── presets/system/          組み込みプリセット
│   ├── presets/user/            ユーザープリセット
│   ├── rules/
│   └── user/profile.json        ★v2.0 ユーザープロファイル
│
└── fps-tools/tests/unit/        1250件 PASS
```

---

## ComfyUI ノード（11種）

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

## ライセンス

MIT License
