"""
fps-adapters/cli/context.py — CLI Context

CLI 全サブコマンドが共有する Manager 群の初期化処理。
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

_ROOT = Path(__file__).parents[2]
_CORE = _ROOT / "fps-core"
_ADAPTERS = _ROOT / "fps-adapters"

for _p in (str(_CORE), str(_ADAPTERS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_template_manager_lock = threading.Lock()
_event_bus_lock = threading.Lock()


class CliContext:
    """
    CLI 実行コンテキスト。各 Manager を遅延初期化して提供する。

    使い方:
        ctx = CliContext()
        dm = ctx.dictionary_manager
        result = ctx.pipeline_manager.compile("masterpiece")
    """

    def __init__(self, data_root: Path | None = None) -> None:
        self.root = _ROOT
        self.data_root = data_root or (_ROOT / "fps-data")
        self._dictionary_manager = None
        self._rule_manager = None
        self._preset_manager = None
        self._pipeline_manager = None
        self._backup_manager = None
        self._cache_manager = None
        self._optimizer_manager = None
        self._history_manager = None
        self._plugin_manager = None
        self._template_manager = None  # ★v1.7
        self._event_bus = None            # ★v1.9
        self._user_profile_manager = None  # ★v2.0

    @property
    def dictionary_manager(self):
        if self._dictionary_manager is None:
            from dictionary.manager import DictionaryManager

            dm = DictionaryManager(
                system_dir=self.data_root / "dictionaries" / "system",
                user_dir=self.data_root / "dictionaries" / "user",
            )
            dm.load()
            self._dictionary_manager = dm
        return self._dictionary_manager

    @property
    def rule_manager(self):
        if self._rule_manager is None:
            from rules.manager import RuleManager

            rm = RuleManager(rule_dir=self.data_root / "rules")
            rm.load()
            self._rule_manager = rm
        return self._rule_manager

    @property
    def preset_manager(self):
        if self._preset_manager is None:
            from preset.manager import PresetManager

            pm = PresetManager(
                system_dir=self.data_root / "presets" / "system",
                user_dir=self.data_root / "presets" / "user",
            )
            pm.load()
            self._preset_manager = pm
        return self._preset_manager

    @property
    def cache_manager(self):
        if self._cache_manager is None:
            from cache.manager import CacheManager

            self._cache_manager = CacheManager(max_size=256, default_ttl=3600)
        return self._cache_manager

    @property
    def pipeline_manager(self):
        if self._pipeline_manager is None:
            from pipeline.category_weights import CategoryWeightTable
            from pipeline.manager import PipelineManager

            pm = PipelineManager(cache_manager=self.cache_manager)
            weight_path = self.data_root / "rules" / "category_weights.json"
            ctx: dict = {
                "dictionary_manager": self.dictionary_manager,
                "rule_manager": self.rule_manager,
            }
            if weight_path.exists():
                ctx["category_weight_table"] = CategoryWeightTable.load(weight_path)
            pm.set_context(**ctx)
            pm.set_event_bus(self.event_bus)
            self._pipeline_manager = pm
        return self._pipeline_manager

    @property
    def backup_manager(self):
        if self._backup_manager is None:
            from backup.manager import BackupManager
            from backup.models import BackupTarget

            bm = BackupManager(
                backup_dir=self.root / "backup",
                max_count=10,
                source_dirs={
                    BackupTarget.DICTIONARY: self.data_root / "dictionaries",
                    BackupTarget.RULES: self.data_root / "rules",
                    BackupTarget.PRESETS: self.data_root / "presets",
                },
            )
            bm.setup()
            self._backup_manager = bm
        return self._backup_manager

    @property
    def optimizer_manager(self):
        if self._optimizer_manager is None:
            from optimizer.manager import OptimizerManager

            self._optimizer_manager = OptimizerManager(dictionary_manager=self.dictionary_manager)
        return self._optimizer_manager

    @property
    def history_manager(self):
        if self._history_manager is None:
            from history.history_manager import HistoryManager

            hm = HistoryManager(
                history_file=self.root / "logs" / "prompt_history.jsonl",
                max_entries=500,
            )
            hm.load()
            self._history_manager = hm
        return self._history_manager

    @property
    def plugin_manager(self):
        if self._plugin_manager is None:
            from plugins.manager import PluginManager

            self._plugin_manager = PluginManager()
        return self._plugin_manager

    @property
    def template_manager(self):
        """
        ★ v1.7 — TemplateManager プロパティ（負債4解消）。
        初回アクセス時にスレッドセーフな遅延初期化を行う。
        """
        if self._template_manager is None:
            with _template_manager_lock:
                if self._template_manager is None:
                    from template.manager import TemplateManager  # type: ignore[import]
                    system_dir = self.data_root / "templates" / "system"
                    tm = TemplateManager(
                        system_dir=system_dir if system_dir.exists() else None
                    )
                    tm.load()
                    self._template_manager = tm
        return self._template_manager

    @property
    def event_bus(self):
        """
        ★ v1.9 — EventBus シングルトンプロパティ。
        PipelineManager・HistoryManager と EventBus を統合して提供する。
        """
        if self._event_bus is None:
            with _event_bus_lock:
                if self._event_bus is None:
                    from events.event_bus import EventBus  # type: ignore[import]
                    bus = EventBus()
                    bus.enable_history(max_history=500)
                    self._event_bus = bus
        return self._event_bus

    @property
    def user_profile_manager(self):
        """★ v2.0 — UserProfileManager シングルトンプロパティ。"""
        if self._user_profile_manager is None:
            from user.manager import UserProfileManager  # type: ignore[import]
            upm = UserProfileManager(profile_dir=self.data_root / "user")
            upm.load()
            self._user_profile_manager = upm
        return self._user_profile_manager


