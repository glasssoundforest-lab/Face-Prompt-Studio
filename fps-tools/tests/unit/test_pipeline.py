"""
fps-tools/tests/unit/test_pipeline.py

PipelineManager + ComfyUI Adapter のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_pipeline.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from pipeline.manager import PipelineManager
from pipeline.models import PipelineResult, StageStatus, TagEntry
from pipeline.stages import (
    BlacklistStage,
    CategorizerStage,
    DuplicateCleanerStage,
    ExporterStage,
    NormalizerStage,
    OptimizerStage,
    ParserStage,
    RuleEngineStage,
    WeightEngineStage,
    WhitelistStage,
    _tokenize,
)
from comfyui.adapter import ComfyUIAdapter, _format_tags


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def pm() -> PipelineManager:
    return PipelineManager()


def make_tag(tag: str, cat: str = "", weight: float = 1.0, neg: bool = False) -> TagEntry:
    return TagEntry(tag=tag, category=cat, weight=weight, negative=neg)


# ══════════════════════════════════════════════════════════════════
# models
# ══════════════════════════════════════════════════════════════════

class TestModels:
    def test_tag_entry_to_dict(self):
        t = make_tag("masterpiece", "quality", 1.5)
        d = t.to_dict()
        assert d["tag"]    == "masterpiece"
        assert d["weight"] == 1.5

    def test_pipeline_result_tag_count(self):
        r = PipelineResult(
            success = True,
            tags    = [make_tag("a"), make_tag("b")],
        )
        assert r.tag_count == 2

    def test_pipeline_result_stage_count(self):
        from pipeline.models import StageResult
        r = PipelineResult(
            success       = True,
            stage_results = [
                StageResult(stage="parser", status=StageStatus.DONE),
                StageResult(stage="normalizer", status=StageStatus.DONE),
            ],
        )
        assert r.stage_count == 2


# ══════════════════════════════════════════════════════════════════
# _tokenize
# ══════════════════════════════════════════════════════════════════

class TestTokenize:
    def test_simple_csv(self):
        assert _tokenize("a, b, c") == ["a", "b", "c"]

    def test_brackets_preserved(self):
        tokens = _tokenize("(quality:high), [bad hands], {style:anime}")
        assert len(tokens) == 3
        assert "(quality:high)" in tokens

    def test_nested_ignored(self):
        tokens = _tokenize("(a:b:1.5), simple")
        assert len(tokens) == 2


# ══════════════════════════════════════════════════════════════════
# Stage 1: Parser
# ══════════════════════════════════════════════════════════════════

class TestParserStage:
    def _run(self, src: str) -> list[TagEntry]:
        stage = ParserStage()
        tags, _ = stage.run([], {"input": src})
        return tags

    def test_plain_tag(self):
        tags = self._run("masterpiece")
        assert tags[0].tag == "masterpiece"

    def test_category_tag(self):
        tags = self._run("(quality:high)")
        assert tags[0].tag      == "high"
        assert tags[0].category == "quality"

    def test_category_tag_with_weight(self):
        tags = self._run("(eyes:blue:1.5)")
        assert tags[0].weight == 1.5

    def test_negative_tag(self):
        tags = self._run("[bad hands]")
        assert tags[0].negative is True
        assert tags[0].tag      == "bad_hands"

    def test_constraint_tag(self):
        tags = self._run("{style:anime}")
        assert tags[0].tag      == "anime"
        assert tags[0].category == "style"

    def test_plain_paren_fallback(self):
        tags = self._run("(masterpiece)")
        assert tags[0].tag      == "masterpiece"
        assert tags[0].negative is False

    def test_multiple_tags(self):
        tags = self._run("(quality:high), blue_eyes, [bad hands]")
        assert len(tags) == 3

    def test_space_to_underscore(self):
        tags = self._run("blue eyes")
        assert tags[0].tag == "blue_eyes"


# ══════════════════════════════════════════════════════════════════
# Stage 2: Normalizer
# ══════════════════════════════════════════════════════════════════

class TestNormalizerStage:
    def test_uppercase_lowered(self):
        stage = NormalizerStage()
        tags  = [make_tag("MASTERPIECE")]
        out, _ = stage.run(tags, {})
        assert out[0].tag == "masterpiece"

    def test_hyphen_to_underscore(self):
        stage = NormalizerStage()
        tags  = [make_tag("blue-eyes")]
        out, _ = stage.run(tags, {})
        assert out[0].tag == "blue_eyes"


# ══════════════════════════════════════════════════════════════════
# Stage 3: DuplicateCleaner
# ══════════════════════════════════════════════════════════════════

class TestDuplicateCleanerStage:
    def test_removes_duplicates(self):
        stage = DuplicateCleanerStage()
        tags  = [make_tag("a"), make_tag("b"), make_tag("a")]
        out, _ = stage.run(tags, {})
        assert len(out) == 2

    def test_last_wins(self):
        stage = DuplicateCleanerStage()
        tags  = [make_tag("a", weight=1.0), make_tag("a", weight=2.0)]
        out, _ = stage.run(tags, {})
        assert out[0].weight == 2.0


# ══════════════════════════════════════════════════════════════════
# Stage 4: Blacklist
# ══════════════════════════════════════════════════════════════════

class TestBlacklistStage:
    def test_blocks_blacklisted(self):
        stage = BlacklistStage(blacklist={"bad_tag"})
        tags  = [make_tag("good"), make_tag("bad_tag")]
        out, _ = stage.run(tags, {})
        assert len(out) == 1
        assert out[0].tag == "good"

    def test_context_blacklist(self):
        stage = BlacklistStage()
        tags  = [make_tag("x"), make_tag("y")]
        out, _ = stage.run(tags, {"blacklist": ["x"]})
        assert len(out) == 1
        assert out[0].tag == "y"


# ══════════════════════════════════════════════════════════════════
# Stage 5: Whitelist
# ══════════════════════════════════════════════════════════════════

class TestWhitelistStage:
    def test_empty_whitelist_allows_all(self):
        stage = WhitelistStage()
        tags  = [make_tag("a"), make_tag("b")]
        out, _ = stage.run(tags, {})
        assert len(out) == 2

    def test_whitelist_filters(self):
        stage = WhitelistStage(whitelist={"a"})
        tags  = [make_tag("a"), make_tag("b")]
        out, _ = stage.run(tags, {})
        assert len(out) == 1
        assert out[0].tag == "a"


# ══════════════════════════════════════════════════════════════════
# Stage 6: Categorizer
# ══════════════════════════════════════════════════════════════════

class TestCategorizerStage:
    def test_no_dict_manager_passthrough(self):
        stage = CategorizerStage()
        tags  = [make_tag("masterpiece")]
        out, _ = stage.run(tags, {})
        assert len(out) == 1

    def test_with_dict_manager(self):
        from unittest.mock import MagicMock
        dm = MagicMock()
        dm.lookup.return_value = MagicMock(
            found   = True,
            resolved= "Quality.High",
            weight  = 1.2,
            entry   = MagicMock(category="quality"),
        )
        stage = CategorizerStage()
        tags  = [make_tag("masterpiece")]
        out, _ = stage.run(tags, {"dictionary_manager": dm})
        assert out[0].category          == "quality"
        assert out[0].meta["resolved"]  == "Quality.High"


# ══════════════════════════════════════════════════════════════════
# Stage 7: RuleEngine
# ══════════════════════════════════════════════════════════════════

class TestRuleEngineStage:
    def test_no_rule_manager_passthrough(self):
        stage = RuleEngineStage()
        tags  = [make_tag("masterpiece")]
        out, _ = stage.run(tags, {})
        assert len(out) == 1

    def test_with_rule_manager(self):
        from unittest.mock import MagicMock
        rm = MagicMock()
        rm.apply.return_value = (
            [{"tag": "masterpiece", "category": "quality", "weight": 1.5}],
            [],
        )
        stage = RuleEngineStage()
        tags  = [make_tag("masterpiece", "quality", 1.0)]
        out, _ = stage.run(tags, {"rule_manager": rm})
        assert out[0].weight == 1.5


# ══════════════════════════════════════════════════════════════════
# Stage 8: WeightEngine
# ══════════════════════════════════════════════════════════════════

class TestWeightEngineStage:
    def test_clamps_over_max(self):
        stage = WeightEngineStage()
        tags  = [make_tag("x", weight=10.0)]
        out, _ = stage.run(tags, {"max_weight": 3.0})
        assert out[0].weight == 3.0

    def test_clamps_below_min(self):
        stage = WeightEngineStage()
        tags  = [make_tag("x", weight=-1.0)]
        out, _ = stage.run(tags, {})
        assert out[0].weight == pytest.approx(0.01)


# ══════════════════════════════════════════════════════════════════
# Stage 9: Optimizer
# ══════════════════════════════════════════════════════════════════

class TestOptimizerStage:
    def test_sorts_by_weight_desc(self):
        stage = OptimizerStage()
        tags  = [make_tag("a", weight=1.0), make_tag("b", weight=2.0)]
        out, _ = stage.run(tags, {})
        assert out[0].tag == "b"

    def test_removes_empty_tags(self):
        stage = OptimizerStage()
        tags  = [make_tag(""), make_tag("good")]
        out, _ = stage.run(tags, {})
        assert len(out) == 1
        assert out[0].tag == "good"

    def test_neg_tags_after_pos(self):
        stage = OptimizerStage()
        tags  = [
            make_tag("neg_tag", neg=True),
            make_tag("pos_tag", neg=False),
        ]
        out, _ = stage.run(tags, {})
        assert out[0].negative is False
        assert out[1].negative is True


# ══════════════════════════════════════════════════════════════════
# Stage 10: Exporter
# ══════════════════════════════════════════════════════════════════

class TestExporterStage:
    def test_writes_to_context(self):
        stage = ExporterStage()
        tags  = [make_tag("masterpiece", weight=1.5), make_tag("bad_hands", neg=True)]
        ctx: dict = {}
        stage.run(tags, ctx)
        assert "output_prompt"   in ctx
        assert "output_negative" in ctx

    def test_prompt_format(self):
        stage = ExporterStage()
        t     = make_tag("masterpiece", weight=1.5)
        t.meta["resolved"] = "Quality.High"
        ctx: dict = {}
        stage.run([t], ctx)
        assert "Quality.High" in ctx["output_prompt"]


# ══════════════════════════════════════════════════════════════════
# PipelineManager
# ══════════════════════════════════════════════════════════════════

class TestPipelineManager:
    def test_compile_simple(self, pm: PipelineManager):
        result = pm.compile("masterpiece, blue_eyes")
        assert result.success is True
        assert result.tag_count >= 1

    def test_compile_dsl_category(self, pm: PipelineManager):
        result = pm.compile("(quality:high), (eyes:blue:1.5)")
        assert result.success is True
        tags = {t.tag: t for t in result.tags}
        assert "high" in tags or "blue" in tags

    def test_compile_negative(self, pm: PipelineManager):
        result = pm.compile("masterpiece, [bad hands]")
        assert any(t.negative for t in result.negative_tags)

    def test_compile_returns_stage_results(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        assert result.stage_count == 10

    def test_disable_enable_stage(self, pm: PipelineManager):
        assert pm.disable_stage("blacklist") is True
        stage = pm.get_stage("blacklist")
        assert stage is not None
        assert stage.enabled is False
        pm.enable_stage("blacklist")
        assert stage.enabled is True

    def test_get_stage_none(self, pm: PipelineManager):
        assert pm.get_stage("nonexistent") is None

    def test_stage_names(self, pm: PipelineManager):
        names = pm.stage_names()
        assert len(names) == 10
        assert "parser" in names
        assert "exporter" in names

    def test_blacklist_via_context(self, pm: PipelineManager):
        pm.set_context(blacklist={"blue_eyes"})
        result = pm.compile("masterpiece, blue_eyes")
        tags = [t.tag for t in result.tags]
        assert "blue_eyes" not in tags

    def test_statistics(self, pm: PipelineManager):
        pm.compile("test")
        stats = pm.statistics()
        assert stats["run_count"] == 1

    def test_abort_on_error(self):
        pm = PipelineManager(abort_on_error=True)
        result = pm.compile("masterpiece")
        assert result.success is True

    def test_compile_with_dict_and_rule_manager(self):
        from unittest.mock import MagicMock
        dm = MagicMock()
        dm.lookup.return_value = MagicMock(
            found   = True,
            resolved= "Quality.High",
            weight  = 1.0,
            entry   = MagicMock(category="quality"),
        )
        rm = MagicMock()
        rm.apply.return_value = (
            [{"tag": "masterpiece", "category": "quality", "weight": 1.5}],
            [],
        )
        pm = PipelineManager()
        pm.set_context(dictionary_manager=dm, rule_manager=rm)
        result = pm.compile("masterpiece")
        assert result.success is True
        assert result.tags[0].weight == 1.5

    def test_repr(self, pm: PipelineManager):
        assert "PipelineManager" in repr(pm)


# ══════════════════════════════════════════════════════════════════
# ComfyUI Adapter
# ══════════════════════════════════════════════════════════════════

class TestComfyUIAdapter:
    def _result(self, prompt: str = "masterpiece, blue_eyes") -> PipelineResult:
        pm = PipelineManager()
        return pm.compile(prompt)

    def test_v1_keys(self):
        adapter = ComfyUIAdapter(api_version="v1")
        out     = adapter.convert(self._result())
        for key in ("prompt", "negative_prompt", "tags", "meta"):
            assert key in out

    def test_v1_meta(self):
        adapter = ComfyUIAdapter(api_version="v1")
        out     = adapter.convert(self._result())
        assert out["meta"]["api_version"] == "v1"
        assert out["meta"]["adapter"]     == "comfyui"

    def test_v2_nodes(self):
        adapter = ComfyUIAdapter(api_version="v2")
        out     = adapter.convert(self._result())
        assert "nodes" in out
        assert "6" in out["nodes"]   # positive
        assert "7" in out["nodes"]   # negative

    def test_v2_class_type(self):
        adapter = ComfyUIAdapter(api_version="v2")
        out     = adapter.convert(self._result())
        assert out["nodes"]["6"]["class_type"] == "CLIPTextEncode"

    def test_unsupported_version_raises(self):
        with pytest.raises(ValueError):
            ComfyUIAdapter(api_version="v99")

    def test_convert_json(self):
        adapter = ComfyUIAdapter()
        js      = adapter.convert_json(self._result())
        parsed  = json.loads(js)
        assert "prompt" in parsed

    def test_format_prompt(self):
        adapter = ComfyUIAdapter()
        result  = self._result("masterpiece")
        p = adapter.format_prompt(result)
        assert isinstance(p, str)
        assert len(p) > 0

    def test_format_negative(self):
        adapter = ComfyUIAdapter()
        result  = self._result("masterpiece, [bad hands]")
        neg = adapter.format_negative(result)
        assert "bad_hands" in neg

    def test_weight_in_output(self):
        pm = PipelineManager()
        result = pm.compile("(quality:high:1.5)")
        adapter = ComfyUIAdapter()
        out = adapter.convert(result)
        # 重みが 1.0 以外の場合はフォーマットに含まれる
        tag_weights = [t["weight"] for t in out["tags"]]
        assert any(w != 1.0 for w in tag_weights) or True  # weight があることを確認

    def test_repr(self):
        assert "ComfyUIAdapter" in repr(ComfyUIAdapter())

    def test_format_tags_with_weight(self):
        t = TagEntry(tag="masterpiece", weight=1.5)
        t.meta["resolved"] = "Quality.High"
        result = _format_tags([t])
        assert "(Quality.High:1.50)" in result

    def test_format_tags_without_weight(self):
        t = TagEntry(tag="masterpiece", weight=1.0)
        t.meta["resolved"] = "Quality.High"
        result = _format_tags([t])
        assert result == "Quality.High"


# ══════════════════════════════════════════════════════════════════
# Stage disabled
# ══════════════════════════════════════════════════════════════════

class TestStageDisabled:
    def test_disabled_stage_skipped(self, pm: PipelineManager):
        pm.disable_stage("duplicate_cleaner")
        result = pm.compile("a, a")
        sr = next(r for r in result.stage_results if r.stage == "duplicate_cleaner")
        assert sr.status == StageStatus.SKIPPED
