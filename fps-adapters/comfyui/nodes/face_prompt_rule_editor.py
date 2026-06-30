"""
fps-adapters/comfyui/nodes/face_prompt_rule_editor.py
ノード: 🎭 Face Prompt Rule Editor

機能:
  - ロード済みルールの確認・動的な有効/無効切替
  - 個別ルールを ON/OFF してプロンプトへの影響をテストできる
  - ルール一覧と統計情報をレポートとして出力

入力:
  test_prompt      STRING  ルール適用テスト用プロンプト
  disable_rule_ids STRING  無効化するルールID（カンマ区切り、任意）

出力:
  rule_report      STRING  ルール一覧・統計レポート
  test_result      STRING  test_prompt にルールを適用した結果
"""

from __future__ import annotations

from typing import Any

from .node_base import FPSNodeBase, _get_pipeline_manager, _get_rule_manager


class FacePromptRuleEditorNode(FPSNodeBase):
    """Face Prompt Rule Editor ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("rule_report", "test_result")
    FUNCTION = "edit_rules"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {},
            "optional": {
                "test_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "masterpiece, blue_eyes",
                        "placeholder": "ルール適用テスト用プロンプト",
                    },
                ),
                "disable_rule_ids": (
                    "STRING",
                    {
                        "default": "",
                        "placeholder": "無効化するルールID（カンマ区切り）",
                    },
                ),
            },
        }

    def edit_rules(
        self,
        test_prompt: str = "",
        disable_rule_ids: str = "",
    ) -> tuple[str, str]:
        """
        ルール一覧レポートとテスト結果を生成する。

        Returns:
            (rule_report, test_result)
        """
        rm = _get_rule_manager()
        if rm is None:
            return "[ERROR] RuleManager の初期化に失敗しました。", ""

        # 無効化リクエストされたルールを一時的に無効化
        disable_ids = [rid.strip() for rid in disable_rule_ids.split(",") if rid.strip()]
        disabled_now: list[str] = []
        for rid in disable_ids:
            if rm.disable(rid):
                disabled_now.append(rid)

        # ── ルール一覧レポート ────────────────────────────
        report_lines = ["=== Face Prompt Rule Editor ===", ""]
        stats = rm.statistics()
        report_lines += [
            f"Total rules    : {stats['total_rules']}",
            f"Enabled rules  : {stats['enabled_rules']}",
            f"Disabled rules : {stats['disabled_rules']}",
            f"By action      : {stats['by_action']}",
            "",
            "--- Rule List (priority desc) ---",
        ]

        for rule in rm.rules():
            status = "ON " if rule.enabled else "OFF"
            cond_str = (
                ", ".join(f"{c.op}={c.value}" for c in rule.conditions)
                if rule.conditions
                else "(no condition — applies to all)"
            )
            report_lines.append(
                f"  [{status}] p={rule.priority:<3} {rule.id:<30} "
                f"{rule.action.type} -> {rule.action.value}"
            )
            report_lines.append(f"        condition: {cond_str}")
            if rule.description:
                report_lines.append(f"        desc: {rule.description}")

        if disabled_now:
            report_lines += [
                "",
                "--- Temporarily Disabled This Run ---",
                f"  {', '.join(disabled_now)}",
            ]

        validation_errors = rm.validate()
        if validation_errors:
            report_lines += ["", "--- Validation Errors ---"]
            report_lines.extend(f"  {e}" for e in validation_errors)

        rule_report = "\n".join(report_lines)

        # ── テストプロンプトへの適用結果 ──────────────────
        test_result = ""
        if test_prompt.strip():
            pm = _get_pipeline_manager()
            if pm:
                result = pm.compile(test_prompt)
                test_lines = [
                    f"Input  : {test_prompt}",
                    f"Output : {result.prompt}",
                    f"Negative: {result.negative}",
                    "",
                    "Applied rules:",
                ]
                applied = result.meta.get("applied_rules", [])
                if applied:
                    for ar in applied:
                        test_lines.append(
                            f"  [{ar.rule_id}] {ar.action} -> {ar.target_tag} ({ar.detail})"
                        )
                else:
                    test_lines.append("  (none)")
                test_result = "\n".join(test_lines)

        # 無効化を元に戻す（ノードは副作用を残さない設計）
        for rid in disabled_now:
            rm.enable(rid)

        return rule_report, test_result
