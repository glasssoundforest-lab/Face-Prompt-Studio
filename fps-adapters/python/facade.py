"""
fps-adapters/python/facade.py — FacePromptStudio Facade

外部開発者・スクリプトから Face Prompt Studio の全機能に
単一クラス経由でアクセスできる統合ファサード。

将来の pip パッケージ化（`pip install face-prompt-studio` での配布）
を見据え、内部 Manager の存在を意識せずに使える薄いラッパーとして設計。

使い方:
    from python.facade import FacePromptStudio

    studio = FacePromptStudio()
    result = studio.compile("masterpiece, blue_eyes")
    print(result.prompt)

    analysis = studio.optimize("blue_eyes, brown_eyes")
    print(analysis.score.overall_score)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).parents[2]
_CORE = _ROOT / "fps-core"
_ADAPTERS = _ROOT / "fps-adapters"

for _p in (str(_CORE), str(_ADAPTERS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class FacePromptStudio:
    """
    Face Prompt Studio 統合ファサードクラス。

    内部で DictionaryManager / RuleManager / PresetManager /
    PipelineManager / CacheManager / BackupManager / OptimizerManager /
    HistoryManager / PluginManager / EventBus を自動初期化し、
    シンプルなメソッド群として公開する。

    使い方:
        studio = FacePromptStudio()
        result = studio.compile("masterpiece, blue_eyes")

        comfyui_json = studio.export(result, "comfyui")
        a1111_prompt = studio.export(result, "a1111")["prompt"]

        analysis = studio.optimize("blue_eyes, brown_eyes")

        studio.record_history(result)
        studio.backup()
    """

    def __init__(
        self,
        data_root: str | Path | None = None,
        enable_cache: bool = True,
        enable_events: bool = False,
        track_history: bool = False,
    ) -> None:
        """
        Args:
            data_root:      fps-data ディレクトリのパス（省略時はリポジトリ標準位置）
            enable_cache:   パイプラインキャッシュを有効化するか
            enable_events:  EventBus を有効化するか
            track_history:  compile() 結果を自動で履歴記録するか
        """
        self.root = _ROOT
        self.data_root = Path(data_root) if data_root else (_ROOT / "fps-data")
        self._track_history = track_history

        self._dictionary_manager: Any = None
        self._rule_manager: Any = None
        self._preset_manager: Any = None
        self._pipeline_manager: Any = None
        self._cache_manager: Any = None
        self._backup_manager: Any = None
        self._optimizer_manager: Any = None
        self._history_manager: Any = None
        self._plugin_manager: Any = None
        self._event_bus: Any = None

        self._enable_cache = enable_cache
        self._enable_events = enable_events

        self._initialize()

    # ══════════════════════════════════════════════════════════════
    # Initialization
    # ══════════════════════════════════════════════════════════════

    def _initialize(self) -> None:
        from dictionary.manager import DictionaryManager
        from pipeline.category_weights import CategoryWeightTable
        from pipeline.manager import PipelineManager
        from rules.manager import RuleManager

        dm = DictionaryManager(
            system_dir=self.data_root / "dictionaries" / "system",
            user_dir=self.data_root / "dictionaries" / "user",
        )
        dm.load()
        self._dictionary_manager = dm

        rm = RuleManager(rule_dir=self.data_root / "rules")
        rm.load()
        self._rule_manager = rm

        if self._enable_cache:
            from cache.manager import CacheManager

            self._cache_manager = CacheManager(max_size=256, default_ttl=3600)

        if self._enable_events:
            from events.event_bus import EventBus

            self._event_bus = EventBus()

        pm = PipelineManager(
            cache_manager=self._cache_manager,
            event_bus=self._event_bus,
        )
        weight_path = self.data_root / "rules" / "category_weights.json"
        ctx: dict[str, Any] = {
            "dictionary_manager": self._dictionary_manager,
            "rule_manager": self._rule_manager,
        }
        if weight_path.exists():
            ctx["category_weight_table"] = CategoryWeightTable.load(weight_path)
        pm.set_context(**ctx)
        self._pipeline_manager = pm

    # ══════════════════════════════════════════════════════════════
    # Core: Compile
    # ══════════════════════════════════════════════════════════════

    def compile(self, prompt: str) -> Any:
        """
        プロンプトをコンパイルする。

        Args:
            prompt: DSL 形式のプロンプト文字列

        Returns:
            PipelineResult
        """
        result = self._pipeline_manager.compile(prompt)
        if self._track_history:
            self.record_history(result, input_prompt=prompt)
        return result

    def export(self, result: Any, adapter: str = "comfyui") -> dict[str, Any]:
        """
        コンパイル結果を指定アダプター形式に変換する。

        Args:
            result:  compile() の戻り値（PipelineResult）
            adapter: "comfyui" | "a1111" | "novelai"

        Returns:
            アダプター形式の辞書
        """
        if adapter == "comfyui":
            from comfyui.adapter import ComfyUIAdapter

            return ComfyUIAdapter(api_version="v1").convert(result)
        if adapter == "a1111":
            from a1111.adapter import A1111Adapter

            return A1111Adapter().convert(result)
        if adapter == "novelai":
            from novelai.adapter import NovelAIAdapter

            return NovelAIAdapter().convert(result)
        raise ValueError(f"unknown adapter: '{adapter}'")

    # ══════════════════════════════════════════════════════════════
    # Dictionary
    # ══════════════════════════════════════════════════════════════

    def lookup(self, tag: str) -> Any:
        """辞書からタグを検索する"""
        return self._dictionary_manager.lookup(tag)

    def dictionary_stats(self) -> dict[str, Any]:
        """辞書統計を返す"""
        return self._dictionary_manager.statistics()

    def dictionary_categories(self) -> list[str]:
        """辞書のカテゴリ一覧を返す"""
        return self._dictionary_manager.categories()

    # ══════════════════════════════════════════════════════════════
    # Presets
    # ══════════════════════════════════════════════════════════════

    @property
    def _presets(self) -> Any:
        if self._preset_manager is None:
            from preset.manager import PresetManager

            pm = PresetManager(
                system_dir=self.data_root / "presets" / "system",
                user_dir=self.data_root / "presets" / "user",
            )
            pm.load()
            self._preset_manager = pm
        return self._preset_manager

    def list_presets(self) -> list[Any]:
        """プリセット一覧を返す"""
        return self._presets.list_presets()

    def apply_preset(self, preset_id: str) -> Any:
        """
        プリセットを適用してコンパイルする。

        Returns:
            PipelineResult
        """
        applied = self._presets.apply(preset_id)
        prompt_str = ", ".join(t["tag"] for t in applied["tags"])
        return self.compile(prompt_str)

    def save_preset(
        self,
        preset_id: str,
        name: str,
        tags: list[dict[str, Any]],
        negative_tags: list[dict[str, Any]] | None = None,
        description: str = "",
    ) -> Path:
        """
        新しいプリセットをユーザープリセットとして保存する。

        Args:
            preset_id:     プリセットID
            name:          表示名
            tags:          [{"tag": str, "category": str, "weight": float}, ...]
            negative_tags: ネガティブタグ（同様の形式）
            description:   説明文

        Returns:
            保存先ファイルパス
        """
        from preset.models import Preset, PresetSource, PresetTag

        preset = Preset(
            id=preset_id,
            name=name,
            tags=[
                PresetTag(
                    tag=t["tag"],
                    category=t.get("category", ""),
                    weight=t.get("weight", 1.0),
                )
                for t in tags
            ],
            negative_tags=[
                PresetTag(
                    tag=t["tag"],
                    category=t.get("category", ""),
                    weight=t.get("weight", 1.0),
                )
                for t in (negative_tags or [])
            ],
            source=PresetSource.USER,
            description=description,
        )
        return self._presets.save(preset)

    # ══════════════════════════════════════════════════════════════
    # Optimizer
    # ══════════════════════════════════════════════════════════════

    @property
    def _optimizer(self) -> Any:
        if self._optimizer_manager is None:
            from optimizer.manager import OptimizerManager

            self._optimizer_manager = OptimizerManager(dictionary_manager=self._dictionary_manager)
        return self._optimizer_manager

    def optimize(self, prompt: str) -> Any:
        """
        プロンプトの品質を分析する。

        Args:
            prompt: 分析対象プロンプト（DSL文字列）

        Returns:
            OptimizationResult
        """
        result = self.compile(prompt)
        return self._optimizer.analyze_pipeline_result(result)

    # ══════════════════════════════════════════════════════════════
    # History
    # ══════════════════════════════════════════════════════════════

    @property
    def _history(self) -> Any:
        if self._history_manager is None:
            from history.history_manager import HistoryManager

            hm = HistoryManager(
                history_file=self.root / "logs" / "prompt_history.jsonl",
                max_entries=500,
            )
            hm.load()
            self._history_manager = hm
        return self._history_manager

    def record_history(
        self,
        result: Any,
        input_prompt: str = "",
        label: str = "",
    ) -> Any:
        """compile() 結果を履歴に記録する"""
        score = 0.0
        try:
            opt = self._optimizer.analyze_pipeline_result(result)
            score = opt.score.overall_score
        except Exception:
            pass

        return self._history.record(
            input_prompt=input_prompt,
            output_prompt=result.prompt,
            output_negative=result.negative,
            tag_count=result.tag_count,
            overall_score=score,
            label=label,
        )

    def history(self, limit: int = 20) -> list[Any]:
        """変換履歴一覧を返す"""
        return self._history.list_entries(limit=limit)

    # ══════════════════════════════════════════════════════════════
    # Backup
    # ══════════════════════════════════════════════════════════════

    @property
    def _backup(self) -> Any:
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

    def backup(self, target: str = "all") -> Any:
        """
        バックアップを作成する。

        Args:
            target: "all" | "dictionary" | "rules" | "presets"

        Returns:
            BackupResult
        """
        from backup.models import BackupTarget

        target_map = {
            "all": BackupTarget.ALL,
            "dictionary": BackupTarget.DICTIONARY,
            "rules": BackupTarget.RULES,
            "presets": BackupTarget.PRESETS,
        }
        return self._backup.backup(target_map.get(target, BackupTarget.ALL))

    def list_backups(self) -> list[Any]:
        """バックアップ一覧を返す"""
        return self._backup.list_backups()

    def restore_backup(self, backup_id: str) -> Any:
        """バックアップをリストアする"""
        return self._backup.restore(backup_id)

    # ══════════════════════════════════════════════════════════════
    # Plugins
    # ══════════════════════════════════════════════════════════════

    @property
    def _plugins(self) -> Any:
        if self._plugin_manager is None:
            from plugins.manager import PluginManager

            self._plugin_manager = PluginManager()
        return self._plugin_manager

    def load_plugin(self, path: str | Path) -> int:
        """プラグインファイルをロードする"""
        return self._plugins.load_from_file(path)

    def apply_plugins(self) -> int:
        """ロード済みステージプラグインをパイプラインに統合する"""
        return self._plugins.apply_to_pipeline(self._pipeline_manager)

    # ══════════════════════════════════════════════════════════════
    # Validation
    # ══════════════════════════════════════════════════════════════

    def validate(self) -> dict[str, list[str]]:
        """辞書/ルール/プリセットを検証する。エラーがあるものだけ返す"""
        errors: dict[str, list[str]] = {}

        dict_errors = self._dictionary_manager.validate()
        if dict_errors:
            errors["dictionary"] = dict_errors

        rule_errors = self._rule_manager.validate()
        if rule_errors:
            errors["rules"] = rule_errors

        preset_errors = self._presets.validate()
        if preset_errors:
            errors["presets"] = preset_errors

        return errors

    def is_valid(self) -> bool:
        """全データが検証エラーなしかどうかを返す"""
        return len(self.validate()) == 0

    # ══════════════════════════════════════════════════════════════
    # Misc
    # ══════════════════════════════════════════════════════════════

    def statistics(self) -> dict[str, Any]:
        """全体の統計情報を返す"""
        stats: dict[str, Any] = {
            "dictionary": self._dictionary_manager.statistics(),
            "rules": self._rule_manager.statistics(),
            "pipeline": self._pipeline_manager.statistics(),
        }
        if self._cache_manager is not None:
            stats["cache"] = self._pipeline_manager.cache_statistics()
        return stats

    def __repr__(self) -> str:
        return (
            f"FacePromptStudio(data_root={self.data_root}, "
            f"cache={self._enable_cache}, events={self._enable_events})"
        )
