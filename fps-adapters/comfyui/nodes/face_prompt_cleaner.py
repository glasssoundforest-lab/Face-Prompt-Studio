"""
fps-adapters/comfyui/nodes/face_prompt_cleaner.py
ノード: 🎭 Face Prompt Cleaner

機能:
  - テキストプロンプトのクリーニング（重複除去・ブラックリスト・正規化）
  - 顔特化 15 カテゴリのオン/オフスイッチ
  - カテゴリ別の重み調整
  - ネガティブプロンプトのパススルー
  - デバッグ情報出力

出力:
  cleaned_prompt  STRING  クリーニング後プロンプト
  negative        STRING  ネガティブプロンプト（パススルー）
  tag_count       INT     出力タグ数
  debug_text      STRING  デバッグ情報
"""

from __future__ import annotations

from typing import Any

from .node_base import FPSNodeBase, _get_pipeline_manager

# 顔特化 15 カテゴリ
FACE_CATEGORIES = [
    "quality",
    "eyes",
    "eyebrows",
    "eyelashes",
    "face_shape",
    "nose",
    "mouth",
    "teeth",
    "skin",
    "expression",
    "accessories",
    "glasses",
    "piercing",
    "makeup",
    "fantasy_parts",
    "hair",
    "style",
]


class FacePromptCleanerNode(FPSNodeBase):
    """Face Prompt Cleaner ノード（15カテゴリ対応）"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "STRING", "INT", "STRING")
    RETURN_NAMES = ("cleaned_prompt", "negative", "tag_count", "debug_text")
    FUNCTION = "clean"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        # カテゴリスイッチを動的に生成
        cat_switches: dict[str, Any] = {}
        for cat in FACE_CATEGORIES:
            cat_switches[f"keep_{cat}"] = ("BOOLEAN", {"default": True})

        # 重み調整（主要カテゴリのみ）
        weight_inputs: dict[str, Any] = {}
        for cat in ["quality", "eyes", "hair", "expression", "skin", "makeup"]:
            weight_inputs[f"weight_{cat}"] = (
                "FLOAT",
                {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 3.0,
                    "step": 0.05,
                },
            )

        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "入力プロンプト（DSL または通常テキスト）",
                    },
                ),
            },
            "optional": {
                "negative": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "ネガティブプロンプト（パススルー）",
                    },
                ),
                **cat_switches,
                **weight_inputs,
                "blacklist_extra": (
                    "STRING",
                    {
                        "default": "",
                        "placeholder": "追加ブラックリスト（カンマ区切り）",
                    },
                ),
                "weight_preset": (
                    [
                        "none",
                        "balanced",
                        "quality_focused",
                        "expression_focused",
                        "fantasy_focused",
                    ],
                    {"default": "none"},
                ),
                "max_weight": (
                    "FLOAT",
                    {
                        "default": 2.0,
                        "min": 0.5,
                        "max": 3.0,
                        "step": 0.1,
                    },
                ),
            },
        }

    def clean(
        self,
        prompt: str,
        negative: str = "",
        # カテゴリスイッチ（全15カテゴリ + hair + style）
        keep_quality: bool = True,
        keep_eyes: bool = True,
        keep_eyebrows: bool = True,
        keep_eyelashes: bool = True,
        keep_face_shape: bool = True,
        keep_nose: bool = True,
        keep_mouth: bool = True,
        keep_teeth: bool = True,
        keep_skin: bool = True,
        keep_expression: bool = True,
        keep_accessories: bool = True,
        keep_glasses: bool = True,
        keep_piercing: bool = True,
        keep_makeup: bool = True,
        keep_fantasy_parts: bool = True,
        keep_hair: bool = True,
        keep_style: bool = True,
        # カテゴリ別重みスケール
        weight_quality: float = 1.0,
        weight_eyes: float = 1.0,
        weight_hair: float = 1.0,
        weight_expression: float = 1.0,
        weight_skin: float = 1.0,
        weight_makeup: float = 1.0,
        # その他
        blacklist_extra: str = "",
        weight_preset: str = "none",
        max_weight: float = 2.0,
    ) -> tuple[str, str, int, str]:
        """
        プロンプトをクリーニングして返す。

        Returns:
            (cleaned_prompt, negative, tag_count, debug_text)
        """
        # ── カテゴリスイッチマップ ────────────────────────────
        category_switches = {
            "quality": keep_quality,
            "eyes": keep_eyes,
            "eyebrows": keep_eyebrows,
            "eyelashes": keep_eyelashes,
            "face_shape": keep_face_shape,
            "nose": keep_nose,
            "mouth": keep_mouth,
            "teeth": keep_teeth,
            "skin": keep_skin,
            "expression": keep_expression,
            "accessories": keep_accessories,
            "glasses": keep_glasses,
            "piercing": keep_piercing,
            "makeup": keep_makeup,
            "fantasy_parts": keep_fantasy_parts,
            "hair": keep_hair,
            "style": keep_style,
        }

        # ── カテゴリ重みスケールマップ ────────────────────────
        category_weights = {
            "quality": weight_quality,
            "eyes": weight_eyes,
            "hair": weight_hair,
            "expression": weight_expression,
            "skin": weight_skin,
            "makeup": weight_makeup,
        }

        # ── 追加ブラックリスト構築 ────────────────────────────
        blacklist: set[str] = set()
        if blacklist_extra.strip():
            blacklist.update(
                t.strip().lower().replace(" ", "_") for t in blacklist_extra.split(",") if t.strip()
            )

        # ── パイプライン実行 ──────────────────────────────────
        pm = _get_pipeline_manager(
            blacklist=blacklist or None,
            max_weight=max_weight,
            weight_preset=None if weight_preset == "none" else weight_preset,
        )

        if pm is None:
            debug = "[ERROR] PipelineManager の初期化に失敗しました。"
            return prompt, negative, 0, debug

        result = pm.compile(prompt)

        # ── カテゴリスイッチ・重みスケール適用 ────────────────
        filtered_tags = []
        skipped_tags = []
        for tag in result.tags:
            cat = tag.category.lower() if tag.category else ""
            if cat in category_switches and not category_switches[cat]:
                skipped_tags.append(tag)
                continue
            if cat in category_weights:
                tag.weight = round(tag.weight * category_weights[cat], 3)
            filtered_tags.append(tag)

        # ── 出力プロンプト生成 ────────────────────────────────
        parts: list[str] = []
        for t in filtered_tags:
            resolved = t.meta.get("resolved") or t.tag
            if t.weight != 1.0:
                parts.append(f"({resolved}:{t.weight:.2f})")
            else:
                parts.append(resolved)

        cleaned_prompt = ", ".join(parts)
        tag_count = len(filtered_tags)

        # ── デバッグ情報 ──────────────────────────────────────
        debug_lines = [
            "=== Face Prompt Cleaner Debug ===",
            f"Input    : {prompt[:60]}{'...' if len(prompt)>60 else ''}",
            f"Output   : {cleaned_prompt[:60]}{'...' if len(cleaned_prompt)>60 else ''}",
            f"Tags In  : {len(result.tags) + len(result.negative_tags)}",
            f"Tags Out : {tag_count}",
            f"Skipped  : {len(skipped_tags)} (category switch OFF)",
            f"Negative : {len(result.negative_tags)}",
            "",
            "--- Stage Results ---",
        ]
        for sr in result.stage_results:
            status = str(sr.status).upper().replace("STAGESTATUS.", "")
            debug_lines.append(f"  {sr.stage:<22} {status:<8} {sr.tags_in:>3} → {sr.tags_out:>3}")

        # ── タグ変換前後比較（パーサー直後 vs 最終出力） ──────
        debug_lines += ["", "--- Tag Diff (parsed → final) ---"]
        # rule_engine 適用前の集合を rule 結果から逆算するのは複雑なため、
        # 「カテゴリスイッチ前」(= result.tags + skipped_tags) を基準に
        # ADD/REMOVE はルール適用結果として別枠で明示する
        before_names = {t.tag for t in result.tags} | {t.tag for t in skipped_tags}
        after_names = {t.tag for t in filtered_tags}
        category_removed = sorted(before_names - after_names)
        category_kept = sorted(before_names & after_names)
        rule_added = sorted(
            {ar.target_tag for ar in result.meta.get("applied_rules", []) if ar.action == "ADD"}
        )
        if rule_added:
            debug_lines.append(f"  + added by rules : {', '.join(rule_added)}")
        if category_removed:
            debug_lines.append(f"  - removed (category OFF) : {', '.join(category_removed)}")
        debug_lines.append(f"  = passed through  : {len(category_kept)} tags")

        # ── カテゴリ別集計表 ──────────────────────────────────
        debug_lines += ["", "--- Category Summary ---"]
        cat_counts: dict[str, int] = {}
        cat_weight_sum: dict[str, float] = {}
        for t in filtered_tags:
            c = t.category or "uncategorized"
            cat_counts[c] = cat_counts.get(c, 0) + 1
            cat_weight_sum[c] = cat_weight_sum.get(c, 0.0) + t.weight
        for c in sorted(cat_counts.keys()):
            count = cat_counts[c]
            avg_w = cat_weight_sum[c] / count
            debug_lines.append(f"  {c:<14} count={count:<3} avg_weight={avg_w:.2f}")

        # ── 適用ルール一覧 ────────────────────────────────────
        applied_rules = result.meta.get("applied_rules", [])
        if applied_rules:
            debug_lines += ["", "--- Applied Rules ---"]
            for ar in applied_rules:
                debug_lines.append(f"  [{ar.rule_id}] {ar.action} → {ar.target_tag}  ({ar.detail})")
        else:
            debug_lines += ["", "--- Applied Rules ---", "  (no rules applied)"]

        debug_lines += ["", "--- Output Tags ---"]
        for t in filtered_tags:
            resolved = t.meta.get("resolved") or t.tag
            debug_lines.append(f"  [{t.category or 'unknown':<14}] {resolved}  (w={t.weight:.2f})")

        if skipped_tags:
            debug_lines += ["", "--- Skipped Tags (category OFF) ---"]
            for t in skipped_tags:
                debug_lines.append(f"  [{t.category:<14}] {t.tag}")

        if result.errors:
            debug_lines += ["", "--- Errors ---"]
            debug_lines.extend(f"  {e}" for e in result.errors)

        debug_text = "\n".join(debug_lines)
        return cleaned_prompt, negative, tag_count, debug_text
