#!/usr/bin/env python3
"""
fps_cli.py — Face Prompt Studio CLI エントリポイント

使い方:
  python fps_cli.py compile "masterpiece, blue_eyes"
  python fps_cli.py validate
  python fps_cli.py backup create
  ./fps_cli.py compile "masterpiece" --json   (実行権限付与時)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "fps-adapters"))

from cli.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
