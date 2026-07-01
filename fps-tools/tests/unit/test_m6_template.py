"""
fps-tools/tests/unit/test_m6_template.py

M6-3 プロンプトテンプレートエンジン テスト (40件)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))

from template.manager import TemplateManager  # noqa: E402
from template.models import RenderResult, Template, TemplateVariable  # noqa: E402


# ══════════════════════════════════════════════════════════════════
# Template / TemplateVariable モデル (8件)
# ══════════════════════════════════════════════════════════════════
class TestTemplateModels:
    def test_template_variable_names(self):
        t = Template(id="t1", name="T", body="{quality}, {eye_color} eyes")
        assert t.variable_names == ["quality", "eye_color"]

    def test_template_variable_names_dedup(self):
        t = Template(id="t1", name="T", body="{a}, {b}, {a}")
        assert t.variable_names == ["a", "b"]

    def test_template_to_dict(self):
        t = Template(id="t1", name="T", body="{x}", category="test")
        d = t.to_dict()
        assert d["id"] == "t1"
        assert d["body"] == "{x}"

    def test_template_variable_default(self):
        v = TemplateVariable("eye_color", default="blue_eyes")
        assert v.default == "blue_eyes"

    def test_render_result_success_true_when_no_missing(self):
        r = RenderResult(template_id="t", rendered="done", missing_variables=[])
        assert r.success is True

    def test_render_result_success_false_when_missing(self):
        r = RenderResult(template_id="t", rendered="...", missing_variables=["x"])
        assert r.success is False

    def test_template_tags_default_empty(self):
        t = Template(id="t1", name="T", body="x")
        assert t.tags == []

    def test_template_category_default(self):
        t = Template(id="t1", name="T", body="x")
        assert t.category == "general"


# ══════════════════════════════════════════════════════════════════
# TemplateManager 基本操作 (12件)
# ══════════════════════════════════════════════════════════════════
class TestTemplateManager:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tm = TemplateManager()
        self.tm.load()

    def test_load_returns_self(self):
        tm = TemplateManager()
        result = tm.load()
        assert result is tm

    def test_builtin_templates_present(self):
        assert len(self.tm.list_templates()) >= 5

    def test_list_templates_returns_list(self):
        templates = self.tm.list_templates()
        assert isinstance(templates, list)

    def test_get_face_basic_exists(self):
        t = self.tm.get("face_basic")
        assert t is not None
        assert t.id == "face_basic"

    def test_get_nonexistent_returns_none(self):
        assert self.tm.get("__no_such_template__") is None

    def test_exists_true_for_builtin(self):
        assert self.tm.exists("face_basic")

    def test_exists_false_for_unknown(self):
        assert not self.tm.exists("__no_such__")

    def test_list_by_category_face(self):
        face_templates = self.tm.list_templates(category="face")
        assert len(face_templates) >= 1
        assert all(t.category == "face" for t in face_templates)

    def test_list_by_category_negative(self):
        neg = self.tm.list_templates(category="negative")
        assert len(neg) >= 1

    def test_categories_returns_list(self):
        cats = self.tm.categories()
        assert isinstance(cats, list)
        assert "face" in cats

    def test_statistics_total(self):
        stats = self.tm.statistics()
        assert stats["total_templates"] >= 5

    def test_statistics_by_category(self):
        stats = self.tm.statistics()
        assert "face" in stats["by_category"]


# ══════════════════════════════════════════════════════════════════
# render() / render_body() (15件)
# ══════════════════════════════════════════════════════════════════
class TestTemplateRender:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.tm = TemplateManager()
        self.tm.load()

    def test_render_face_basic_all_vars(self):
        result = self.tm.render("face_basic", {
            "quality": "masterpiece",
            "eye_color": "blue_eyes",
            "hair_color": "blonde",
            "hair_length": "long",
            "expression": "smile",
        })
        assert result.success
        assert "masterpiece" in result.rendered
        assert "blue_eyes" in result.rendered

    def test_render_missing_var_not_success(self):
        result = self.tm.render("face_basic", {"quality": "masterpiece"})
        assert not result.success
        assert len(result.missing_variables) > 0

    def test_render_result_variables_used(self):
        result = self.tm.render("face_basic", {
            "quality": "masterpiece",
            "eye_color": "red_eyes",
            "hair_color": "black",
            "hair_length": "short",
            "expression": "serious",
        })
        assert "quality" in result.variables_used
        assert result.variables_used["quality"] == "masterpiece"

    def test_render_unknown_template_raises_key_error(self):
        with pytest.raises(KeyError):
            self.tm.render("__no_such__", {})

    def test_render_template_id_in_result(self):
        result = self.tm.render("face_basic", {
            "quality": "masterpiece",
            "eye_color": "blue_eyes",
            "hair_color": "gold",
            "hair_length": "long",
            "expression": "smile",
        })
        assert result.template_id == "face_basic"

    def test_render_body_direct(self):
        result = self.tm.render_body("{foo}, {bar}", {"foo": "hello", "bar": "world"})
        assert result.rendered == "hello, world"

    def test_render_body_missing_var(self):
        result = self.tm.render_body("{a}, {b}", {"a": "x"})
        assert "b" in result.missing_variables

    def test_render_body_empty_vars(self):
        result = self.tm.render_body("{a}", {})
        assert "a" in result.missing_variables

    def test_render_body_no_placeholders(self):
        result = self.tm.render_body("masterpiece, blue_eyes", {})
        assert result.rendered == "masterpiece, blue_eyes"
        assert result.success

    def test_render_body_template_id_empty(self):
        result = self.tm.render_body("{x}", {"x": "y"})
        assert result.template_id == ""

    def test_render_warnings_for_missing(self):
        result = self.tm.render_body("{x}, {y}", {"x": "val"})
        assert len(result.warnings) > 0

    def test_render_no_warnings_when_complete(self):
        result = self.tm.render_body("{x}", {"x": "val"})
        assert result.warnings == []

    def test_render_fantasy_template(self):
        result = self.tm.render("fantasy_character", {
            "quality": "masterpiece",
            "eye_color": "purple_eyes",
            "hair_color": "silver_hair",
            "fantasy_feature": "cat_ears",
            "expression": "smile",
            "accessories": "",
        })
        assert "masterpiece" in result.rendered
        assert "cat_ears" in result.rendered

    def test_render_negative_basic_template(self):
        result = self.tm.render("negative_basic", {
            "additional_negative": "watermark, text",
        })
        assert "low_quality" in result.rendered
        assert "watermark" in result.rendered

    def test_render_deduplicates_placeholders(self):
        # 同じ変数名が複数あっても1回の指定で両方置換される
        result = self.tm.render_body("{x} and {x}", {"x": "test"})
        assert result.rendered == "test and test"


# ══════════════════════════════════════════════════════════════════
# REST API: テンプレートエンドポイント (5件)
# ══════════════════════════════════════════════════════════════════
fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from rest.app import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestTemplateRestApi:
    def test_list_templates_200(self, client: TestClient):
        r = client.get("/templates")
        assert r.status_code == 200

    def test_list_templates_schema(self, client: TestClient):
        body = client.get("/templates").json()
        assert "templates" in body
        assert "total" in body
        assert body["total"] >= 5

    def test_list_templates_by_category(self, client: TestClient):
        body = client.get("/templates?category=face").json()
        assert all(t["category"] == "face" for t in body["templates"])

    def test_render_template_200(self, client: TestClient):
        r = client.post(
            "/templates/face_basic/render",
            json={"variables": {
                "quality": "masterpiece",
                "eye_color": "blue_eyes",
                "hair_color": "gold",
                "hair_length": "long",
                "expression": "smile",
            }},
        )
        assert r.status_code == 200

    def test_render_template_not_found_404(self, client: TestClient):
        r = client.post("/templates/__no_such__/render", json={"variables": {}})
        assert r.status_code == 404
