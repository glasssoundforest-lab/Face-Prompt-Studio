"""
fps-adapters/comfyui/nodes/face_prompt_profile.py
ノード: 🎭 Face Prompt Profile  ★v2.1 新設

UserProfile を ComfyUI ノードグラフ内で活用するためのノード群。

FacePromptProfileNode:
  プロファイルから推奨タグ・除外タグを取得して文字列で出力する。
  Compiler ノードの前段に接続して使う。

  入力:
    top_n           INT     推奨タグ件数（1〜30）
    include_str     STRING  追加で含めたいタグ（カンマ区切り）

  出力:
    recommended     STRING  推奨タグ（カンマ区切り）
    excluded        STRING  除外タグ（カンマ区切り）
    style_includes  STRING  スタイルルールの always_include
    style_excludes  STRING  スタイルルールの always_exclude
    last_learned    STRING  最終学習日時（ISO）

FacePromptProfileApplyNode:
  入力タグ文字列にプロファイルを適用して返す。
  apply_profile=True の Compiler の前段として使う。

  入力:
    prompt          STRING  元のプロンプト（カンマ区切り）
    negative        STRING  元のネガティブ（カンマ区切り）
    add_excludes_to_neg  BOOLEAN  exclude を neg に追加するか

  出力:
    prompt_out      STRING  プロファイル適用後のポジティブ
    negative_out    STRING  プロファイル適用後のネガティブ
    added_tags      STRING  追加されたタグ（カンマ区切り）
    excluded_tags   STRING  除外されたタグ（カンマ区切り）

FacePromptProfileLearnNode:
  履歴から自動学習を実行する。
  定期実行やトリガー接続に使う。

  入力:
    trigger         INT     変化で実行（通常は別ノードの出力に接続）
    limit           INT     学習に使う履歴件数

  出力:
    learned         INT     新規学習タグ数
    updated         INT     更新タグ数
    total           INT     総タグ種類数
    status          STRING  実行結果メッセージ
"""

from __future__ import annotations

import json
from typing import Any

from .node_base import FPSNodeBase, _get_history_manager, _get_upm


class FacePromptProfileNode(FPSNodeBase):
    """UserProfile から推奨タグ・除外タグを取得するノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES  = ("recommended", "excluded", "style_includes", "style_excludes", "last_learned")
    FUNCTION      = "get_profile_tags"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "top_n": ("INT", {"default": 10, "min": 1, "max": 30, "step": 1}),
            },
            "optional": {
                "include_str": ("STRING", {
                    "default": "",
                    "placeholder": "追加タグ（カンマ区切り、推奨リストに追加）",
                }),
            },
        }

    def get_profile_tags(
        self, top_n: int = 10, include_str: str = ""
    ) -> tuple[str, str, str, str, str]:
        """
        プロファイルから推奨タグ・除外タグを取得する。

        Returns:
            (recommended, excluded, style_includes, style_excludes, last_learned)
        """
        upm = _get_upm()
        if upm is None:
            empty = ("", "", "", "", "profile unavailable")
            return empty

        profile = upm.get_profile()
        stats   = upm.statistics()

        # 推奨タグ
        recs = upm.recommend(top_n)
        rec_tags = [e.tag for e in recs]

        # 追加指定タグをマージ
        if include_str.strip():
            extras = [t.strip() for t in include_str.split(",") if t.strip()]
            rec_tags = list(dict.fromkeys(extras + rec_tags))

        # 除外タグ
        excluded = profile.excluded_tags()

        # スタイルルールの include / exclude
        style_inc: list[str] = []
        style_exc: list[str] = []
        for rule in profile.style_rules:
            if rule.enabled:
                style_inc.extend(rule.always_include)
                style_exc.extend(rule.always_exclude)

        last_learned = stats.get("last_learned") or "未学習"

        return (
            ", ".join(rec_tags),
            ", ".join(excluded),
            ", ".join(dict.fromkeys(style_inc)),
            ", ".join(dict.fromkeys(style_exc)),
            last_learned,
        )


class FacePromptProfileApplyNode(FPSNodeBase):
    """入力プロンプトにプロファイルを適用するノード"""

    RETURN_TYPES  = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES  = ("prompt_out", "negative_out", "added_tags", "excluded_tags")
    FUNCTION      = "apply_profile"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "元のポジティブプロンプト",
                }),
            },
            "optional": {
                "negative": ("STRING", {"multiline": True, "default": ""}),
                "add_excludes_to_neg": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Neg+Exclude ON",
                    "label_off": "Neg+Exclude OFF",
                }),
            },
        }

    def apply_profile(
        self,
        prompt: str,
        negative: str = "",
        add_excludes_to_neg: bool = True,
    ) -> tuple[str, str, str, str]:
        """
        プロファイルをプロンプトに適用する。

        Returns:
            (prompt_out, negative_out, added_tags, excluded_tags)
        """
        upm = _get_upm()
        if upm is None:
            return prompt, negative, "", ""

        # pos への適用
        original = [t.strip() for t in prompt.split(",") if t.strip()]
        applied  = upm.apply_profile(original)
        added    = [t for t in applied  if t not in original]
        excluded = [t for t in original if t not in applied]

        prompt_out = ", ".join(applied)
        neg_out    = negative

        # always_exclude を neg に追加
        if add_excludes_to_neg:
            profile = upm.get_profile()
            neg_adds: list[str] = []
            for rule in profile.style_rules:
                if rule.enabled:
                    neg_adds.extend(rule.always_exclude)
            if neg_adds:
                existing = {t.strip() for t in neg_out.split(",") if t.strip()}
                new_neg  = [t for t in neg_adds if t not in existing]
                if new_neg:
                    sep = ", " if neg_out.strip() else ""
                    neg_out = neg_out.rstrip(", ") + sep + ", ".join(new_neg)

        return (
            prompt_out,
            neg_out,
            ", ".join(added),
            ", ".join(excluded),
        )


class FacePromptProfileLearnNode(FPSNodeBase):
    """履歴から自動学習を実行するノード"""

    RETURN_TYPES  = ("INT", "INT", "INT", "STRING")
    RETURN_NAMES  = ("learned", "updated", "total", "status")
    FUNCTION      = "run_learn"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "trigger": ("INT", {
                    "default": 0,
                    "tooltip": "このノードの実行トリガー（別ノードの出力に接続）",
                }),
            },
            "optional": {
                "limit": ("INT", {"default": 200, "min": 10, "max": 1000, "step": 10}),
            },
        }

    def run_learn(self, trigger: int = 0, limit: int = 200) -> tuple[int, int, int, str]:
        """
        履歴から学習を実行する。

        Returns:
            (learned, updated, total, status)
        """
        upm = _get_upm()
        hm  = _get_history_manager()
        if upm is None or hm is None:
            return (0, 0, 0, "Error: Manager 初期化失敗")
        try:
            entries = hm.list_entries(limit=limit)
            result  = upm.learn(entries)
            upm.build_score_trends(entries, days=30)
            status = (
                f"学習完了 — 新規:{result['learned']}件 "
                f"更新:{result['updated']}件 "
                f"総計:{result['total']}件"
            )
            return (result["learned"], result["updated"], result["total"], status)
        except Exception as e:
            return (0, 0, 0, f"Error: {e}")
