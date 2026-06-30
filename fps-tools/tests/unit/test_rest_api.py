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
