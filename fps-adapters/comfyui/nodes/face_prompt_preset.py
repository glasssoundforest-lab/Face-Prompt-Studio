"""
fps-adapters/comfyui/nodes/face_prompt_preset.py
ノード: 🎭 Face Prompt Preset

機能:
  - プリセットを選択して即座にプロンプト化する専用ノード
  - 複数プリセットのマージにも対応
  - プリセット一覧の取得（INPUT_TYPES で動的選択肢として表示）

入力:
  preset_id       STRING(選択式)  適用するプリセット
  merge_with      STRING          追加でマージするプリセットID（カンマ区切り、任意）
  extra_prompt    STRING          プリセットに追加するプロンプト文字列（任意）

出力:
  prompt          STRING  プリセット由来のプロンプト
  negative        STRING  プリセット由来のネガティブプロンプト
  preset_name     STRING  適用したプリセットの表示名
  tag_count       INT     タグ数
"""

from __future__ import annotations

from typing import Any

from .node_base import _ROOT, FPSNodeBase


def _get_preset_manager():
    """PresetManager を取得する（遅延 import、キャッシュなし — プリセットは
    ユーザーが頻繁に編集する可能性があるため毎回ロードする）"""
    from preset.manager import PresetManager

    data_root = _ROOT / "fps-data" / "presets"
    pm = PresetManager(
        system_dir=data_root / "system",
        user_dir=data_root / "user",
    )
    pm.load()
    return pm


def _list_preset_ids() -> list[str]:
    """ComfyUI のドロップダウン選択肢用にプリセットID一覧を返す"""
    try:
        pm = _get_preset_manager()
        ids = pm.list_ids()
        return ids if ids else ["(no presets found)"]
    except Exception:
        return ["(error loading presets)"]


class FacePromptPresetNode(FPSNodeBase):
    """Face Prompt Preset ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("prompt", "negative", "preset_name", "tag_count")
    FUNCTION = "apply_preset"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        preset_ids = _list_preset_ids()
        return {
            "required": {
                "preset_id": (preset_ids, {"default": preset_ids[0]}),
            },
            "optional": {
                "merge_with": (
                    "STRING",
                    {
                        "default": "",
                        "placeholder": "追加マージするプリセットID（カンマ区切り）",
                    },
                ),
                "extra_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "プリセットに追加するプロンプト",
                    },
                ),
            },
        }

    def apply_preset(
        self,
        preset_id: str,
        merge_with: str = "",
        extra_prompt: str = "",
    ) -> tuple[str, str, str, int]:
        """
        プリセットを適用してプロンプト文字列を生成する。

        Returns:
            (prompt, negative, preset_name, tag_count)
        """
        try:
            pm = _get_preset_manager()
        except Exception as e:
            return "", "", f"[ERROR] {e}", 0

        if not pm.exists(preset_id):
            return "", "", f"[ERROR] preset '{preset_id}' not found", 0

        # マージ対象IDリストを構築
        merge_ids = [preset_id]
        if merge_with.strip():
            merge_ids += [m.strip() for m in merge_with.split(",") if m.strip()]

        # 有効なIDのみフィルタ
        valid_ids = [mid for mid in merge_ids if pm.exists(mid)]
        if not valid_ids:
            return "", "", f"[ERROR] no valid presets in: {merge_ids}", 0

        if len(valid_ids) == 1:
            preset = pm.get(valid_ids[0])
            tags = preset.tags
            negative_tags = preset.negative_tags
            display_name = preset.name
        else:
            merge_result = pm.merge(valid_ids, result_id="_node_merge", result_name="Merged")
            tags = merge_result.preset.tags
            negative_tags = merge_result.preset.negative_tags
            display_name = f"Merged({', '.join(valid_ids)})"

        # プロンプト文字列生成
        parts = [f"({t.tag}:{t.weight:.2f})" if t.weight != 1.0 else t.tag for t in tags]
        if extra_prompt.strip():
            parts.append(extra_prompt.strip())

        neg_parts = [t.tag for t in negative_tags]

        prompt = ", ".join(parts)
        negative = ", ".join(neg_parts)
        tag_count = len(tags)

        return prompt, negative, display_name, tag_count
