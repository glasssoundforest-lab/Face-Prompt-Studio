"""
fps-tools/tests/unit/test_novelai_adapter.py

NovelAIAdapter のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_novelai_adapter.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from novelai.adapter import NovelAIAdapter, _to_brace_notation
from pipeline.manager import PipelineManager


@pytest.fixture
def pm() -> PipelineManager:
    return PipelineManager()


class TestNovelAIAdapter:
    def test_convert_keys(self, pm: PipelineManager):
        result = pm.compile("masterpiece, blue_eyes")
        adapter = NovelAIAdapter()
        out = adapter.convert(result)
        for key in ("prompt", "negative_prompt", "tags", "meta"):
            assert key in out

    def test_convert_meta_adapter_name(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = NovelAIAdapter()
        out = adapter.convert(result)
        assert out["meta"]["adapter"] == "novelai"

    def test_format_prompt_explicit_weight_default(self, pm: PipelineManager):
        result = pm.compile("(quality:high:1.5)")
        adapter = NovelAIAdapter()  # use_brace_notation=False がデフォルト
        prompt = adapter.format_prompt(result)
        assert ":1.50)" in prompt

    def test_format_prompt_brace_notation(self, pm: PipelineManager):
        result = pm.compile("(quality:high:1.05)")
        adapter = NovelAIAdapter(use_brace_notation=True)
        prompt = adapter.format_prompt(result)
        assert "{" in prompt and "}" in prompt

    def test_format_negative_called_uc(self, pm: PipelineManager):
        result = pm.compile("masterpiece, [bad hands]")
        adapter = NovelAIAdapter()
        neg = adapter.format_negative(result)
        assert "bad_hands" in neg

    def test_convert_json_valid(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = NovelAIAdapter()
        js = adapter.convert_json(result)
        parsed = json.loads(js)
        assert "prompt" in parsed

    def test_to_api_payload_structure(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = NovelAIAdapter()
        payload = adapter.to_api_payload(result)
        assert "input" in payload
        assert "model" in payload
        assert "parameters" in payload
        assert "negative_prompt" in payload["parameters"]

    def test_to_api_payload_defaults(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = NovelAIAdapter()
        payload = adapter.to_api_payload(result)
        assert payload["model"] == "nai-diffusion-3"
        assert payload["parameters"]["steps"] == 28
        assert payload["parameters"]["sampler"] == "k_euler_ancestral"

    def test_to_api_payload_custom_model(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = NovelAIAdapter()
        payload = adapter.to_api_payload(result, model="nai-diffusion-4")
        assert payload["model"] == "nai-diffusion-4"

    def test_to_api_payload_extra_params(self, pm: PipelineManager):
        result = pm.compile("masterpiece")
        adapter = NovelAIAdapter()
        payload = adapter.to_api_payload(result, seed=999)
        assert payload["parameters"]["seed"] == 999

    def test_repr(self):
        adapter = NovelAIAdapter()
        assert "NovelAIAdapter" in repr(adapter)


class TestBraceNotation:
    def test_weight_one_no_brace(self):
        result = _to_brace_notation("tag", 1.0)
        assert result == "tag"

    def test_weight_above_one_uses_curly(self):
        result = _to_brace_notation("tag", 1.05)
        assert result == "{tag}"

    def test_weight_below_one_uses_square(self):
        result = _to_brace_notation("tag", 0.95)
        assert result == "[tag]"

    def test_weight_double_nested_curly(self):
        result = _to_brace_notation("tag", 1.1025)  # 1.05^2
        assert result == "{{tag}}"

    def test_weight_double_nested_square(self):
        result = _to_brace_notation("tag", 0.9025)  # 0.95^2
        assert result == "[[tag]]"

    def test_extreme_high_weight_capped_at_five(self):
        result = _to_brace_notation("tag", 3.0)
        assert result.count("{") <= 5

    def test_extreme_low_weight_capped_at_five(self):
        result = _to_brace_notation("tag", 0.1)
        assert result.count("[") <= 5
