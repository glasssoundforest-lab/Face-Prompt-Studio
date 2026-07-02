# Face Prompt Studio — ComfyUI インストールガイド

## 動作要件

- ComfyUI（最新版推奨）
- Python 3.11 以上
- **fps-core の外部依存ゼロ**（標準ライブラリのみで動作）

---

## インストール手順

### ① リポジトリをクローン

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/glasssoundforest-lab/Face-Prompt-Studio.git FacePromptStudio
```

> **重要**: フォルダ名は `FacePromptStudio`（スペースなし）にしてください。
> ComfyUI が `custom_nodes/FacePromptStudio/__init__.py` をエントリポイントとして読み込みます。

### ② 依存ライブラリのインストール（任意）

ComfyUI ノードだけを使う場合は追加ライブラリ不要です。
REST API サーバーを使う場合のみ以下を実行:

```bash
# ComfyUI の Python 環境を使って実行
/path/to/ComfyUI/python_embeded/python.exe -m pip install fastapi uvicorn pydantic

# 通常の Python 環境の場合
pip install -r ComfyUI/custom_nodes/FacePromptStudio/requirements.txt
```

### ③ データディレクトリの確認

```
ComfyUI/custom_nodes/FacePromptStudio/
├── __init__.py              ← ComfyUI エントリポイント
├── fps-core/                ← コアライブラリ（依存ゼロ）
├── fps-adapters/comfyui/    ← ComfyUI ノード実装
├── fps-data/                ← 辞書・プリセット・ルール
│   ├── dictionaries/        ← 日本語1002件を含む辞書
│   ├── presets/             ← プリセット（system/user）
│   └── rules/               ← ルール定義
└── requirements.txt
```

### ④ ComfyUI を起動

ComfyUI を再起動すると `FacePromptStudio` ノードが自動的に読み込まれます。

---

## 利用可能なノード（15種）

ノードメニューの **FacePromptStudio** カテゴリから追加できます。

| ノード名 | 用途 |
|---|---|
| 🎭 Face Prompt Compiler | プロンプトをコンパイルして pos/neg を出力（メインノード） |
| 🎭 Face Prompt Cleaner | タグの正規化・重複除去 |
| 🎭 Face Prompt Optimizer | 品質スコア分析・問題検出 |
| 🎭 Face Prompt Preset | プリセット適用 |
| 🎭 Face Prompt Rule Editor | ルールの動的編集・適用 |
| 🎭 Face Prompt Category Filter | カテゴリフィルタリング |
| 🎭 Face Prompt History | 変換履歴の記録・参照 |
| 🎭 Face Prompt Backup | データバックアップ・リストア |
| 🎭 Face Prompt Group Control | グループ重み一括制御 |
| 🎭 Face Prompt Template | テンプレート展開 |
| 🎭 Face Prompt Debug | デバッグ出力 |
| 🎭 Face Prompt Profile | 推奨タグ取得（v2.1） |
| 🎭 Face Prompt Profile Apply | プロファイルをプロンプトに適用（v2.1） |
| 🎭 Face Prompt Profile Learn | 履歴から自動学習（v2.1） |
| 🎭 Face Prompt Batch | 複数プロンプトを一括処理（v2.4） |

---

## 推奨ワークフロー

### シンプル構成（Compiler のみ）

```
[テキスト入力]
    prompt: "masterpiece, soft_light, blue_eyes"
         ↓
[🎭 Face Prompt Compiler]
    apply_profile: false
    max_weight: 2.0
         ↓
    prompt_out → [KSampler] positive
    negative_out → [KSampler] negative
```

### プロファイル統合構成（v2.1+）

```
[🎭 Face Prompt Profile Learn]   ← 初回のみ実行（履歴から学習）
         ↓ trigger
[🎭 Face Prompt Profile]         ← 推奨タグ取得
    recommended → 参考表示
         ↓
[テキスト入力]
         ↓
[🎭 Face Prompt Profile Apply]   ← プロファイル適用（除外・追加）
    prompt_out ↓   negative_out ↓
[🎭 Face Prompt Compiler]
    apply_profile: true          ← 二重適用でさらに精度向上
         ↓
    prompt_out → [KSampler] positive
    negative_out → [KSampler] negative
```

### バッチ処理構成（v2.4+）

```
[テキスト入力]                      ← 1行1プロンプト（最大50件）
    "masterpiece, blue_eyes
     anime_style, colorful
     portrait, natural_light"
         ↓
[🎭 Face Prompt Batch]
    apply_profile: true
    max_items: 10
         ↓
    best_prompt   → [KSampler] positive  ← 最高スコアの結果
    best_negative → [KSampler] negative
    summary       → [テキスト表示]       ← 処理結果サマリー
```

---

## トラブルシューティング

### ノードが表示されない

1. `ComfyUI/custom_nodes/FacePromptStudio/__init__.py` が存在するか確認
2. ComfyUI のコンソールログで `FacePromptStudio` のエラーを確認
3. Python バージョンが 3.11 以上か確認: `python --version`

### `fps-core` が見つからないエラー

```
ModuleNotFoundError: No module named 'dictionary'
```

`fps-core/` ディレクトリが存在するか確認:
```
ComfyUI/custom_nodes/FacePromptStudio/fps-core/
├── dictionary/
├── pipeline/
├── preset/
└── ...
```

存在しない場合は `git clone` をやり直してください（`--recursive` は不要）。

### 辞書・プリセットが動かない

`fps-data/` ディレクトリが存在するか確認:
```bash
ls ComfyUI/custom_nodes/FacePromptStudio/fps-data/dictionaries/system/
```

### REST API サーバーを同時に使いたい

```bash
cd ComfyUI/custom_nodes/FacePromptStudio
uvicorn fps-adapters.rest.app:app --port 8420 --reload
```

Web UI: http://localhost:8420/

---

## アップデート方法

```bash
cd ComfyUI/custom_nodes/FacePromptStudio
git pull origin main
```

ComfyUI を再起動すれば新しいノードが反映されます。
