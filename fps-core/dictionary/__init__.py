"""fps-core.dictionary — DictionaryManager パッケージ"""

from .exceptions import (
    DictionaryError,
    DictLoadError,
    DictMergeError,
    DictNotFoundError,
    DictValidationError,
)
from .manager import DictionaryManager
from .models import DictEntry, DictFile, DictSource, LookupResult

__all__ = [
    "DictionaryManager",
    "DictEntry",
    "DictFile",
    "DictSource",
    "LookupResult",
    "DictionaryError",
    "DictLoadError",
    "DictValidationError",
    "DictMergeError",
    "DictNotFoundError",
]
