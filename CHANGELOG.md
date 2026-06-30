# Changelog

All notable changes to Face Prompt Studio are documented here.
Format: [Semantic Versioning](https://semver.org/)

---

## [Unreleased]

### Planned (Milestone 2 以降)
- 追加入力モデル対応（Florence2 / Qwen2-VL / InternVL / MiniCPM-V）
- Category Weight Engine GUI 強化
- Prompt Optimizer（品質スコアリング・矛盾検出）
- A1111 / NovelAI アダプター
- Plugin System / Event System
- GUI Studio（Web UI）

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

[Unreleased]: https://github.com/glasssoundforest-lab/Face-Prompt-Studio/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/glasssoundforest-lab/Face-Prompt-Studio/releases/tag/v0.5.0
