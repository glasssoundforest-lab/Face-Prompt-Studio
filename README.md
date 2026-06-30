# Face Prompt Studio

Prompt Compiler Framework for Stable Diffusion / ComfyUI — 顔プロンプト
（face prompt）の最適化・クリーニング・ルールベース処理に特化した
プロフェッショナル品質のフレームワーク。

ComfyUI はアダプターの一つに過ぎない、ロングタームで拡張可能な
アーキテクチャを採用しています。

## ステータス

**v0.6.0** — Phase 2 Face Prompt Cleaner 強化完了

- 438 unit tests / 203 compat tests — 全て PASS（合計641件）
- Coverage 90%（閾値 85%）
- Ruff / Black / mypy 全クリア

## 特徴

- **顔特化辞書システム** — 24カテゴリ・1169キー（eyes / hair / expression /
  makeup / fantasy_parts / age / ethnicity など）
- **同義語対応** — WD14 / JoyCaption / Florence2 / Qwen2-VL / InternVL /
  MiniCPM-V 主要キャプションモデルの出力タグを自動正規化
- **10ステージパイプライン** — Parser → Normalizer → Blacklist →
  Categorizer → RuleEngine → Optimizer → Exporter
- **JSON駆動ルールエンジン** — Python修正不要でタグの追加/削除/重み変更
- **ComfyUI ノード6種** — Cleaner / Compiler / Debug / Preset / RuleEditor / CategoryFilter
- **Clean Architecture** — core はアダプター依存ゼロ、拡張容易

## リポジトリ構造

```
fps/
├── fps-core/          Pure Python core（アダプター依存ゼロ）
│   ├── config/        ConfigManager
│   ├── fps_logging/   FPSLogger
│   ├── dictionary/    DictionaryManager
│   ├── rules/         RuleManager
│   ├── preset/        PresetManager
│   ├── cache/         CacheManager
│   ├── backup/        BackupManager
│   └── pipeline/      PipelineManager（10ステージ）
├── fps-adapters/      アダプター（core から独立）
│   └── comfyui/       ComfyUI Adapter + カスタムノード6種
├── fps-data/          辞書・ルール・プリセットデータ
│   └── dictionaries/system/
│       ├── (17 顔特化カテゴリ).json
│       └── synonyms/  WD14 / JoyCaption / 表記揺れ対応
└── fps-tools/
    └── tests/
        ├── unit/         390 tests
        ├── compat/       146 tests
        └── performance/  27 tests
```

## クイックスタート

### インストール

```bash
git clone https://github.com/glasssoundforest-lab/Face-Prompt-Studio.git fps
cd fps
pip install pytest pytest-cov pyyaml ruff black mypy --break-system-packages
```

### 動作確認

```bash
python main.py              # smoke + unit テスト
python main.py --compat     # + 互換性テスト
python main.py --perf       # + 性能テスト（測定結果表示）
python main.py --all        # 全テスト + lint + format + typecheck
```

### Python から使う

```python
import sys
sys.path.insert(0, "fps-core")
sys.path.insert(0, "fps-adapters")

from dictionary.manager import DictionaryManager
from pipeline.manager import PipelineManager
from comfyui.adapter import ComfyUIAdapter

dm = DictionaryManager(
    system_dir="fps-data/dictionaries/system",
    user_dir="fps-data/dictionaries/user",
)
dm.load()

pm = PipelineManager()
pm.set_context(dictionary_manager=dm)

result = pm.compile("(quality:high:1.5), blue_eyes, elf_ears, [bad hands]")
print(result.prompt)     # "Quality.High, Eyes.Blue, Fantasy.ElfEars"
print(result.negative)   # "bad_hands"

adapter = ComfyUIAdapter(api_version="v1")
output = adapter.convert(result)
```

### ComfyUI への導入

```
ComfyUI/custom_nodes/Face-Prompt-Studio/   ← このリポジトリを clone
```

起動すると `FacePromptStudio` カテゴリに以下のノードが追加されます。

- **Face Prompt Cleaner** — プロンプトクリーニング、17カテゴリスイッチ
- **Face Prompt Compiler** — DSLフルコンパイル、プリセット適用
- **Face Prompt Debug** — 変換差分・辞書統計表示
- **Face Prompt Preset** — プリセット選択・複数マージ
- **Face Prompt Rule Editor** — ルール確認・テスト・一時無効化
- **Face Prompt Category Filter** — カテゴリベースのタグ抽出/除外

## DSL 構文

```
(category:value)          カテゴリ指定         例: (quality:high)
(category:value:weight)   重み付きカテゴリ     例: (eyes:blue:1.5)
[tag]                      ネガティブプロンプト 例: [bad hands]
{category:value}          制約                 例: {style:anime}
word                       プレーンタグ（辞書解決） 例: masterpiece
```

## 設計方針

- **Clean Architecture** — `fps-core` は `fps-adapters` に一切依存しない
- **SOLID** / Adapter pattern / Plugin system
- **JSON/YAML configurable**（JSON優先）/ Hot reload
- **user 辞書は絶対にシステム更新で上書きされない**

## 開発フェーズ

| Phase | 内容 | 状態 |
|---|---|---|
| 1 | Foundation | ✅ 完了（v0.5.0） |
| 2 | Face Prompt Cleaner 強化 | ✅ 完了（v0.6.0） |
| 3 | Prompt Optimizer | 計画中 |
| 4 | AI Adapter Layer | 計画中 |
| 5 | GUI Studio | 計画中 |

## コーディング規約

Python 3.11+ / Type hints / PEP8 / Black / Ruff / mypy（strict）/
pytest / `slots=True` dataclass / Docstrings

## ライセンス

TBD

## コントリビューション

`feature/**` ブランチで開発し、`develop` へ PR を送ってください。
PR テンプレートのチェックリストに従い、`python main.py --all` が
全て PASS することを確認してください。
