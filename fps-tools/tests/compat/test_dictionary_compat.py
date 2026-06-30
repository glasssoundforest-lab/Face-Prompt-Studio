"""
fps-tools/tests/compat/test_dictionary_compat.py

辞書システムの互換性テスト。
全 fps-data 辞書ファイルがロード可能で、構造的整合性を持つことを検証する。

pytest で実行: pytest fps-tools/tests/compat/test_dictionary_compat.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from dictionary.loader import load_dict_dir, load_dict_file
from dictionary.manager import DictionaryManager
from dictionary.models import DictSource
from dictionary.validator import validate_dict_file

SYSTEM_DIR = ROOT / "fps-data" / "dictionaries" / "system"
USER_DIR   = ROOT / "fps-data" / "dictionaries" / "user"


# ══════════════════════════════════════════════════════════════════
# 全辞書ファイルの構造検証
# ══════════════════════════════════════════════════════════════════

class TestAllDictionaryFilesValid:
    """fps-data 配下の全 .json 辞書ファイルが個別に妥当であることを確認する"""

    def _all_dict_files(self) -> list[Path]:
        return sorted(SYSTEM_DIR.rglob("*.json"))

    def test_at_least_one_file_exists(self):
        files = self._all_dict_files()
        assert len(files) >= 15, "辞書ファイル数が想定を下回っています"

    def test_every_file_is_valid_json(self):
        for f in self._all_dict_files():
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                pytest.fail(f"{f.relative_to(ROOT)}: JSON パースエラー: {e}")

    def test_every_file_loads_without_error(self):
        for f in self._all_dict_files():
            try:
                load_dict_file(f, DictSource.SYSTEM)
            except Exception as e:
                pytest.fail(f"{f.relative_to(ROOT)}: 読み込みエラー: {e}")

    def test_every_file_passes_validation(self):
        errors_by_file: dict[str, list[str]] = {}
        for f in self._all_dict_files():
            df = load_dict_file(f, DictSource.SYSTEM)
            try:
                validate_dict_file(df)
            except Exception as e:
                errors_by_file[str(f.relative_to(ROOT))] = [str(e)]

        assert not errors_by_file, f"バリデーションエラー:\n{errors_by_file}"

    def test_every_file_has_required_fields(self):
        for f in self._all_dict_files():
            data = json.loads(f.read_text(encoding="utf-8"))
            assert "version" in data, f"{f.name}: 'version' フィールドが必要"
            assert "entries" in data, f"{f.name}: 'entries' フィールドが必要"
            assert isinstance(data["entries"], list), f"{f.name}: 'entries' はリストである必要"


# ══════════════════════════════════════════════════════════════════
# グローバル一意性検証（ファイル横断）
# ══════════════════════════════════════════════════════════════════

class TestGlobalUniqueness:
    """ファイルをまたいだキー・エイリアスの重複がないことを確認する
    （DictionaryManager のマージ仕様上、後優先で上書きされるため
     エラーにはならないが、意図しない上書きを検出する）"""

    def _normalize(self, s: str) -> str:
        return s.strip().lower().replace(" ", "_").replace("-", "_")

    def test_no_unintended_cross_file_key_collision(self):
        """
        正規化キーがファイルをまたいで衝突する場合、resolved 値が
        一致しているか（同義語としての意図的重複か）を確認する。
        resolved が食い違う場合のみ「想定外の衝突」として報告する。
        """
        seen: dict[str, tuple[str, str]] = {}  # key -> (filename, resolved)
        conflicts: list[str] = []

        files = sorted(SYSTEM_DIR.rglob("*.json"))
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            for entry in data.get("entries", []):
                k = self._normalize(entry["key"])
                resolved = entry.get("resolved", "")
                if k in seen:
                    prev_file, prev_resolved = seen[k]
                    if prev_file != f.name and prev_resolved != resolved:
                        conflicts.append(
                            f"key '{k}': {prev_file}({prev_resolved}) "
                            f"vs {f.name}({resolved})"
                        )
                else:
                    seen[k] = (f.name, resolved)

        # whitelist の wl_ プレフィックスは設計上の除外対象
        unexpected = [c for c in conflicts if not c.startswith("key 'wl_")]
        assert not unexpected, f"resolved 値が食い違う想定外の衝突:\n{unexpected}"

    def test_dictionary_manager_loads_full_set_without_exception(self):
        """全辞書を読み込んで例外が出ないこと（DictionaryManager 経由）"""
        dm = DictionaryManager(system_dir=SYSTEM_DIR, user_dir=USER_DIR)
        dm.load()  # 例外が出なければ OK
        assert dm.statistics()["total_keys"] > 0


# ══════════════════════════════════════════════════════════════════
# resolved 値のフォーマット一貫性
# ══════════════════════════════════════════════════════════════════

class TestResolvedFormatConsistency:
    """resolved 値が 'Category.Value' 形式で一貫していることを確認する"""

    def _all_entries(self) -> list[dict]:
        entries = []
        for f in sorted(SYSTEM_DIR.rglob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            entries.extend(data.get("entries", []))
        return entries

    def test_all_resolved_have_dot_notation(self):
        bad = [
            e["key"] for e in self._all_entries()
            if "." not in e.get("resolved", "")
        ]
        assert not bad, f"ドット記法でない resolved 値: {bad}"

    def test_all_resolved_start_uppercase(self):
        bad = [
            e["key"] for e in self._all_entries()
            if not e.get("resolved", "")[:1].isupper()
        ]
        assert not bad, f"resolved が大文字始まりでないエントリ: {bad}"

    def test_all_weights_in_valid_range(self):
        bad = [
            (e["key"], e.get("weight", 1.0))
            for e in self._all_entries()
            if not (0.0 < e.get("weight", 1.0) <= 3.0)
        ]
        assert not bad, f"weight が範囲外のエントリ: {bad}"


# ══════════════════════════════════════════════════════════════════
# カテゴリ網羅性（v0.1.0-dev 仕様との対比）
# ══════════════════════════════════════════════════════════════════

class TestFaceCategoryCompleteness:
    """v0.1.0-dev スナップショットで定義された顔特化カテゴリが
    全て辞書として存在することを確認する"""

    REQUIRED_KEEP_CATEGORIES = [
        "hair", "eyes", "eyebrows", "eyelashes", "face_shape",
        "nose", "mouth", "teeth", "skin", "expression",
        "accessories", "glasses", "piercing", "makeup", "fantasy_parts",
    ]

    @classmethod
    @pytest.fixture(scope="class")
    def dm(cls) -> DictionaryManager:
        manager = DictionaryManager(system_dir=SYSTEM_DIR, user_dir=USER_DIR)
        manager.load()
        return manager

    @pytest.mark.parametrize("category", REQUIRED_KEEP_CATEGORIES)
    def test_category_exists(self, dm: DictionaryManager, category: str):
        assert category in dm.categories(), f"必須カテゴリ '{category}' が存在しません"

    @pytest.mark.parametrize("category", REQUIRED_KEEP_CATEGORIES)
    def test_category_has_entries(self, dm: DictionaryManager, category: str):
        stats = dm.statistics()
        by_cat = stats.get("by_category", {})
        assert by_cat.get(category, 0) > 0, f"カテゴリ '{category}' にエントリがありません"


# ══════════════════════════════════════════════════════════════════
# 同義語辞書の網羅性
# ══════════════════════════════════════════════════════════════════

class TestSynonymCoverage:
    SYNONYMS_DIR = SYSTEM_DIR / "synonyms"

    def test_synonyms_dir_exists(self):
        assert self.SYNONYMS_DIR.exists()

    def test_synonyms_dir_has_files(self):
        files = list(self.SYNONYMS_DIR.glob("*.json"))
        assert len(files) >= 7  # wd14/joycaption/common/florence2/qwen2vl/internvl/minicpm

    def test_synonyms_loaded_via_rglob(self):
        """サブディレクトリの辞書が load_dict_dir で正しく読み込まれること"""
        files = load_dict_dir(SYSTEM_DIR, DictSource.SYSTEM)
        synonym_files = [f for f in files if f.category == "synonyms"]
        assert len(synonym_files) >= 7

    def test_wd14_specific_tags_present(self):
        dm = DictionaryManager(system_dir=SYSTEM_DIR, user_dir=USER_DIR)
        dm.load()
        for tag in ["1girl", "tsurime", "tareme"]:
            r = dm.lookup(tag)
            assert r.found, f"WD14 固有タグ '{tag}' が見つかりません"
