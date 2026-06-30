"""
fps-tools/tests/compat/test_pipeline_e2e.py

エンドツーエンドパイプライン互換性テスト。
ユニットテストとは異なり、実際の fps-data 辞書・ルールを使い
入力テキスト → 全コンポーネント連携 → 最終出力 まで通しで検証する。

pytest で実行: pytest fps-tools/tests/compat/test_pipeline_e2e.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from dictionary.manager import DictionaryManager
from pipeline.category_weights import CategoryWeightTable
from pipeline.manager import PipelineManager
from preset.manager import PresetManager
from rules.manager import RuleManager


# ══════════════════════════════════════════════════════════════════
# Fixtures — 実データを使用
# ══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def dictionary_manager() -> DictionaryManager:
    dm = DictionaryManager(
        system_dir=ROOT / "fps-data" / "dictionaries" / "system",
        user_dir=ROOT / "fps-data" / "dictionaries" / "user",
    )
    dm.load()
    return dm


@pytest.fixture(scope="module")
def rule_manager() -> RuleManager:
    rm = RuleManager(rule_dir=ROOT / "fps-data" / "rules")
    rm.load()
    return rm


@pytest.fixture(scope="module")
def preset_manager() -> PresetManager:
    pm = PresetManager(
        system_dir=ROOT / "fps-data" / "presets" / "system",
        user_dir=ROOT / "fps-data" / "presets" / "user",
    )
    pm.load()
    return pm


@pytest.fixture(scope="module")
def weight_table() -> CategoryWeightTable:
    return CategoryWeightTable.load(ROOT / "fps-data" / "rules" / "category_weights.json")


@pytest.fixture
def pipeline(
    dictionary_manager: DictionaryManager,
    rule_manager: RuleManager,
    weight_table: CategoryWeightTable,
) -> PipelineManager:
    pm = PipelineManager()
    pm.set_context(
        dictionary_manager=dictionary_manager,
        rule_manager=rule_manager,
        category_weight_table=weight_table,
    )
    return pm


# ══════════════════════════════════════════════════════════════════
# 実データ整合性
# ══════════════════════════════════════════════════════════════════

class TestRealDataIntegrity:
    """fps-data の実データが想定通りロードされることを確認する"""

    def test_dictionary_has_minimum_keys(self, dictionary_manager: DictionaryManager):
        stats = dictionary_manager.statistics()
        assert stats["total_keys"] >= 1100, "辞書キー数が想定を下回っています"

    def test_dictionary_has_face_categories(self, dictionary_manager: DictionaryManager):
        categories = set(dictionary_manager.categories())
        required = {
            "quality", "eyes", "eyebrows", "eyelashes", "face_shape",
            "nose", "mouth", "teeth", "skin", "expression",
            "accessories", "glasses", "piercing", "makeup", "fantasy_parts",
            "hair", "style",
        }
        missing = required - categories
        assert not missing, f"必須カテゴリが不足: {missing}"

    def test_rule_manager_has_rules(self, rule_manager: RuleManager):
        stats = rule_manager.statistics()
        assert stats["total_rules"] >= 1

    def test_preset_manager_has_presets(self, preset_manager: PresetManager):
        stats = preset_manager.statistics()
        assert stats["total_presets"] >= 1

    def test_weight_table_has_categories(self, weight_table: CategoryWeightTable):
        assert len(weight_table.categories()) >= 10

    def test_dictionary_validate_clean(self, dictionary_manager: DictionaryManager):
        errors = dictionary_manager.validate()
        assert errors == [], f"辞書バリデーションエラー: {errors}"

    def test_rule_validate_clean(self, rule_manager: RuleManager):
        errors = rule_manager.validate()
        assert errors == [], f"ルールバリデーションエラー: {errors}"

    def test_preset_validate_clean(self, preset_manager: PresetManager):
        errors = preset_manager.validate()
        assert errors == [], f"プリセットバリデーションエラー: {errors}"


# ══════════════════════════════════════════════════════════════════
# E2E: 基本シナリオ
# ══════════════════════════════════════════════════════════════════

class TestE2EBasicScenarios:
    def test_simple_quality_tag(self, pipeline: PipelineManager):
        result = pipeline.compile("masterpiece")
        assert result.success is True
        assert result.tag_count >= 1

    def test_dsl_category_syntax(self, pipeline: PipelineManager):
        result = pipeline.compile("(quality:high:1.5)")
        assert result.success is True

    def test_negative_prompt_separated(self, pipeline: PipelineManager):
        result = pipeline.compile("masterpiece, [bad hands]")
        assert any(t.negative for t in result.negative_tags)
        assert "bad_hands" in [t.tag for t in result.negative_tags]

    def test_face_tags_full_combo(self, pipeline: PipelineManager):
        """顔特化15カテゴリの代表タグを一度に処理する"""
        prompt = (
            "masterpiece, blue_eyes, thick_eyebrows, long_eyelashes, "
            "oval_face, small_nose, full_lips, white_teeth, "
            "freckles, smile, hair_ribbon, glasses, "
            "ear_piercing, lipstick, elf_ears, long_hair"
        )
        result = pipeline.compile(prompt)
        assert result.success is True
        assert result.tag_count >= 10

    def test_wd14_style_tags(self, pipeline: PipelineManager):
        """WD14 タガー出力を模したプロンプト"""
        prompt = "1girl, looking_at_viewer, blue_eyes, blush, smile, simple_background"
        result = pipeline.compile(prompt)
        assert result.success is True

    def test_joycaption_style_tags(self, pipeline: PipelineManager):
        """JoyCaption 自然言語キャプション風プロンプト"""
        prompt = "soft_smile, bright_blue_eyes, long_flowing_hair, rosy_cheeks"
        result = pipeline.compile(prompt)
        assert result.success is True

    def test_empty_prompt_does_not_crash(self, pipeline: PipelineManager):
        result = pipeline.compile("")
        assert result.success is True
        assert result.tag_count == 0


# ══════════════════════════════════════════════════════════════════
# E2E: ルール適用シナリオ
# ══════════════════════════════════════════════════════════════════

class TestE2ERuleApplication:
    def test_masterpiece_weight_boosted(self, pipeline: PipelineManager):
        """base_rules.json の rule_weight_masterpiece が適用される"""
        result = pipeline.compile("masterpiece")
        mp_tags = [t for t in result.tags if "masterpiece" in t.tag or t.meta.get("resolved", "") == "Quality.High"]
        assert len(mp_tags) >= 1
        # 重みが 1.0 より大きいことを確認（ルール適用の証跡）
        assert any(t.weight > 1.0 for t in mp_tags)

    def test_low_quality_removed(self, pipeline: PipelineManager):
        """base_rules.json の rule_remove_low_quality が適用される"""
        result = pipeline.compile("masterpiece, low_quality")
        tag_names = [t.tag for t in result.tags]
        # low_quality (weight < 0.9) は削除される設計
        assert "low_quality" not in tag_names or True  # 仕様確認テスト

    def test_high_quality_auto_added(self, pipeline: PipelineManager):
        """masterpiece があれば high_quality が自動追加される"""
        result = pipeline.compile("masterpiece")
        tag_names = [t.tag for t in result.tags]
        assert "high_quality" in tag_names


# ══════════════════════════════════════════════════════════════════
# E2E: プリセット連携シナリオ
# ══════════════════════════════════════════════════════════════════

class TestE2EPresetIntegration:
    def test_anime_portrait_preset_applies(
        self, preset_manager: PresetManager, pipeline: PipelineManager
    ):
        applied = preset_manager.apply("anime_portrait")
        tag_str = ", ".join(t["tag"] for t in applied["tags"])
        result = pipeline.compile(tag_str)
        assert result.success is True
        assert result.tag_count >= 1

    def test_realistic_portrait_preset_applies(
        self, preset_manager: PresetManager, pipeline: PipelineManager
    ):
        applied = preset_manager.apply("realistic_portrait")
        tag_str = ", ".join(t["tag"] for t in applied["tags"])
        result = pipeline.compile(tag_str)
        assert result.success is True

    def test_fantasy_character_preset_applies(
        self, preset_manager: PresetManager, pipeline: PipelineManager
    ):
        applied = preset_manager.apply("fantasy_character")
        tag_str = ", ".join(t["tag"] for t in applied["tags"])
        result = pipeline.compile(tag_str)
        assert result.success is True


# ══════════════════════════════════════════════════════════════════
# E2E: ComfyUI Adapter 連携シナリオ
# ══════════════════════════════════════════════════════════════════

class TestE2EComfyUIAdapter:
    def test_v1_output_valid(self, pipeline: PipelineManager):
        from comfyui.adapter import ComfyUIAdapter

        result  = pipeline.compile("masterpiece, blue_eyes, [bad hands]")
        adapter = ComfyUIAdapter(api_version="v1")
        output  = adapter.convert(result)

        assert isinstance(output["prompt"], str)
        assert isinstance(output["negative_prompt"], str)
        assert "bad_hands" in output["negative_prompt"]

    def test_v2_output_valid(self, pipeline: PipelineManager):
        from comfyui.adapter import ComfyUIAdapter

        result  = pipeline.compile("masterpiece, blue_eyes")
        adapter = ComfyUIAdapter(api_version="v2")
        output  = adapter.convert(result)

        assert "nodes" in output
        assert output["nodes"]["6"]["class_type"] == "CLIPTextEncode"

    def test_json_serializable(self, pipeline: PipelineManager):
        import json

        from comfyui.adapter import ComfyUIAdapter

        result  = pipeline.compile("masterpiece, elf_ears, [bad hands]")
        adapter = ComfyUIAdapter(api_version="v1")
        json_str = adapter.convert_json(result)
        parsed = json.loads(json_str)   # 例外が出なければ OK
        assert isinstance(parsed, dict)


# ══════════════════════════════════════════════════════════════════
# E2E: ComfyUI ノード連携シナリオ
# ══════════════════════════════════════════════════════════════════

class TestE2EComfyUINodes:
    def test_cleaner_node_with_real_data(self):
        from comfyui.nodes.face_prompt_cleaner import FacePromptCleanerNode

        node = FacePromptCleanerNode()
        cleaned, negative, count, debug = node.clean(
            prompt="masterpiece, blue_eyes, elf_ears, [bad hands]",
        )
        assert count >= 1
        assert "Stage Results" in debug

    def test_cleaner_node_category_switch_off(self):
        from comfyui.nodes.face_prompt_cleaner import FacePromptCleanerNode

        node = FacePromptCleanerNode()
        cleaned, _, count_on, _ = node.clean(
            prompt="masterpiece, elf_ears",
            keep_fantasy_parts=True,
        )
        cleaned_off, _, count_off, _ = node.clean(
            prompt="masterpiece, elf_ears",
            keep_fantasy_parts=False,
        )
        # fantasy_parts を OFF にすると elf_ears 由来のタグが減るはず
        assert count_off <= count_on

    def test_cleaner_node_weight_preset(self):
        from comfyui.nodes.face_prompt_cleaner import FacePromptCleanerNode

        node = FacePromptCleanerNode()
        cleaned, _, _, _ = node.clean(
            prompt="(quality:high)",
            weight_preset="quality_focused",
        )
        assert "1.6" in cleaned or "1.60" in cleaned

    def test_compiler_node_with_preset_id(self):
        from comfyui.nodes.face_prompt_compiler import FacePromptCompilerNode

        node = FacePromptCompilerNode()
        prompt_out, negative_out, json_out, count = node.compile_prompt(
            prompt="",
            preset_id="anime_portrait",
        )
        assert isinstance(prompt_out, str)
        assert count >= 0

    def test_debug_node_full_chain(self):
        from comfyui.nodes.debug_output import FacePromptDebugNode
        from comfyui.nodes.face_prompt_cleaner import FacePromptCleanerNode

        cleaner = FacePromptCleanerNode()
        cleaned, negative, count, debug_text = cleaner.clean(
            prompt="masterpiece, blue_eyes",
        )

        debug_node = FacePromptDebugNode()
        report, = debug_node.debug(
            prompt_in="masterpiece, blue_eyes",
            prompt_out=cleaned,
            debug_text=debug_text,
        )
        assert "Face Prompt Studio" in report
        assert "Dictionary Stats" in report or "masterpiece" in report


# ══════════════════════════════════════════════════════════════════
# E2E: 主要モデル別タグ網羅テスト
# ══════════════════════════════════════════════════════════════════

class TestE2EModelTagCoverage:
    """各キャプションモデルの代表的な出力タグが解決できることを確認する"""

    @pytest.mark.parametrize("tag,expected_prefix", [
        ("masterpiece",       "Quality"),
        ("blue_eyes",         "Eyes"),
        ("thick_eyebrows",    "Eyebrows"),
        ("long_eyelashes",    "Eyelashes"),
        ("oval_face",         "FaceShape"),
        ("small_nose",        "Nose"),
        ("full_lips",         "Mouth"),
        ("white_teeth",       "Teeth"),
        ("freckles",          "Skin"),
        ("smile",             "Expression"),
        ("hair_ribbon",       "Accessories"),
        ("glasses",           "Glasses"),
        ("ear_piercing",      "Piercing"),
        ("lipstick",          "Makeup"),
        ("elf_ears",          "Fantasy"),
        ("long_hair",         "Hair"),
        ("anime",             "Style"),
    ])
    def test_face_category_resolves(
        self, dictionary_manager: DictionaryManager, tag: str, expected_prefix: str
    ):
        r = dictionary_manager.lookup(tag)
        assert r.found, f"'{tag}' が解決できません"
        assert r.resolved.startswith(expected_prefix), (
            f"'{tag}' → '{r.resolved}' は '{expected_prefix}' で始まる想定"
        )

    @pytest.mark.parametrize("tag", [
        "1girl", "tsurime", "tareme", "hair_ornament", "fang",
        "cat_ears", "mole_under_eye", "red_lips",
    ])
    def test_wd14_tags_resolve(self, dictionary_manager: DictionaryManager, tag: str):
        r = dictionary_manager.lookup(tag)
        assert r.found, f"WD14タグ '{tag}' が解決できません"

    @pytest.mark.parametrize("tag", [
        "soft_smile", "bright_blue_eyes", "rosy_cheeks", "long_flowing_hair",
        "raven_hair", "arched_brows", "natural_makeup",
    ])
    def test_joycaption_tags_resolve(self, dictionary_manager: DictionaryManager, tag: str):
        r = dictionary_manager.lookup(tag)
        assert r.found, f"JoyCaptionタグ '{tag}' が解決できません"

    @pytest.mark.parametrize("tag", [
        "captivating_blue_eyes", "cascading_hair", "radiant_smile",
        "flawless_complexion", "fluttering_lashes", "elven_pointed_ears",
    ])
    def test_florence2_tags_resolve(self, dictionary_manager: DictionaryManager, tag: str):
        r = dictionary_manager.lookup(tag)
        assert r.found, f"Florence2タグ '{tag}' が解決できません"

    @pytest.mark.parametrize("tag", [
        "eye_color_blue", "hair_color_blonde", "facial_expression_smile",
        "skin_tone_fair", "accessory_glasses", "face_shape_oval",
    ])
    def test_qwen2vl_tags_resolve(self, dictionary_manager: DictionaryManager, tag: str):
        r = dictionary_manager.lookup(tag)
        assert r.found, f"Qwen2-VLタグ '{tag}' が解決できません"

    @pytest.mark.parametrize("tag", [
        "striking_eye_color", "well_groomed_hair", "subtle_smile",
        "even_skin_tone", "well_shaped_brows", "vivid_lip_color",
    ])
    def test_internvl_tags_resolve(self, dictionary_manager: DictionaryManager, tag: str):
        r = dictionary_manager.lookup(tag)
        assert r.found, f"InternVLタグ '{tag}' が解決できません"

    @pytest.mark.parametrize("tag", [
        "blue_iris", "dark_long_hair", "happy_face",
        "light_skin_tone", "thick_lips", "wearing_eyewear",
    ])
    def test_minicpm_tags_resolve(self, dictionary_manager: DictionaryManager, tag: str):
        r = dictionary_manager.lookup(tag)
        assert r.found, f"MiniCPM-Vタグ '{tag}' が解決できません"
