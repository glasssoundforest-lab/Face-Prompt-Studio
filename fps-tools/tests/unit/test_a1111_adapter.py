"""
fps-tools/tests/unit/test_a1111_adapter.py

A1111Adapter のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_a1111_adapter.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from a1111.adapter import A1111Adapter
from pipeline.manager import PipelineManager


@pytest.fixture
def pm() -> PipelineManager:
    return PipelineManager()


class TestA1111Adapter:
    def test_convert_keys(self, pm: PipelineManager):
        result = pm.compile("masterpiece, blue_eyes")
        adapter = A1111Adapter()
        out = adapter.convert(result)
        for key in ("prompt", "negative_prompt", "tags", "meta"):
            assert key in out

    def test_convert_meta_adapter_name(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = A1111Adapter()
        out = adapter.convert(result)
        assert out["meta"]["adapter"] == "a1111"

    def test_format_prompt_weighted(self, pm: PipelineManager):
        result = pm.compile("(quality:high:1.5)")
        adapter = A1111Adapter()
        prompt = adapter.format_prompt(result)
        assert ":1.50)" in prompt

    def test_format_prompt_no_weight_no_parens(self, pm: PipelineManager):
        result = pm.compile("(eyes:blue)")  # weight 指定なし → 1.0
        adapter = A1111Adapter()
        prompt = adapter.format_prompt(result)
        assert "(" not in prompt or ":" not in prompt

    def test_format_negative(self, pm: PipelineManager):
        result = pm.compile("masterpiece, [bad hands]")
        adapter = A1111Adapter()
        neg = adapter.format_negative(result)
        assert "bad_hands" in neg

    def test_convert_json_valid(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = A1111Adapter()
        js = adapter.convert_json(result)
        parsed = json.loads(js)
        assert "prompt" in parsed

    def test_to_api_payload_defaults(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = A1111Adapter()
        payload = adapter.to_api_payload(result)
        assert payload["steps"] == 20
        assert payload["cfg_scale"] == 7.0
        assert payload["sampler_name"] == "Euler a"

    def test_to_api_payload_custom_params(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = A1111Adapter()
        payload = adapter.to_api_payload(result, steps=30, cfg_scale=9.0)
        assert payload["steps"] == 30
        assert payload["cfg_scale"] == 9.0

    def test_to_api_payload_extra_params(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = A1111Adapter()
        payload = adapter.to_api_payload(result, seed=12345)
        assert payload["seed"] == 12345

    def test_weight_precision_custom(self, pm: PipelineManager):
        result = pm.compile("(quality:high:1.567)")
        adapter = A1111Adapter(weight_precision=1)
        prompt = adapter.format_prompt(result)
        assert ":1.6)" in prompt or ":1.5)" in prompt or ":1.4)" in prompt

    def test_repr(self):
        adapter = A1111Adapter()
        assert "A1111Adapter" in repr(adapter)

    def test_tags_have_weight_field(self, pm: PipelineManager):
        result = pm.compile("(quality:high:1.5)")
        adapter = A1111Adapter()
        out = adapter.convert(result)
        assert all("weight" in t for t in out["tags"])
