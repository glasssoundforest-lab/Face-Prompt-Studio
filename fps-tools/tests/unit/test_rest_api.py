"""
fps-tools/tests/unit/test_rest_api.py

REST API（Gap 4 対応）のユニットテスト。
fastapi が未インストールの環境では自動的にスキップされる。

pytest で実行: pytest fps-tools/tests/unit/test_rest_api.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from rest.app import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health_status_ok(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_contains_dictionary_keys(self, client: TestClient):
        r = client.get("/health")
        body = r.json()
        assert body["dictionary_keys"] > 1000

    def test_health_contains_rule_count(self, client: TestClient):
        r = client.get("/health")
        body = r.json()
        assert body["rule_count"] >= 1


class TestCompile:
    def test_compile_basic(self, client: TestClient):
        r = client.post("/compile", params={"prompt": "masterpiece, blue_eyes"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["tag_count"] >= 1

    def test_compile_empty_prompt(self, client: TestClient):
        r = client.post("/compile", params={"prompt": ""})
        assert r.status_code == 200
        assert r.json()["tag_count"] == 0

    def test_compile_with_comfyui_adapter(self, client: TestClient):
        r = client.post("/compile", params={"prompt": "masterpiece", "adapter": "comfyui"})
        body = r.json()
        assert body["adapter_output"] is not None
        assert "prompt" in body["adapter_output"]

    def test_compile_with_a1111_adapter(self, client: TestClient):
        r = client.post("/compile", params={"prompt": "masterpiece", "adapter": "a1111"})
        body = r.json()
        assert body["adapter_output"] is not None

    def test_compile_with_novelai_adapter(self, client: TestClient):
        r = client.post("/compile", params={"prompt": "masterpiece", "adapter": "novelai"})
        body = r.json()
        assert body["adapter_output"] is not None

    def test_compile_without_adapter_returns_none(self, client: TestClient):
        r = client.post("/compile", params={"prompt": "masterpiece"})
        body = r.json()
        assert body["adapter_output"] is None

    def test_compile_dsl_syntax(self, client: TestClient):
        r = client.post("/compile", params={"prompt": "(quality:high:1.5)"})
        body = r.json()
        assert body["success"] is True


class TestOptimize:
    def test_optimize_returns_score(self, client: TestClient):
        r = client.post("/optimize", params={"prompt": "masterpiece"})
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["score"]["overall_score"] <= 100

    def test_optimize_detects_conflict(self, client: TestClient):
        r = client.post("/optimize", params={"prompt": "blue_eyes, brown_eyes"})
        body = r.json()
        assert len(body["issues"]) >= 1
        assert any(i["type"] == "conflict" for i in body["issues"])

    def test_optimize_has_recommendations(self, client: TestClient):
        r = client.post("/optimize", params={"prompt": "masterpiece"})
        body = r.json()
        assert len(body["recommendations"]) > 0


class TestDictionary:
    def test_search_found(self, client: TestClient):
        r = client.get("/dictionary/search", params={"query": "blue_eyes"})
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is True
        assert body["resolved"] == "Eyes.Blue"

    def test_search_not_found(self, client: TestClient):
        r = client.get("/dictionary/search", params={"query": "nonexistent_xyz_999"})
        body = r.json()
        assert body["found"] is False

    def test_search_missing_query_param(self, client: TestClient):
        r = client.get("/dictionary/search")
        assert r.status_code == 422

    def test_stats(self, client: TestClient):
        r = client.get("/dictionary/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["total_keys"] > 1000
        assert "by_category" in body


class TestPresets:
    def test_list_presets(self, client: TestClient):
        r = client.get("/presets")
        assert r.status_code == 200
        body = r.json()
        assert len(body["presets"]) >= 3

    def test_apply_existing_preset(self, client: TestClient):
        r = client.post("/presets/anime_portrait/apply")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["tag_count"] > 0

    def test_apply_nonexistent_preset(self, client: TestClient):
        r = client.post("/presets/nonexistent_preset_xyz/apply")
        assert r.status_code == 404


class TestHistory:
    def test_list_history_empty_or_more(self, client: TestClient):
        r = client.get("/history")
        assert r.status_code == 200
        body = r.json()
        assert "entries" in body
        assert "total" in body

    def test_list_history_with_limit(self, client: TestClient):
        r = client.get("/history", params={"limit": 5})
        assert r.status_code == 200

    def test_list_history_invalid_limit_rejected(self, client: TestClient):
        r = client.get("/history", params={"limit": 0})
        assert r.status_code == 422


class TestValidate:
    def test_validate_success(self, client: TestClient):
        r = client.post("/validate")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["errors"] == {}


class TestWebUI:
    def test_root_serves_html(self, client: TestClient):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_root_contains_fps_title(self, client: TestClient):
        r = client.get("/")
        assert "FPS" in r.text

    def test_static_index_accessible(self, client: TestClient):
        r = client.get("/static/index.html")
        assert r.status_code == 200


class TestResponseSchemas:
    def test_compile_response_has_all_fields(self, client: TestClient):
        r = client.post("/compile", params={"prompt": "masterpiece"})
        body = r.json()
        for field in ("success", "prompt", "negative", "tag_count", "errors"):
            assert field in body

    def test_health_response_has_all_fields(self, client: TestClient):
        r = client.get("/health")
        body = r.json()
        for field in ("status", "version", "dictionary_keys", "rule_count"):
            assert field in body

    def test_optimize_response_score_has_all_fields(self, client: TestClient):
        r = client.post("/optimize", params={"prompt": "masterpiece"})
        score = r.json()["score"]
        for field in ("overall_score", "coverage_score", "balance_score", "redundancy_score"):
            assert field in score


# ─────────────────────────────────────────────────────────────
# M5-3 Knowledge Browser エンドポイントテスト (+20件)
# ─────────────────────────────────────────────────────────────


class TestDictionaryCategories:
    """GET /dictionary/categories (5件)"""

    def test_categories_status_200(self, client: TestClient):
        r = client.get("/dictionary/categories")
        assert r.status_code == 200

    def test_categories_schema(self, client: TestClient):
        body = client.get("/dictionary/categories").json()
        assert "categories" in body
        assert "total" in body
        assert isinstance(body["categories"], list)

    def test_categories_count_matches_total(self, client: TestClient):
        body = client.get("/dictionary/categories").json()
        assert len(body["categories"]) == body["total"]

    def test_categories_sorted(self, client: TestClient):
        cats = client.get("/dictionary/categories").json()["categories"]
        assert cats == sorted(cats)

    def test_categories_nonempty(self, client: TestClient):
        total = client.get("/dictionary/categories").json()["total"]
        assert total > 0


class TestDictionaryEntries:
    """GET /dictionary/entries (10件)"""

    def test_entries_status_200(self, client: TestClient):
        r = client.get("/dictionary/entries")
        assert r.status_code == 200

    def test_entries_schema(self, client: TestClient):
        body = client.get("/dictionary/entries").json()
        assert "entries" in body
        assert "total" in body

    def test_entries_item_fields(self, client: TestClient):
        entries = client.get("/dictionary/entries?limit=1").json()["entries"]
        if entries:
            e = entries[0]
            for f in ("key", "resolved", "weight", "category", "synonyms"):
                assert f in e

    def test_entries_category_filter(self, client: TestClient):
        cats = client.get("/dictionary/categories").json()["categories"]
        if not cats:
            return
        cat = cats[0]
        entries = client.get(f"/dictionary/entries?category={cat}").json()["entries"]
        for e in entries:
            assert e["category"] == cat

    def test_entries_search_filter(self, client: TestClient):
        entries = client.get("/dictionary/entries?search=eyes").json()["entries"]
        for e in entries:
            assert "eyes" in e["key"] or "eyes" in e["resolved"].lower()

    def test_entries_limit_respected(self, client: TestClient):
        entries = client.get("/dictionary/entries?limit=5").json()["entries"]
        assert len(entries) <= 5

    def test_entries_limit_max_500(self, client: TestClient):
        # limit=9999 は le=500 バリデーションで 422
        assert client.get("/dictionary/entries?limit=9999").status_code == 422
        # limit=500 は正常動作
        r = client.get("/dictionary/entries?limit=500")
        assert r.status_code == 200
        assert len(r.json()["entries"]) <= 500

    def test_entries_category_and_search_combined(self, client: TestClient):
        cats = client.get("/dictionary/categories").json()["categories"]
        if not cats:
            return
        body = client.get(f"/dictionary/entries?category={cats[0]}&search=a").json()
        assert "entries" in body

    def test_entries_unknown_category_returns_empty(self, client: TestClient):
        body = client.get("/dictionary/entries?category=__no_such_cat__").json()
        assert body["entries"] == []
        assert body["total"] == 0

    def test_entries_response_has_category_field(self, client: TestClient):
        body = client.get("/dictionary/entries?category=eyes").json()
        assert body["category"] == "eyes"


class TestDictionarySynonyms:
    """GET /dictionary/synonyms (5件)"""

    def _first_key(self, client: TestClient) -> str:
        entries = client.get("/dictionary/entries?limit=1").json()["entries"]
        return entries[0]["key"] if entries else "blue_eyes"

    def test_synonyms_status_200(self, client: TestClient):
        key = self._first_key(client)
        assert client.get(f"/dictionary/synonyms?key={key}").status_code == 200

    def test_synonyms_schema(self, client: TestClient):
        key = self._first_key(client)
        body = client.get(f"/dictionary/synonyms?key={key}").json()
        for f in ("key", "synonyms", "resolved", "weight", "category"):
            assert f in body

    def test_synonyms_key_matches_request(self, client: TestClient):
        key = self._first_key(client)
        body = client.get(f"/dictionary/synonyms?key={key}").json()
        assert body["key"] == key

    def test_synonyms_list_type(self, client: TestClient):
        key = self._first_key(client)
        body = client.get(f"/dictionary/synonyms?key={key}").json()
        assert isinstance(body["synonyms"], list)

    def test_synonyms_unknown_key_returns_404(self, client: TestClient):
        r = client.get("/dictionary/synonyms?key=__not_a_real_key_xyz__")
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
# M5-4 History Timeline エンドポイントテスト (+20件)
# ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def history_entry_id(client: TestClient) -> str:  # noqa: ARG001
    """HistoryManager に直接エントリを記録してIDを返す（cache依存を回避）"""
    from rest.app import get_context

    ctx = get_context()
    entry = ctx.history_manager.record(
        input_prompt="masterpiece, blue_eyes",
        output_prompt="Quality.High, Eyes.Blue",
        tag_count=2,
        overall_score=82.5,
    )
    return entry.id


class TestHistoryGet:
    """GET /history/{id} (5件)"""

    def test_get_entry_status_200(self, client: TestClient, history_entry_id: str):
        r = client.get(f"/history/{history_entry_id}")
        assert r.status_code == 200

    def test_get_entry_schema(self, client: TestClient, history_entry_id: str):
        body = client.get(f"/history/{history_entry_id}").json()
        for f in ("id", "input_prompt", "output_prompt", "tag_count",
                  "overall_score", "created_at", "favorite", "label"):
            assert f in body

    def test_get_entry_id_matches(self, client: TestClient, history_entry_id: str):
        body = client.get(f"/history/{history_entry_id}").json()
        assert body["id"] == history_entry_id

    def test_get_entry_not_found_returns_404(self, client: TestClient):
        r = client.get("/history/__no_such_id_xyz__")
        assert r.status_code == 404

    def test_get_entry_has_output_prompt(self, client: TestClient, history_entry_id: str):
        body = client.get(f"/history/{history_entry_id}").json()
        assert isinstance(body["output_prompt"], str)


class TestHistoryFavorite:
    """POST /history/{id}/favorite (4件)"""

    def test_toggle_favorite_status_200(self, client: TestClient, history_entry_id: str):
        r = client.post(f"/history/{history_entry_id}/favorite")
        assert r.status_code == 200

    def test_toggle_favorite_schema(self, client: TestClient, history_entry_id: str):
        body = client.post(f"/history/{history_entry_id}/favorite").json()
        assert "id" in body
        assert "favorite" in body
        assert isinstance(body["favorite"], bool)

    def test_toggle_favorite_toggles_state(self, client: TestClient, history_entry_id: str):
        r1 = client.post(f"/history/{history_entry_id}/favorite").json()["favorite"]
        r2 = client.post(f"/history/{history_entry_id}/favorite").json()["favorite"]
        assert r1 != r2

    def test_toggle_favorite_not_found_returns_404(self, client: TestClient):
        r = client.post("/history/__no_such_id_xyz__/favorite")
        assert r.status_code == 404


class TestHistoryLabel:
    """PUT /history/{id}/label (4件)"""

    def test_set_label_status_200(self, client: TestClient, history_entry_id: str):
        r = client.put(f"/history/{history_entry_id}/label", json={"label": "test_label"})
        assert r.status_code == 200

    def test_set_label_schema(self, client: TestClient, history_entry_id: str):
        body = client.put(f"/history/{history_entry_id}/label", json={"label": "hello"}).json()
        assert "id" in body
        assert "label" in body

    def test_set_label_value_persisted(self, client: TestClient, history_entry_id: str):
        client.put(f"/history/{history_entry_id}/label", json={"label": "persist_check"})
        body = client.get(f"/history/{history_entry_id}").json()
        assert body["label"] == "persist_check"

    def test_set_label_not_found_returns_404(self, client: TestClient):
        r = client.put("/history/__no_such_id_xyz__/label", json={"label": "x"})
        assert r.status_code == 404


class TestHistoryDiff:
    """GET /history/{id1}/diff/{id2} (4件)"""

    @pytest.fixture(scope="class")
    def two_entry_ids(self, client: TestClient):  # noqa: ARG002
        """2件のエントリを直接記録して返す"""
        from rest.app import get_context

        ctx = get_context()
        e1 = ctx.history_manager.record(
            input_prompt="masterpiece, blue_eyes",
            output_prompt="Quality.High, Eyes.Blue",
            tag_count=2,
            overall_score=80.0,
        )
        e2 = ctx.history_manager.record(
            input_prompt="masterpiece, red_hair, smile",
            output_prompt="Quality.High, Hair.Red, Expression.Smile",
            tag_count=3,
            overall_score=88.0,
        )
        return e1.id, e2.id

    def test_diff_status_200(self, client: TestClient, two_entry_ids):
        id1, id2 = two_entry_ids
        r = client.get(f"/history/{id1}/diff/{id2}")
        assert r.status_code == 200

    def test_diff_schema(self, client: TestClient, two_entry_ids):
        id1, id2 = two_entry_ids
        body = client.get(f"/history/{id1}/diff/{id2}").json()
        for f in ("entry_id_1", "entry_id_2", "added_tags",
                  "removed_tags", "unchanged_tags", "score_delta", "has_changes"):
            assert f in body

    def test_diff_ids_match(self, client: TestClient, two_entry_ids):
        id1, id2 = two_entry_ids
        body = client.get(f"/history/{id1}/diff/{id2}").json()
        assert body["entry_id_1"] == id1
        assert body["entry_id_2"] == id2

    def test_diff_not_found_returns_404(self, client: TestClient):
        r = client.get("/history/__no_id_1__/diff/__no_id_2__")
        assert r.status_code == 404


class TestHistoryDelete:
    """DELETE /history/{id} (3件)"""

    def test_delete_not_found_returns_404(self, client: TestClient):
        r = client.delete("/history/__no_such_id_to_delete__")
        assert r.status_code == 404

    def test_delete_status_200(self, client: TestClient):
        from rest.app import get_context

        ctx = get_context()
        entry = ctx.history_manager.record(
            input_prompt="delete_me", output_prompt="delete_me_out", tag_count=1, overall_score=50.0
        )
        r = client.delete(f"/history/{entry.id}")
        assert r.status_code == 200

    def test_delete_schema(self, client: TestClient):
        from rest.app import get_context

        ctx = get_context()
        entry = ctx.history_manager.record(
            input_prompt="delete_me_2", output_prompt="delete_me_out_2", tag_count=1, overall_score=50.0
        )
        body = client.delete(f"/history/{entry.id}").json()
        assert "id" in body
        assert body["deleted"] is True
