"""fps-adapters.cli — Face Prompt Studio CLI パッケージ"""

from .context import CliContext
from .main import build_parser, main

__all__ = ["main", "build_parser", "CliContext"]
