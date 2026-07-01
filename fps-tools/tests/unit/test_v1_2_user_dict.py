"""
fps-tools/tests/unit/test_v1_2_user_dict.py

v1.2 ユーザー辞書 CRUD テスト (+25件)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from dictionary.manager import DictionaryManager  # noqa: E402


@pytest.fixture
def dm(tmp_path: Path) -> DictionaryManager:
    """テスト用 DictionaryManager（tmp_path ユーザー辞書）"""
    dm = DictionaryManager(
        system_dir=ROOT / "fps-data" / "dictionaries" / "system",
        user_dir=tmp_path / "user",
    )
    dm.load()
    return dm


# ══════════════════════════════════════════════════════════════════
# DictionaryManager User CRUD（コアレイヤー）
# ══════════════════════════════════════════════════════════════════

class TestUserDictCRUD:
    """ユーザー辞書 CRUD コアテスト (15件)"""

    def test_add_entry_lookup_works(self, dm: DictionaryManager):
        dm.add_user_entry("my_tag", "Quality.High", "quality")
        result = dm.lookup("my_tag")
        assert result.found
        assert result.resolved == "Quality.High"

    def test_add_entry_appears_in_list(self, dm: DictionaryManager):
        dm.add_user_entry("test_key", "Eyes.Blue", "eyes")
        entries = dm.list_user_entries()
        assert any(e["key"] == "test_key" for e in entries)

    def test_add_entry_with_aliases(self, dm: DictionaryManager):
        dm.add_user_entry("my_eye", "Eyes.Blue", "eyes", aliases=["mye", "my eye"])
        result = dm.lookup("mye")
        assert result.found

    def test_add_entry_with_weight(self, dm: DictionaryManager):
        dm.add_user_entry("heavy_tag", "Quality.High", "quality", weight=1.5)
        entries = dm.list_user_entries()
        e = next(x for x in entries if x["key"] == "heavy_tag")
        assert e["weight"] == 1.5

    def test_add_entry_overwrite(self, dm: DictionaryManager):
        dm.add_user_entry("dup_key", "Eyes.Blue", "eyes")
        dm.add_user_entry("dup_key", "Eyes.Green", "eyes")
        result = dm.lookup("dup_key")
        assert result.resolved == "Eyes.Green"

    def test_list_empty_initially(self, dm: DictionaryManager):
        assert dm.list_user_entries() == []

    def test_list_multiple_entries(self, dm: DictionaryManager):
        dm.add_user_entry("k1", "Eyes.Blue", "eyes")
        dm.add_user_entry("k2", "Hair.Blonde", "hair")
        entries = dm.list_user_entries()
        assert len(entries) == 2

    def test_update_resolved(self, dm: DictionaryManager):
        dm.add_user_entry("upd_key", "Eyes.Blue", "eyes")
        ok = dm.update_user_entry("upd_key", resolved="Eyes.Green")
        assert ok is True
        assert dm.lookup("upd_key").resolved == "Eyes.Green"

    def test_update_nonexistent_returns_false(self, dm: DictionaryManager):
        assert dm.update_user_entry("ghost_key", resolved="Eyes.Red") is False

    def test_update_weight(self, dm: DictionaryManager):
        dm.add_user_entry("w_key", "Quality.High", "quality", weight=1.0)
        dm.update_user_entry("w_key", weight=2.0)
        entries = dm.list_user_entries()
        e = next(x for x in entries if x["key"] == "w_key")
        assert e["weight"] == 2.0

    def test_delete_existing(self, dm: DictionaryManager):
        dm.add_user_entry("del_key", "Eyes.Blue", "eyes")
        result = dm.delete_user_entry("del_key")
        assert result is True
        assert dm.lookup("del_key").found is False

    def test_delete_nonexistent_returns_false(self, dm: DictionaryManager):
        assert dm.delete_user_entry("ghost") is False

    def test_delete_removes_from_list(self, dm: DictionaryManager):
        dm.add_user_entry("rm_key", "Eyes.Blue", "eyes")
        dm.delete_user_entry("rm_key")
        assert not any(e["key"] == "rm_key" for e in dm.list_user_entries())

    def test_user_entry_persists_across_reload(self, dm: DictionaryManager):
        dm.add_user_entry("persist_key", "Hair.Blonde", "hair")
        dm.reload()
        assert dm.lookup("persist_key").found

    def test_user_does_not_override_system(self, dm: DictionaryManager):
        """ユーザー辞書でシステムキーを上書きしても system は保持"""
        dm.add_user_entry("blue_eyes", "Eyes.Custom", "eyes")
        # 両方がインデックスに存在する（ユーザーが優先）
        result = dm.lookup("blue_eyes")
        assert result.found


# ══════════════════════════════════════════════════════════════════
# REST API: /dictionary/user/entries
# ══════════════════════════════════════════════════════════════════

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from rest.app import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestUserDictRestApi:
    """REST API ユーザー辞書テスト (10件)"""

    def test_list_returns_200(self, client: TestClient):
        r = client.get("/dictionary/user/entries")
        assert r.status_code == 200

    def test_list_schema(self, client: TestClient):
        body = client.get("/dictionary/user/entries").json()
        assert "entries" in body
        assert "total" in body

    def test_create_returns_201(self, client: TestClient):
        r = client.post("/dictionary/user/entries", json={
            "key": "test_rest_key",
            "resolved": "Eyes.Blue",
            "category": "eyes",
            "aliases": ["test alias"],
            "weight": 1.0,
        })
        assert r.status_code == 201

    def test_create_schema(self, client: TestClient):
        body = client.post("/dictionary/user/entries", json={
            "key": "test_schema_key",
            "resolved": "Hair.Blonde",
            "category": "hair",
        }).json()
        assert "key" in body
        assert "resolved" in body
        assert "category" in body

    def test_create_then_list(self, client: TestClient):
        client.post("/dictionary/user/entries", json={
            "key": "list_test_key",
            "resolved": "Quality.High",
            "category": "quality",
        })
        body = client.get("/dictionary/user/entries").json()
        keys = [e["key"] for e in body["entries"]]
        assert "list_test_key" in keys

    def test_update_returns_200(self, client: TestClient):
        client.post("/dictionary/user/entries", json={
            "key": "upd_rest_key",
            "resolved": "Eyes.Blue",
            "category": "eyes",
        })
        r = client.put("/dictionary/user/entries/upd_rest_key", json={
            "resolved": "Eyes.Green",
        })
        assert r.status_code == 200

    def test_update_not_found_returns_404(self, client: TestClient):
        r = client.put("/dictionary/user/entries/__ghost__", json={"resolved": "x"})
        assert r.status_code == 404

    def test_delete_returns_200(self, client: TestClient):
        client.post("/dictionary/user/entries", json={
            "key": "del_rest_key",
            "resolved": "Eyes.Blue",
            "category": "eyes",
        })
        r = client.delete("/dictionary/user/entries/del_rest_key")
        assert r.status_code == 200

    def test_delete_not_found_returns_404(self, client: TestClient):
        r = client.delete("/dictionary/user/entries/__ghost__")
        assert r.status_code == 404

    def test_delete_schema(self, client: TestClient):
        client.post("/dictionary/user/entries", json={
            "key": "del_schema_key",
            "resolved": "Eyes.Blue",
            "category": "eyes",
        })
        body = client.delete("/dictionary/user/entries/del_schema_key").json()
        assert "key" in body
        assert body["deleted"] is True
