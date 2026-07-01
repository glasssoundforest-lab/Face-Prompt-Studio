"""
fps-tools/tests/unit/test_m6_japanese.py

M6-2 日本語入力対応 テスト (20件)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

JAPANESE_DICT = ROOT / "fps-data" / "dictionaries" / "system" / "synonyms" / "japanese_tags.json"


class TestJapaneseTagsFile:
    """辞書ファイル構造テスト (5件)"""

    def test_file_exists(self):
        assert JAPANESE_DICT.exists()

    def test_file_is_valid_json(self):
        data = json.loads(JAPANESE_DICT.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_has_entries(self):
        data = json.loads(JAPANESE_DICT.read_text(encoding="utf-8"))
        assert len(data.get("entries", [])) >= 500

    def test_entry_schema(self):
        data = json.loads(JAPANESE_DICT.read_text(encoding="utf-8"))
        for entry in data["entries"][:5]:
            assert "key" in entry
            assert "resolved" in entry
            assert "aliases" in entry

    def test_japanese_keys_present(self):
        data = json.loads(JAPANESE_DICT.read_text(encoding="utf-8"))
        keys = [e["key"] for e in data["entries"]]
        # 日本語文字が含まれていること
        assert any(any("\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff" for c in k) for k in keys)


class TestJapaneseTagsContent:
    """主要マッピング検証 (10件)"""

    def setup_method(self):
        data = json.loads(JAPANESE_DICT.read_text(encoding="utf-8"))
        self.entries = {e["key"]: e for e in data["entries"]}

    def test_aoi_me_maps_eyes_blue(self):
        assert "青い目" in self.entries
        assert self.entries["青い目"]["resolved"] == "Eyes.Blue"

    def test_kinpatsu_maps_hair_blonde(self):
        assert "金髪" in self.entries
        assert self.entries["金髪"]["resolved"] == "Hair.Blonde"

    def test_egao_maps_expression_smile(self):
        assert "笑顔" in self.entries
        assert self.entries["笑顔"]["resolved"] == "Expression.Smile"

    def test_shiroi_hada_maps_skin_fair(self):
        assert "白い肌" in self.entries
        assert self.entries["白い肌"]["resolved"] == "Skin.Fair"

    def test_tamago_gata_maps_face_oval(self):
        assert "卵型の顔" in self.entries
        assert self.entries["卵型の顔"]["resolved"] == "FaceShape.Oval"

    def test_ponytail_maps_hair_ponytail(self):
        assert "ポニーテール" in self.entries
        assert self.entries["ポニーテール"]["resolved"] == "Hair.Ponytail"

    def test_neko_mimi_maps_fantasy_cat_ears(self):
        assert "猫耳" in self.entries
        assert self.entries["猫耳"]["resolved"] == "Fantasy.CatEars"

    def test_kouhinshitsu_maps_quality_high(self):
        assert "高品質" in self.entries
        assert self.entries["高品質"]["resolved"] == "Quality.High"

    def test_aliases_are_list(self):
        for entry in self.entries.values():
            assert isinstance(entry["aliases"], list)

    def test_weights_are_floats(self):
        for entry in self.entries.values():
            assert isinstance(entry.get("weight", 1.0), float)


class TestJapaneseTagsInDictionaryManager:
    """DictionaryManager ロード統合テスト (5件)"""

    @pytest.fixture(autouse=True)
    def load_dm(self):
        from dictionary.manager import DictionaryManager
        self.dm = DictionaryManager(
            system_dir=ROOT / "fps-data" / "dictionaries" / "system",
        )
        self.dm.load()

    def test_dm_loads_without_error(self):
        assert self.dm is not None

    def test_japanese_key_lookup_aoi_me(self):
        result = self.dm.lookup("青い目")
        assert result.found
        assert result.resolved == "Eyes.Blue"

    def test_japanese_key_lookup_kinpatsu(self):
        result = self.dm.lookup("金髪")
        assert result.found

    def test_japanese_key_lookup_egao(self):
        result = self.dm.lookup("笑顔")
        assert result.found
        assert result.resolved == "Expression.Smile"

    def test_japanese_alias_lookup(self):
        # 「青目」は「青い目」の alias
        result = self.dm.lookup("青目")
        assert result.found
        assert result.resolved == "Eyes.Blue"
