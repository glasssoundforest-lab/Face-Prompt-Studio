"""
fps-adapters/comfyui/nodes/face_prompt_history.py
ノード: 🎭 Face Prompt History

機能:
  - プロンプト変換結果を履歴として記録する
  - 直近の履歴一覧・統計を表示する
  - 最新履歴との差分比較を表示する

入力:
  input_prompt    STRING  記録する元プロンプト
  output_prompt   STRING  記録する変換後プロンプト
  output_negative STRING  記録する変換後ネガティブ（任意）
  overall_score   FLOAT   品質スコア（任意、Optimizerノードと連携）
  label           STRING  履歴ラベル（任意）
  record          BOOLEAN 記録するかどうか（False ならスキップして閲覧のみ）

出力:
  history_report  STRING  履歴一覧・統計・差分レポート
  entry_id        STRING  記録されたエントリID
"""

from __future__ import annotations

from typing import Any

from .node_base import _ROOT, FPSNodeBase

_history_manager = None


def _get_history_manager():
    """HistoryManager をシングルトンで返す"""
    global _history_manager
    if _history_manager is None:
        from history.history_manager import HistoryManager

        _history_manager = HistoryManager(
            history_file=_ROOT / "logs" / "prompt_history.jsonl",
            max_entries=500,
        )
        _history_manager.load()
    return _history_manager


class FacePromptHistoryNode(FPSNodeBase):
    """Face Prompt History ノード"""

    CATEGORY = "FacePromptStudio"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("history_report", "entry_id")
    FUNCTION = "track_history"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "record": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "input_prompt": (
                    "STRING",
                    {"multiline": True, "default": "", "placeholder": "元プロンプト"},
                ),
                "output_prompt": (
                    "STRING",
                    {"multiline": True, "default": "", "placeholder": "変換後プロンプト"},
                ),
                "output_negative": (
                    "STRING",
                    {"multiline": True, "default": ""},
                ),
                "overall_score": (
                    "FLOAT",
                    {"default": 0.0, "min": 0.0, "max": 100.0, "step": 0.1},
                ),
                "label": ("STRING", {"default": "", "placeholder": "履歴ラベル（任意）"}),
            },
        }

    def track_history(
        self,
        record: bool = True,
        input_prompt: str = "",
        output_prompt: str = "",
        output_negative: str = "",
        overall_score: float = 0.0,
        label: str = "",
    ) -> tuple[str, str]:
        """
        プロンプト変換結果を履歴記録し、レポートを返す。

        Returns:
            (history_report, entry_id)
        """
        try:
            hm = _get_history_manager()
        except Exception as e:
            return f"[ERROR] HistoryManager の初期化に失敗しました: {e}", ""

        entry_id = ""
        if record and (input_prompt.strip() or output_prompt.strip()):
            tag_count = len([t for t in output_prompt.split(",") if t.strip()])
            entry = hm.record(
                input_prompt=input_prompt,
                output_prompt=output_prompt,
                output_negative=output_negative,
                tag_count=tag_count,
                overall_score=overall_score,
                label=label,
            )
            entry_id = entry.id

        # ── レポート生成 ──────────────────────────────────
        lines = ["=== Face Prompt History ===", ""]
        stats = hm.statistics()
        lines += [
            f"Total entries : {stats['total_entries']} (max: {stats['max_entries']})",
            f"Favorites     : {stats['favorite_count']}",
            f"Avg score     : {stats['avg_score']}",
            "",
            "--- Recent History (newest first) ---",
        ]

        recent = hm.list_entries(limit=10)
        for e in recent:
            star = "★" if e.favorite else " "
            label_str = f" [{e.label}]" if e.label else ""
            lines.append(
                f"  {star} {e.created_at_str}  score={e.overall_score:.1f}  "
                f"tags={e.tag_count}{label_str}"
            )
            lines.append(f"      in : {e.input_prompt[:60]}")
            lines.append(f"      out: {e.output_prompt[:60]}")

        if not recent:
            lines.append("  (no history yet)")

        # ── 直近2件の差分比較 ─────────────────────────────
        if len(recent) >= 2:
            from history.diff_viewer import diff_entries, format_diff_report

            diff = diff_entries(recent[1], recent[0])
            lines += ["", format_diff_report(diff, "Previous", "Latest")]

        history_report = "\n".join(lines)
        return history_report, entry_id
