# Changelog

All notable changes to Face Prompt Studio are documented here.
Format: [Semantic Versioning](https://semver.org/)

---

## [Unreleased]

### Planned (Milestone 4 以降)
- A1111 / NovelAI アダプター
- Plugin System / Event System
- GUI Studio（Web UI）

---

## [0.7.0] — 2026-06-30

Phase 3 Prompt Optimizer 完了。プロンプトの品質を定量評価し、
矛盾・冗長性を自動検出、改善提案を行う最適化エンジンを実装。
変換履歴の記録・比較機能も追加。

### Added — Semantic Optimizer

- **fps-core/optimizer/** パッケージ新設
  - `conflict_detector.py` — 9つの排他グループ定義（eyes_color /
    hair_color / hair_length / skin_tone / face_shape / mouth_state /
    quality_level / makeup_intensity 等）に基づく矛盾検出
    （例: `blue_eyes` + `brown_eyes` の同時指定を検出）
  - `redundancy_detector.py` — 意味的重複グループ検出（smile_family /
    lips_full / hair_tied 等）、完全重複タグの保険的検出
  - `quality_scorer.py` — coverage_score（重要カテゴリ網羅度）/
    balance_score（重み分散）/ redundancy_score（矛盾冗長性）の
    加重平均による overall_score 算出
  - `recommender.py` — 検出結果から自然言語の改善提案を生成、
    不足カテゴリへのタグ候補提案（辞書連携対応）
  - `manager.py` — `OptimizerManager`: `analyze()` /
    `analyze_pipeline_result()` / `suggest_tags()`

### Added — Prompt History & Comparison

- **fps-core/history/** パッケージ新設
  - `history_manager.py` — `HistoryManager`: JSON Lines形式での
    永続化、記録/検索/お気に入り/ラベル管理、`max_entries` 超過時の
    自動削除（お気に入りは保護）
  - `diff_viewer.py` — プロンプト文字列・履歴エントリ間の差分計算、
    人間可読なテキストレポート整形

### Added — ComfyUI Nodes（2種追加、合計8ノード）

- **🎭 Face Prompt Optimizer** — 品質スコア・矛盾・冗長性・改善提案を
  レポート出力。`overall_score` / `has_conflicts` も個別出力として提供
- **🎭 Face Prompt History** — プロンプト変換結果の記録、直近10件の
  履歴一覧・統計表示、直近2件の自動差分比較

### Fixed

- **重大バグ（3件目）**: `RuleEngineStage` が `TagEntry` 再構築時に
  `meta`（`resolved` 情報を含む）を引き継いでおらず、`rule_manager` が
  `context` に存在する限り（= ComfyUI ノード経由では常に）辞書解決
  情報が失われていた。Optimizer の矛盾検出が機能しないことから発覚し、
  既存タグの `meta` を `meta_by_tag` マップで復元するよう修正
  （ルールで新規追加されたタグは meta 空のままが正しい挙動）。
  回帰テストを追加。

### Testing

- ユニットテスト 553件（前回497件から56件増、optimizer 40件・
  history 44件・対応ノードテスト27件含む）
- 互換性テスト 225件
- 合計 778 tests PASSED / Coverage 91%（閾値85%維持）

---

## [0.6.0] — 2026-06-30

Phase 2 Face Prompt Cleaner 強化完了。対応キャプションモデルを拡大し、
辞書・デバッグ機能・ComfyUI ノードを大幅に強化。

### Added — Dictionary Expansion

- **追加入力モデル同義語辞書**（4種、121エントリ）
  - `florence2_tags.json`（33）— Florence2 詳細キャプション対応
  - `qwen2vl_tags.json`（21）— Qwen2-VL 構造化記述（key:value形式）対応
  - `internvl_tags.json`（19）— InternVL 詳細記述対応
  - `minicpm_tags.json`（18）— MiniCPM-V 簡潔記述対応

- **補助カテゴリ辞書**（4種、44エントリ）
  - `age.json` — 年齢表現（child〜elderly、外見的特徴）
  - `ethnicity.json` — 地域特有の顔特徴（中立的記述語彙）
  - `body.json` — 顔写りに関連する首・肩周りの体格
  - `clothing.json` — 顔周り・首元の服装（襟・ネックライン・帽子等）

辞書総計: **1169キー / 30ファイル / 24カテゴリ**
（v0.5.0 の784キー/22ファイルから49%拡大）

### Added — Debug Output Enhancement

- **PipelineResult.meta['applied_rules']** — 発火した全ルールの追跡情報を
  パイプライン結果に記録
- **Face Prompt Cleaner デバッグ出力強化**
  - Tag Diff（parsed → final）: ルール由来の追加とカテゴリスイッチ由来の
    除外を明確に区別して表示
  - Category Summary: カテゴリ別タグ数・平均重みの集計表
  - Applied Rules: 発火した全ルールの ID・アクション・対象タグ・詳細一覧

### Added — ComfyUI Nodes（3種追加、合計6ノード）

- **🎭 Face Prompt Preset** — プリセット選択式ドロップダウン、複数プリセット
  マージ、追加プロンプト合成に対応
- **🎭 Face Prompt Rule Editor** — ロード済みルールの一覧・統計表示、
  ルールの一時無効化テスト（副作用なし設計）、テストプロンプトでの
  適用結果確認
- **🎭 Face Prompt Category Filter** — keep_only/exclude モードでの
  カテゴリベースタグ抽出、カテゴリ内訳レポート

### Testing

- ユニットテスト 438件（前回390件から48件増）
- 互換性テスト 203件（モデル別タグ網羅24件追加、ComfyUI 6ノード自動カバー）
- 合計 641 tests PASSED / Coverage 90%（閾値85%維持）

---

## [0.5.0] — 2026-06-30

Phase 1 Foundation 完了。全コアコンポーネント・ComfyUI ノード・
顔特化辞書システムを実装し、本番投入可能な品質に到達。

### Added — Core Components

- **ConfigManager** (`fps-core/config/`)
  JSON/YAML 設定読み込み、ドット記法アクセス、環境変数オーバーライド
  （`FPS_SECTION__KEY`）、hot reload。

- **FPSLogger** (`fps-core/fps_logging/`)
  構造化ログ（JSON Lines）、ANSI カラーコンソール出力、
  RotatingFileHandler、ConfigManager 連携。

- **DictionaryManager** (`fps-core/dictionary/`)
  JSON/YAML 辞書のロード・バリデーション・マージ・ホットリロード。
  system/user 優先順位（user が常に system を上書き）。
  サブディレクトリ再帰読み込み対応（`rglob`）。

- **RuleManager** (`fps-core/rules/`)
  JSON駆動ルールエンジン。アクション: `ADD` / `REMOVE` / `WEIGHT` /
  `REPLACE` / `KEEP_CATEGORY`。条件: `TAG` / `CATEGORY` / `WEIGHT_LT` /
  `WEIGHT_GT` / `ALIAS`（AND結合）。優先度順適用。

- **PresetManager** (`fps-core/preset/`)
  プリセットの保存・検索・マージ・適用。system/user 分離。

- **CacheManager** (`fps-core/cache/`)
  スレッドセーフ LRU キャッシュ、TTL対応、名前空間分離、
  SHA-256ベースキー生成。

- **BackupManager** (`fps-core/backup/`)
  設定/辞書/ルール/プリセットの自動バックアップとリストア、
  世代管理（max_count超過分を自動削除）。

- **PipelineManager** (`fps-core/pipeline/`)
  10ステージプロンプトコンパイルパイプライン:
  Parser → Normalizer → DuplicateCleaner → Blacklist → Whitelist →
  Categorizer → RuleEngine → WeightEngine → Optimizer → Exporter。
  ステージ単位の有効/無効切替対応。

- **CategoryWeightTable** (`fps-core/pipeline/category_weights.py`)
  カテゴリ別デフォルト重み倍率テーブル。4プリセット
  （balanced / quality_focused / expression_focused / fantasy_focused）。

### Added — ComfyUI Integration

- **ComfyUI Adapter** (`fps-adapters/comfyui/adapter.py`)
  v1（フラットJSON）/ v2（ノードグラフ・CLIPTextEncode）出力対応。

- **ComfyUI カスタムノード** (`fps-adapters/comfyui/nodes/`)
  - `Face Prompt Cleaner` — 17カテゴリスイッチ、6カテゴリ重みスケール、
    重みプリセット選択、追加ブラックリスト、デバッグ出力。
  - `Face Prompt Compiler` — DSLフルコンパイル、プリセット適用、
    API v1/v2出力。
  - `Face Prompt Debug` — 変換差分表示、辞書/ルール統計表示。

### Added — DSL

DSL構文サポート: `(category:value)`、`(category:value:weight)`、
`[negative]`、`{constraint:value}`、`(plain)`（コロンなしフォールバック）。

### Added — Dictionary Data

顔特化17カテゴリ辞書（784キー / 22ファイル）:
`quality` / `eyes` / `eyebrows` / `eyelashes` / `face_shape` / `nose` /
`mouth` / `teeth` / `skin` / `expression` / `accessories` / `glasses` /
`piercing` / `makeup` / `fantasy_parts` / `hair` / `style`。

除外カテゴリ辞書: `blacklist_default`（19エントリ）、
`whitelist_face`（17エントリ）。

同義語辞書 (`dictionaries/system/synonyms/`):
- `wd14_tags.json`（51エントリ）— WD14タガー出力対応
- `joycaption_tags.json`（49エントリ）— JoyCaption/Florence2自然言語対応
- `common_variants.json`（29エントリ）— 表記揺れ・略称対応

サンプルデータ: ルール4件、プリセット3種
（anime_portrait / realistic_portrait / fantasy_character）。

### Added — Testing & CI

- ユニットテスト 390件（全コンポーネント）
- 互換性テスト 146件（E2Eシナリオ、辞書整合性、ComfyUIインターフェース準拠）
- 性能テスト 27件（パイプライン速度、辞書ルックアップ速度、キャッシュ効率）
- GitHub Actions CI（Python 3.11/3.12マトリクス、lint/typecheck/test）
- `main.py` デバッグランナー（`--smoke` / `--unit` / `--compat` / `--perf` /
  `--cov` / `--check` / `--all`）

### Added — Dev Tooling

- `pyproject.toml`（pytest/ruff/black/mypy統合設定）
- `Makefile`（`make test` 等ショートカット）
- PRテンプレート、Issueテンプレート（バグ報告/機能要望）

### Fixed

- **辞書バリデーション**: 複数辞書ファイルでキー/エイリアスの正規化後重複を解消
  （`hair.json` / `quality.json` / `skin.json` / `whitelist_face.json` 等）。
- **辞書の意味衝突**: `red_lips`（`mouth.json`: 唇の色 vs `wd14_tags.json`:
  口紅メイク）を `red_lipstick_wd14` にリネームして解消。
- **重大バグ**: ComfyUI ノードの `node_base.py` で `_ROOT` パス計算が
  1階層ズレており（`parents[4]` → 正しくは `parents[3]`）、
  DictionaryManager/RuleManager がノード経由では常に未初期化（None）
  フォールバックしていた。compat tests 整備時に発見・修正。
- **テストインフラ**: pytest 9.x で `--pythonpath` CLI引数が非対応に
  なっていた問題を発見。`pyproject.toml` の `[tool.pytest.ini_options]`
  設定に統一して解消。
- メソッド名 `list()` / Python組み込み型との衝突を `list_presets()` /
  `list_backups()` にリネームして解消。
- `fps-core/logging/` → `fps_logging/`（Python標準ライブラリ衝突回避）。
- `fps-core/__init__.py` / `fps-adapters/__init__.py` 削除
  （ハイフン入りディレクトリ名による mypy エラー回避）。

### Changed

- Coverage 閾値を 80% → 85% に引き上げ（実測 90% 達成）。
- `DictionaryManager` の辞書ロードをサブディレクトリ再帰対応に変更
  （`glob` → `rglob`）。

---

## [0.1.0-dev] — 2026-06-27

初期構想スナップショット。ComfyUI-FacePromptStudio としての
プロジェクトビジョン、アーキテクチャ設計、Phase 1〜5 ロードマップを策定。

---

[Unreleased]: https://github.com/glasssoundforest-lab/Face-Prompt-Studio/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/glasssoundforest-lab/Face-Prompt-Studio/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/glasssoundforest-lab/Face-Prompt-Studio/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/glasssoundforest-lab/Face-Prompt-Studio/releases/tag/v0.5.0
