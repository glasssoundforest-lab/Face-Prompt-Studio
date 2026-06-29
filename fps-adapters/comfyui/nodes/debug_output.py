"""
fps-adapters/comfyui/nodes/debug_output.py
ノード: 🎭 Face Prompt Debug

機能:
  - Face Prompt Cleaner / Compiler の debug_text を受け取り表示
  - 元プロンプト・変換後プロンプトの差分表示
  - 辞書・ルール統計の表示

入力:
  prompt_in    STRING  元プロンプト
  prompt_out   STRING  変換後プロンプト
  debug_text   STRING  デバッグ情報テキスト（Cleaner の出力）

出力:
  report       STRING  整形済みレポート
"""

from __future__ import annotations

from typing import Any

from .node_base import FPSNodeBase, _get_dictionary_manager, _get_rule_manager


class FacePromptDebugNode(FPSNodeBase):
    """Face Prompt Debug ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("report",)
    FUNCTION = "debug"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {},
            "optional": {
                "prompt_in": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "元プロンプト",
                    },
                ),
                "prompt_out": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "変換後プロンプト",
                    },
                ),
                "debug_text": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "placeholder": "Cleaner / Compiler の debug_text を接続",
                    },
                ),
            },
        }

    def debug(
        self,
        prompt_in: str = "",
        prompt_out: str = "",
        debug_text: str = "",
    ) -> tuple[str]:
        """デバッグレポートを生成して返す"""

        lines = [
            "╔══════════════════════════════════════════╗",
            "║     Face Prompt Studio — Debug Report    ║",
            "╚══════════════════════════════════════════╝",
            "",
        ]

        # ── 入出力プロンプト ──────────────────────────────
        if prompt_in:
            lines += [
                "▶ Original Prompt:",
                f"  {prompt_in}",
                "",
            ]

        if prompt_out:
            lines += [
                "▶ Cleaned Prompt:",
                f"  {prompt_out}",
                "",
            ]

        # ── 差分表示 ──────────────────────────────────────
        if prompt_in and prompt_out:
            in_tags = set(t.strip() for t in prompt_in.split(",") if t.strip())
            out_tags = set(t.strip() for t in prompt_out.split(",") if t.strip())
            removed = in_tags - out_tags
            added = out_tags - in_tags

            if removed or added:
                lines.append("▶ Changes:")
                for r in sorted(removed):
                    lines.append(f"  ✗ {r}")
                for a in sorted(added):
                    lines.append(f"  ✚ {a}")
                lines.append("")

        # ── デバッグテキスト ──────────────────────────────
        if debug_text:
            lines += [
                "▶ Pipeline Detail:",
                debug_text,
                "",
            ]

        # ── 辞書・ルール統計 ──────────────────────────────
        dm = _get_dictionary_manager()
        if dm:
            try:
                stats = dm.statistics()
                lines += [
                    "▶ Dictionary Stats:",
                    f"  Total keys   : {stats['total_keys']}",
                    f"  Categories   : {', '.join(dm.categories())}",
                    f"  System files : {stats['system_files']}",
                    f"  User files   : {stats['user_files']}",
                    "",
                ]
            except Exception:
                pass

        rm = _get_rule_manager()
        if rm:
            try:
                stats = rm.statistics()
                lines += [
                    "▶ Rule Stats:",
                    f"  Total rules  : {stats['total_rules']}",
                    f"  Enabled      : {stats['enabled_rules']}",
                    f"  By action    : {stats['by_action']}",
                    "",
                ]
            except Exception:
                pass

        report = "\n".join(lines)
        return (report,)
