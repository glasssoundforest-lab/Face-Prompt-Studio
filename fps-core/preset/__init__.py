"""fps-core.preset — PresetManager パッケージ"""

from .exceptions import (
    PresetError,
    PresetLoadError,
    PresetNotFoundError,
    PresetSaveError,
    PresetValidationError,
)
from .manager import PresetManager
from .merger import diff_presets, merge_presets
from .models import MergeResult, Preset, PresetFile, PresetSource, PresetTag

__all__ = [
    "PresetManager",
    "Preset",
    "PresetTag",
    "PresetFile",
    "PresetSource",
    "MergeResult",
    "merge_presets",
    "diff_presets",
    "PresetError",
    "PresetLoadError",
    "PresetNotFoundError",
    "PresetSaveError",
    "PresetValidationError",
]
