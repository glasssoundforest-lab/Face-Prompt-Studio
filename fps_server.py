#!/usr/bin/env python3
"""
fps_server.py — Face Prompt Studio REST API サーバー起動スクリプト

使い方:
  python fps_server.py
  python fps_server.py --port 8420 --reload

依存:
  pip install fastapi uvicorn --break-system-packages
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "fps-adapters"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Face Prompt Studio REST API Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--reload", action="store_true", help="開発用オートリロード")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print(
            "[ERROR] uvicorn / fastapi がインストールされていません。\n"
            "  pip install fastapi uvicorn --break-system-packages",
            file=sys.stderr,
        )
        return 1

    from rest.app import _FASTAPI_AVAILABLE

    if not _FASTAPI_AVAILABLE:
        print("[ERROR] fastapi が利用できません。", file=sys.stderr)
        return 1

    print(f"Starting Face Prompt Studio API on http://{args.host}:{args.port}")
    print(f"  Docs: http://{args.host}:{args.port}/docs")

    uvicorn.run(
        "rest.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(Path(__file__).parent / "fps-adapters"),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
