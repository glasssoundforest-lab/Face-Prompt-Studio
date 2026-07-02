"""
fps-adapters/comfyui_api/client.py — ComfyUI HTTP API クライアント
★ v2.9 新設

ComfyUI の HTTP API（localhost:8188）と通信する。
プロンプトをワークフロー JSON に変換して送信し、
生成完了まで待機する機能を提供する。

依存: 標準ライブラリのみ（urllib）

ComfyUI API エンドポイント:
  GET  /system_stats       — サーバー情報
  GET  /queue              — キュー状態
  POST /prompt             — ワークフロー送信
  GET  /history/{id}       — 生成履歴
  POST /queue/interrupt    — 中断
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueueEntry:
    """キューエントリ"""
    prompt_id:  str
    status:     str       # "pending" | "running" | "done" | "error"
    outputs:    dict      = field(default_factory=dict)
    error:      str       = ""
    queued_at:  str       = ""
    started_at: str       = ""
    ended_at:   str       = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id":  self.prompt_id,
            "status":     self.status,
            "outputs":    self.outputs,
            "error":      self.error,
            "queued_at":  self.queued_at,
        }


@dataclass
class QueueStatus:
    """ComfyUI キュー全体の状態"""
    running: list[str]    # 実行中の prompt_id リスト
    pending: list[str]    # 待機中の prompt_id リスト
    exec_info: dict       = field(default_factory=dict)

    @property
    def queue_remaining(self) -> int:
        return len(self.running) + len(self.pending)

    def to_dict(self) -> dict[str, Any]:
        return {
            "running":         self.running,
            "pending":         self.pending,
            "queue_remaining": self.queue_remaining,
        }


class ComfyUIClient:
    """
    ComfyUI HTTP API クライアント。

    使い方:
        client = ComfyUIClient(base_url="http://localhost:8188")
        if client.is_available():
            entry = client.queue_prompt(prompt_text, neg_text)
            result = client.wait_for_completion(entry.prompt_id)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8188",
        client_id: str | None = None,
        timeout: int = 10,
    ) -> None:
        self._base    = base_url.rstrip("/")
        self._cid     = client_id or str(uuid.uuid4())
        self._timeout = timeout

    # ── 接続確認 ──────────────────────────────────────────────────

    def is_available(self) -> bool:
        """ComfyUI が起動しているか確認する"""
        try:
            req = urllib.request.Request(f"{self._base}/system_stats")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False

    def get_system_stats(self) -> dict[str, Any]:
        """ComfyUI のシステム情報を返す"""
        try:
            req = urllib.request.Request(f"{self._base}/system_stats")
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            return {"error": str(e), "available": False}

    # ── キュー操作 ─────────────────────────────────────────────────

    def get_queue_status(self) -> QueueStatus:
        """現在のキュー状態を返す"""
        try:
            req = urllib.request.Request(f"{self._base}/queue")
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                data = json.loads(r.read().decode())
            running = [e[1] for e in data.get("queue_running", [])]
            pending = [e[1] for e in data.get("queue_pending", [])]
            return QueueStatus(running=running, pending=pending,
                               exec_info=data.get("exec_info", {}))
        except Exception:
            return QueueStatus(running=[], pending=[])

    def queue_prompt(
        self,
        pos_prompt: str,
        neg_prompt: str = "",
        workflow: dict | None = None,
        model: str = "v1-5-pruned-emaonly.ckpt",
        steps: int = 20,
        cfg: float = 7.0,
        width: int = 512,
        height: int = 512,
        seed: int = -1,
    ) -> QueueEntry:
        """
        プロンプトを ComfyUI キューに送信する。

        workflow を指定した場合はそのまま使用する。
        省略した場合は FPS のデフォルトワークフローを使用する。
        """
        import random
        if seed < 0:
            seed = random.randint(0, 2**32 - 1)

        wf = workflow or self._build_default_workflow(
            pos_prompt, neg_prompt, model, steps, cfg, width, height, seed
        )
        payload = json.dumps({
            "prompt":    wf,
            "client_id": self._cid,
        }).encode()

        try:
            req = urllib.request.Request(
                f"{self._base}/prompt",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                data = json.loads(r.read().decode())
            return QueueEntry(
                prompt_id=data.get("prompt_id", ""),
                status="pending",
                queued_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        except Exception as e:
            return QueueEntry(prompt_id="", status="error", error=str(e))

    def get_prompt_status(self, prompt_id: str) -> QueueEntry:
        """プロンプトの実行状態を返す"""
        # キューで確認
        status = self.get_queue_status()
        if prompt_id in status.running:
            return QueueEntry(prompt_id=prompt_id, status="running")
        if prompt_id in status.pending:
            return QueueEntry(prompt_id=prompt_id, status="pending")
        # 履歴で確認
        try:
            req = urllib.request.Request(
                f"{self._base}/history/{prompt_id}"
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                data = json.loads(r.read().decode())
            if prompt_id in data:
                entry_data = data[prompt_id]
                outputs = entry_data.get("outputs", {})
                return QueueEntry(
                    prompt_id=prompt_id,
                    status="done",
                    outputs=outputs,
                )
        except Exception:
            pass
        return QueueEntry(prompt_id=prompt_id, status="unknown")

    def wait_for_completion(
        self,
        prompt_id: str,
        timeout_sec: int = 120,
        poll_interval: float = 2.0,
    ) -> QueueEntry:
        """
        プロンプトの完了を待機する（ポーリング）。

        Args:
            prompt_id:     待機するプロンプト ID
            timeout_sec:   タイムアウト秒数
            poll_interval: ポーリング間隔（秒）

        Returns:
            QueueEntry（status="done" or "error"）
        """
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            entry = self.get_prompt_status(prompt_id)
            if entry.status in ("done", "error"):
                return entry
            if entry.status == "unknown":
                return QueueEntry(prompt_id=prompt_id, status="error",
                                  error="Prompt not found in queue or history")
            time.sleep(poll_interval)
        return QueueEntry(prompt_id=prompt_id, status="error",
                          error=f"Timeout after {timeout_sec}s")

    def interrupt(self) -> bool:
        """現在の生成を中断する"""
        try:
            req = urllib.request.Request(
                f"{self._base}/queue/interrupt",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False

    # ── デフォルトワークフロー ─────────────────────────────────────

    @staticmethod
    def _build_default_workflow(
        pos: str, neg: str,
        model: str, steps: int, cfg: float,
        width: int, height: int, seed: int,
    ) -> dict:
        """FPS 標準ワークフロー JSON を生成する"""
        return {
            "1": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": model}},
            "2": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": pos, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": neg, "clip": ["1", 1]}},
            "4": {"class_type": "EmptyLatentImage",
                  "inputs": {"width": width, "height": height, "batch_size": 1}},
            "5": {"class_type": "KSampler",
                  "inputs": {
                      "model": ["1", 0],
                      "positive": ["2", 0], "negative": ["3", 0],
                      "latent_image": ["4", 0],
                      "seed": seed, "steps": steps, "cfg": cfg,
                      "sampler_name": "euler", "scheduler": "normal",
                      "denoise": 1.0,
                  }},
            "6": {"class_type": "VAEDecode",
                  "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage",
                  "inputs": {"images": ["6", 0], "filename_prefix": "FPS"}},
        }
