"""
fps-adapters/comfyui/nodes/face_prompt_session.py
ノード: 🎭 Face Prompt Session  ★v2.8 新設

ComfyUI 内でプロンプトのセッションを管理する。
複数バリエーションを1セッションとして蓄積・比較できる。

FacePromptSessionSaveNode — エントリをセッションに保存
  入力: session_id / pos / neg / label / score
  出力: entry_index / session_id / status

FacePromptSessionLoadNode — セッションのベストエントリを取得
  入力: session_id
  出力: best_pos / best_neg / best_score / entry_count
"""
from __future__ import annotations
import json
from typing import Any
from .node_base import FPSNodeBase, _get_context


class FacePromptSessionSaveNode(FPSNodeBase):
    """プロンプトをセッションに保存するノード"""

    RETURN_TYPES  = ("INT", "STRING", "STRING")
    RETURN_NAMES  = ("entry_index", "session_id", "status")
    FUNCTION      = "save_to_session"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "pos_prompt": ("STRING", {"multiline": True, "default": ""}),
                "session_name": ("STRING", {
                    "default": "my_session",
                    "placeholder": "セッション名（なければ自動作成）",
                }),
            },
            "optional": {
                "session_id": ("STRING", {"default": ""}),
                "neg_prompt": ("STRING", {"multiline": True, "default": ""}),
                "label":      ("STRING", {"default": ""}),
                "score":      ("FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0}),
            },
        }

    def save_to_session(
        self,
        pos_prompt: str,
        session_name: str = "my_session",
        session_id: str  = "",
        neg_prompt: str  = "",
        label: str       = "",
        score: float     = 0.0,
    ) -> tuple[int, str, str]:
        ctx = _get_context()
        if ctx is None:
            return (-1, "", "Error: Context unavailable")
        try:
            sm = ctx.session_manager
            # セッション ID 未指定なら名前で検索 or 新規作成
            if not session_id.strip():
                sessions = sm.list_all()
                matched = next((s for s in sessions
                                if s.name == session_name.strip()), None)
                if matched:
                    session = matched
                else:
                    session = sm.create(session_name.strip())
                session_id = session.id
            entry = sm.add_entry(
                session_id, pos_prompt, neg_prompt, label, score
            )
            if entry is None:
                return (-1, session_id, f"Error: Session '{session_id}' not found")
            return (entry.index, session_id,
                    f"✅ saved: {session_name}[{entry.index}] score={score:.1f}")
        except Exception as e:
            return (-1, session_id, f"Error: {e}")


class FacePromptSessionLoadNode(FPSNodeBase):
    """セッションのベストエントリを取得するノード"""

    RETURN_TYPES  = ("STRING", "STRING", "FLOAT", "INT", "STRING")
    RETURN_NAMES  = ("best_pos", "best_neg", "best_score",
                     "entry_count", "session_info")
    FUNCTION      = "load_best"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "session_id": ("STRING", {
                    "default": "",
                    "placeholder": "セッション ID",
                }),
            },
        }

    def load_best(self, session_id: str) -> tuple[str, str, float, int, str]:
        ctx = _get_context()
        if ctx is None:
            return ("", "", 0.0, 0, '{"error":"Context unavailable"}')
        try:
            sm = ctx.session_manager
            s  = sm.get(session_id.strip())
            if s is None:
                return ("", "", 0.0, 0,
                        json.dumps({"error": f"Session '{session_id}' not found"}))
            best = s.best_entry
            info = json.dumps({
                "id": s.id, "name": s.name,
                "entry_count": s.entry_count,
                "best_index": best.index if best else None,
                "best_label": best.label if best else None,
            }, ensure_ascii=False, indent=2)
            return (
                best.pos   if best else "",
                best.neg   if best else "",
                best.score if best else 0.0,
                s.entry_count, info,
            )
        except Exception as e:
            return ("", "", 0.0, 0, json.dumps({"error": str(e)}))
