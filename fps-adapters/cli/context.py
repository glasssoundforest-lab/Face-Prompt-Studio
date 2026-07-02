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

    def __init__(self, data_root: "Path | None" = None) -> None:
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
        self._user_manager = None         # ★v2.3
        self._share_manager = None        # ★v2.3
        self._batch_manager = None        # ★v2.4
        self._preset_version_manager = None  # ★v2.4
        self._ai_manager = None            # ★v2.5
        self._wildcard_manager = None     # ★v2.6
        self._character_manager = None    # ★v2.7
        self._export_manager   = None    # ★v2.8
        self._session_manager  = None    # ★v2.8
        self._translate_engine = None    # ★v2.9
        self._chain_manager    = None    # ★v2.9
        self._comfyui_client   = None    # ★v2.9
        self._marketplace      = None    # ★v3.0

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

    @property
    def user_manager(self):
        """★ v2.3 — UserManager シングルトンプロパティ。"""
        if self._user_manager is None:
            from user.auth import UserManager  # type: ignore[import]
            um = UserManager(db_path=self.data_root / "user" / "users.db")
            self._user_manager = um
        return self._user_manager

    @property
    def share_manager(self):
        """★ v2.3 — ShareManager シングルトンプロパティ。"""
        if self._share_manager is None:
            from user.share import ShareManager  # type: ignore[import]
            sm = ShareManager(db_path=self.data_root / "user" / "share.db")
            self._share_manager = sm
        return self._share_manager

    @property
    def batch_manager(self):
        """★ v2.4 — BatchManager シングルトンプロパティ。"""
        if self._batch_manager is None:
            from batch.manager import BatchManager  # type: ignore[import]
            self._batch_manager = BatchManager(
                pipeline_manager=self.pipeline_manager,
                optimizer_manager=self.optimizer_manager,
            )
        return self._batch_manager

    @property
    def preset_version_manager(self):
        """★ v2.4 — PresetVersionManager シングルトンプロパティ。"""
        if self._preset_version_manager is None:
            from preset.version_manager import PresetVersionManager  # type: ignore[import]
            self._preset_version_manager = PresetVersionManager(
                versions_dir=self.data_root / "presets" / "versions",
                max_versions=20,
            )
        return self._preset_version_manager

    @property
    def ai_manager(self):
        """★ v2.5 — AI マネージャー（LoRA/Tagger/Consistency/Negative）"""
        if self._ai_manager is None:
            from ai.lora_analyzer import LoraAnalyzer       # type: ignore
            from ai.tagger_bridge import TaggerBridge        # type: ignore
            from ai.consistency_checker import ConsistencyChecker  # type: ignore
            from ai.negative_learner import NegativeLearner  # type: ignore
            dm = self.dictionary_manager
            self._ai_manager = {
                "lora":        LoraAnalyzer(dictionary_manager=dm),
                "tagger":      TaggerBridge(dictionary_manager=dm),
                "consistency": ConsistencyChecker(dictionary_manager=dm),
                "negative":    NegativeLearner(),
            }
        return self._ai_manager

    @property
    def wildcard_manager(self):
        """★ v2.6 — WildcardManager シングルトンプロパティ。"""
        if self._wildcard_manager is None:
            from wildcard.manager import WildcardManager  # type: ignore
            self._wildcard_manager = WildcardManager(
                wildcard_dir=self.data_root / "wildcards"
            )
        return self._wildcard_manager

    @property
    def character_manager(self):
        """★ v2.7 — CharacterManager シングルトンプロパティ。"""
        if self._character_manager is None:
            from character.manager import CharacterManager  # type: ignore
            self._character_manager = CharacterManager(
                characters_dir=self.data_root / "characters"
            )
        return self._character_manager

    @property
    def export_manager(self):
        """★ v2.8 — BundleExporter（マルチフォーマットエクスポーター）。"""
        if self._export_manager is None:
            from export.exporters import BundleExporter  # type: ignore
            self._export_manager = BundleExporter()
        return self._export_manager

    @property
    def session_manager(self):
        """★ v2.8 — SessionManager シングルトンプロパティ。"""
        if self._session_manager is None:
            from session.manager import SessionManager  # type: ignore
            self._session_manager = SessionManager(
                sessions_dir=self.data_root / "sessions"
            )
        return self._session_manager

    @property
    def translate_engine(self):
        """★ v2.9 — TranslateEngine シングルトンプロパティ。"""
        if self._translate_engine is None:
            from translate.engine import TranslateEngine  # type: ignore
            self._translate_engine = TranslateEngine(
                dictionary_manager=self.dictionary_manager
            )
        return self._translate_engine

    @property
    def chain_manager(self):
        """★ v2.9 — ChainManager シングルトンプロパティ。"""
        if self._chain_manager is None:
            from chain.manager import ChainManager  # type: ignore
            self._chain_manager = ChainManager(
                chains_dir=self.data_root / "chains"
            )
        return self._chain_manager

    @property
    def comfyui_client(self):
        """★ v2.9 — ComfyUIClient シングルトンプロパティ。"""
        if self._comfyui_client is None:
            import sys
            from pathlib import Path
            _adp = str(Path(__file__).resolve().parents[1])
            if _adp not in sys.path:
                sys.path.insert(0, _adp)
            from comfyui_api.client import ComfyUIClient  # type: ignore
            self._comfyui_client = ComfyUIClient()
        return self._comfyui_client

    @property
    def marketplace(self):
        """★ v3.0 — MarketplaceManager シングルトンプロパティ。"""
        if self._marketplace is None:
            from marketplace.manager import MarketplaceManager  # type: ignore
            self._marketplace = MarketplaceManager(
                plugins_dir=self.data_root / "plugins"
            )
        return self._marketplace










