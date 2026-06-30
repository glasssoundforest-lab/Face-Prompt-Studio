"""fps-core.history — HistoryManager パッケージ"""

from .diff_viewer import diff_entries, diff_prompts, format_diff_report
from .history_manager import HistoryManager
from .models import DiffEntry, HistoryEntry

__all__ = [
    "HistoryManager",
    "HistoryEntry",
    "DiffEntry",
    "diff_prompts",
    "diff_entries",
    "format_diff_report",
]
