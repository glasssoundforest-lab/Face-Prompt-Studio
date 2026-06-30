"""fps-core.plugins — PluginManager パッケージ"""

from .base_plugin import AdapterPlugin, BasePlugin, DictionarySourcePlugin, StagePlugin
from .exceptions import (
    PluginDependencyError,
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginValidationError,
)
from .loader import (
    load_plugin_from_file,
    load_plugin_from_module,
    load_plugins_from_dir,
    safe_load_plugin_from_file,
    validate_plugin,
)
from .manager import PluginManager
from .models import PluginInfo, PluginLoadResult, PluginType
from .registry import PluginRegistry

__all__ = [
    "PluginManager",
    "PluginRegistry",
    "BasePlugin",
    "StagePlugin",
    "AdapterPlugin",
    "DictionarySourcePlugin",
    "PluginInfo",
    "PluginType",
    "PluginLoadResult",
    "load_plugin_from_file",
    "load_plugins_from_dir",
    "load_plugin_from_module",
    "safe_load_plugin_from_file",
    "validate_plugin",
    "PluginError",
    "PluginLoadError",
    "PluginNotFoundError",
    "PluginDependencyError",
    "PluginValidationError",
]
