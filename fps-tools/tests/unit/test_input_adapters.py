"""
fps-tools/tests/unit/test_input_adapters.py

Input Model Adapters のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_input_adapters.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from input.base_input_adapter import BaseInputAdapter
from input.florence2_adapter import Florence2Adapter
from input.joycaption_adapter import JoyCaptionAdapter
from input.wd14_adapter import WD14Adapter


# ══════════════════════════════════════════════════════════════════
# BaseInputAdapter
# ══════════════════════════════════════════════════════════════════

class TestBaseInputAdapter:
    def test_normalize_tag_lowercase(self):
        adapter = WD14Adapter()
        assert adapter.normalize_tag("Blue Eyes") == "blue_eyes"

    def test_normalize_tag_hyphen(self):
        adapter = WD14Adapter()
        assert adapter.normalize_tag("blue-eyes") == "blue_eyes"

    def test_remove_stopwords(self):
        adapter = WD14Adapter()
        result = adapter.remove_stopwords(["the", "blue_eyes", "a", "smile"])
        assert "the" not in result
        assert "blue_eyes" in result

    def test_deduplicate_preserves_order(self):
        adapter = WD14Adapter()
        result = adapter.deduplicate(["a", "b", "a", "c", "b"])
        assert result == ["a", "b", "c"]

    def test_deduplicate_case_insensitive(self):
        adapter = WD14Adapter()
        result = adapter.deduplicate(["Tag", "tag", "TAG"])
        assert len(result) == 1

    def test_repr(self):
        adapter = WD14Adapter(min_confidence=0.5)
        assert "WD14Adapter" in repr(adapter)
        assert "0.5" in repr(adapter)

    def test_cannot_instantiate_base_directly(self):
        with pytest.raises(TypeError):
            BaseInputAdapter()  # type: ignore[abstract]


# ══════════════════════════════════════════════════════════════════
# WD14Adapter
# ══════════════════════════════════════════════════════════════════

class TestWD14Adapter:
    def test_simple_comma_separated(self):
        adapter = WD14Adapter()
        result = adapter.preprocess("1girl, blue_eyes, smile")
        assert "1girl" in result
        assert "blue_eyes" in result

    def test_confidence_filtering(self):
        adapter = WD14Adapter(min_confidence=0.5)
        result = adapter.preprocess("blue_eyes:0.9, low_tag:0.1")
        assert "blue_eyes" in result
        assert "low_tag" not in result

    def test_confidence_boundary_inclusive(self):
        adapter = WD14Adapter(min_confidence=0.5)
        result = adapter.preprocess("exact:0.5")
        assert "exact" in result

    def test_rating_tags_excluded_by_default(self):
        adapter = WD14Adapter()
        result = adapter.preprocess("1girl:0.9, rating_safe:0.99, general:0.9")
        assert "rating_safe" not in result
        assert "general" not in result

    def test_rating_tags_included_when_disabled(self):
        adapter = WD14Adapter(exclude_rating_tags=False)
        result = adapter.preprocess("rating_safe:0.99")
        assert "rating_safe" in result

    def test_newline_separated(self):
        adapter = WD14Adapter()
        result = adapter.preprocess("1girl\nblue_eyes\nsmile")
        tags = [t.strip() for t in result.split(",")]
        assert "1girl" in tags
        assert "blue_eyes" in tags

    def test_empty_input(self):
        adapter = WD14Adapter()
        assert adapter.preprocess("") == ""

    def test_whitespace_only_input(self):
        adapter = WD14Adapter()
        assert adapter.preprocess("   ") == ""

    def test_no_confidence_tags_pass_through(self):
        adapter = WD14Adapter()
        result = adapter.preprocess("masterpiece, blue_eyes")
        assert "masterpiece" in result
        assert "blue_eyes" in result

    def test_normalizes_spaces_to_underscore(self):
        adapter = WD14Adapter()
        result = adapter.preprocess("blue eyes:0.9")
        assert "blue_eyes" in result

    def test_deduplication(self):
        adapter = WD14Adapter()
        result = adapter.preprocess("1girl:0.9, 1girl:0.8")
        tags = result.split(", ")
        assert tags.count("1girl") == 1

    def test_invalid_confidence_treated_as_no_confidence(self):
        adapter = WD14Adapter()
        result = adapter.preprocess("weird:tag:format")
        # コロンが複数あっても処理が落ちないこと
        assert isinstance(result, str)

    def test_model_name(self):
        assert WD14Adapter.model_name == "wd14"


# ══════════════════════════════════════════════════════════════════
# JoyCaptionAdapter
# ══════════════════════════════════════════════════════════════════

class TestJoyCaptionAdapter:
    def test_extracts_eye_color_phrase(self):
        adapter = JoyCaptionAdapter()
        result = adapter.preprocess("She has bright blue eyes.")
        assert "bright_blue_eyes" in result or "blue_eyes" in result

    def test_extracts_hair_phrase(self):
        adapter = JoyCaptionAdapter()
        result = adapter.preprocess(
            "A young woman with bright blue eyes and long flowing blonde hair, "
            "wearing a soft smile."
        )
        assert "long_flowing_blonde_hair" in result

    def test_extracts_smile_without_filler(self):
        adapter = JoyCaptionAdapter()
        result = adapter.preprocess(
            "A young woman with bright blue eyes, wearing a soft smile."
        )
        assert "soft_smile" in result
        assert "young_woman" not in result

    def test_multiple_sentences(self):
        adapter = JoyCaptionAdapter()
        result = adapter.preprocess(
            "She has fair skin. She has delicate features."
        )
        assert "fair_skin" in result
        assert "delicate_features" in result

    def test_empty_input(self):
        adapter = JoyCaptionAdapter()
        assert adapter.preprocess("") == ""

    def test_filler_words_excluded(self):
        adapter = JoyCaptionAdapter()
        result = adapter.preprocess("A young woman appears in the background.")
        assert "young_woman" not in result

    def test_long_phrase_excluded(self):
        """6語以上の長すぎるフレーズはタグとして不適切なので除外される"""
        adapter = JoyCaptionAdapter()
        result = adapter.preprocess(
            "This is a very long descriptive phrase that should not become a tag."
        )
        # 極端に長いフレーズはタグ化されない
        for tag in result.split(", "):
            assert tag.count("_") <= 4  # 5語以下 = アンダースコア4個以下

    def test_model_name(self):
        assert JoyCaptionAdapter.model_name == "joycaption"

    def test_deduplication(self):
        adapter = JoyCaptionAdapter()
        result = adapter.preprocess("blue eyes. blue eyes.")
        tags = result.split(", ")
        assert len(tags) == len(set(t.lower() for t in tags))


# ══════════════════════════════════════════════════════════════════
# Florence2Adapter
# ══════════════════════════════════════════════════════════════════

class TestFlorence2Adapter:
    def test_removes_task_token(self):
        adapter = Florence2Adapter()
        result = adapter.preprocess(
            "<MORE_DETAILED_CAPTION>A woman with blue eyes."
        )
        assert "<MORE_DETAILED_CAPTION>" not in result

    def test_extracts_tags_after_token_removal(self):
        adapter = Florence2Adapter()
        result = adapter.preprocess(
            "<MORE_DETAILED_CAPTION>A woman with captivating blue eyes "
            "and cascading hair."
        )
        assert "captivating_blue_eyes" in result
        assert "cascading_hair" in result

    def test_no_task_token_still_works(self):
        adapter = Florence2Adapter()
        result = adapter.preprocess("A woman with blue eyes.")
        assert "blue_eyes" in result

    def test_multiple_task_tokens(self):
        adapter = Florence2Adapter()
        result = adapter.preprocess(
            "<DETAILED_CAPTION><MORE_DETAILED_CAPTION>A woman with blue eyes."
        )
        assert "<" not in result

    def test_empty_input(self):
        adapter = Florence2Adapter()
        assert adapter.preprocess("") == ""

    def test_model_name(self):
        assert Florence2Adapter.model_name == "florence2"

    def test_inherits_joycaption_logic(self):
        assert issubclass(Florence2Adapter, JoyCaptionAdapter)


# ══════════════════════════════════════════════════════════════════
# Pipeline 統合
# ══════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    def test_wd14_to_pipeline(self):
        from dictionary.manager import DictionaryManager
        from pipeline.manager import PipelineManager

        dm = DictionaryManager(
            system_dir=ROOT / "fps-data" / "dictionaries" / "system",
            user_dir=ROOT / "fps-data" / "dictionaries" / "user",
        )
        dm.load()
        pm = PipelineManager()
        pm.set_context(dictionary_manager=dm)

        adapter = WD14Adapter(min_confidence=0.35)
        dsl = adapter.preprocess("1girl:0.998, blue_eyes:0.95, smile:0.42")
        result = pm.compile(dsl)

        assert result.success is True
        assert result.tag_count >= 2

    def test_joycaption_to_pipeline(self):
        from dictionary.manager import DictionaryManager
        from pipeline.manager import PipelineManager

        dm = DictionaryManager(
            system_dir=ROOT / "fps-data" / "dictionaries" / "system",
            user_dir=ROOT / "fps-data" / "dictionaries" / "user",
        )
        dm.load()
        pm = PipelineManager()
        pm.set_context(dictionary_manager=dm)

        adapter = JoyCaptionAdapter()
        dsl = adapter.preprocess(
            "A young woman with bright blue eyes and long flowing blonde hair."
        )
        result = pm.compile(dsl)
        assert result.success is True

    def test_florence2_to_pipeline(self):
        from dictionary.manager import DictionaryManager
        from pipeline.manager import PipelineManager

        dm = DictionaryManager(
            system_dir=ROOT / "fps-data" / "dictionaries" / "system",
            user_dir=ROOT / "fps-data" / "dictionaries" / "user",
        )
        dm.load()
        pm = PipelineManager()
        pm.set_context(dictionary_manager=dm)

        adapter = Florence2Adapter()
        dsl = adapter.preprocess(
            "<MORE_DETAILED_CAPTION>A woman with captivating blue eyes."
        )
        result = pm.compile(dsl)
        assert result.success is True
        # 同義語辞書に captivating_blue_eyes が登録済みなら解決される
        assert any(t.meta.get("resolved") == "Eyes.Blue" for t in result.tags)
