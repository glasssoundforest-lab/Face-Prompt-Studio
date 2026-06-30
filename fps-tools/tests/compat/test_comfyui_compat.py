"""
fps-tools/tests/compat/test_comfyui_compat.py

ComfyUI 入出力互換性テスト。
ComfyUI が要求するノードインターフェース仕様（INPUT_TYPES / RETURN_TYPES /
FUNCTION / CATEGORY）への準拠と、NODE_CLASS_MAPPINGS の整合性を検証する。

pytest で実行: pytest fps-tools/tests/compat/test_comfyui_compat.py -v
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from comfyui import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS


# ══════════════════════════════════════════════════════════════════
# ComfyUI ノードインターフェース準拠
# ══════════════════════════════════════════════════════════════════

class TestComfyUINodeInterface:
    """
    ComfyUI が要求するノードクラスインターフェースに
    全ノードが準拠していることを検証する。

    必須属性:
      - INPUT_TYPES()  classmethod、dict を返す
      - RETURN_TYPES   tuple[str, ...]
      - RETURN_NAMES   tuple[str, ...]（RETURN_TYPES と同じ長さ）
      - FUNCTION       str（実行メソッド名）
      - CATEGORY       str
    """

    @pytest.fixture(params=list(NODE_CLASS_MAPPINGS.items()))
    def node_entry(self, request):
        return request.param  # (node_id, node_class)

    def test_input_types_is_classmethod(self, node_entry):
        node_id, node_class = node_entry
        assert hasattr(node_class, "INPUT_TYPES"), f"{node_id}: INPUT_TYPES がありません"
        assert inspect.ismethod(node_class.INPUT_TYPES) or isinstance(
            inspect.getattr_static(node_class, "INPUT_TYPES"), classmethod
        ), f"{node_id}: INPUT_TYPES は classmethod である必要があります"

    def test_input_types_returns_dict(self, node_entry):
        node_id, node_class = node_entry
        types = node_class.INPUT_TYPES()
        assert isinstance(types, dict), f"{node_id}: INPUT_TYPES() は dict を返す必要があります"

    def test_input_types_has_required_key(self, node_entry):
        node_id, node_class = node_entry
        types = node_class.INPUT_TYPES()
        assert "required" in types, f"{node_id}: 'required' キーが必要です"

    def test_return_types_is_tuple(self, node_entry):
        node_id, node_class = node_entry
        assert isinstance(node_class.RETURN_TYPES, tuple), (
            f"{node_id}: RETURN_TYPES はタプルである必要があります"
        )

    def test_return_names_matches_return_types_length(self, node_entry):
        node_id, node_class = node_entry
        assert len(node_class.RETURN_TYPES) == len(node_class.RETURN_NAMES), (
            f"{node_id}: RETURN_TYPES と RETURN_NAMES の長さが一致しません "
            f"({len(node_class.RETURN_TYPES)} != {len(node_class.RETURN_NAMES)})"
        )

    def test_function_is_string(self, node_entry):
        node_id, node_class = node_entry
        assert isinstance(node_class.FUNCTION, str), f"{node_id}: FUNCTION は文字列である必要があります"

    def test_function_method_exists(self, node_entry):
        node_id, node_class = node_entry
        assert hasattr(node_class, node_class.FUNCTION), (
            f"{node_id}: FUNCTION で指定されたメソッド '{node_class.FUNCTION}' が存在しません"
        )

    def test_category_is_string(self, node_entry):
        node_id, node_class = node_entry
        assert isinstance(node_class.CATEGORY, str), f"{node_id}: CATEGORY は文字列である必要があります"

    def test_category_not_empty(self, node_entry):
        node_id, node_class = node_entry
        assert node_class.CATEGORY.strip() != "", f"{node_id}: CATEGORY が空です"

    def test_function_callable_with_required_inputs(self, node_entry):
        """必須入力のデフォルト値だけでノードが実行できることを確認する"""
        node_id, node_class = node_entry
        types = node_class.INPUT_TYPES()
        kwargs = {}

        for section in ("required", "optional"):
            for name, spec in types.get(section, {}).items():
                if len(spec) > 1 and isinstance(spec[1], dict) and "default" in spec[1]:
                    kwargs[name] = spec[1]["default"]
                elif spec[0] == "STRING":
                    kwargs[name] = ""
                elif spec[0] == "BOOLEAN":
                    kwargs[name] = True
                elif spec[0] == "FLOAT" or spec[0] == "INT":
                    kwargs[name] = 1.0
                elif isinstance(spec[0], list):
                    kwargs[name] = spec[0][0]

        instance = node_class()
        func = getattr(instance, node_class.FUNCTION)
        result = func(**kwargs)

        assert isinstance(result, tuple), f"{node_id}: 戻り値はタプルである必要があります"
        assert len(result) == len(node_class.RETURN_TYPES), (
            f"{node_id}: 戻り値の数が RETURN_TYPES と一致しません"
        )


# ══════════════════════════════════════════════════════════════════
# NODE_CLASS_MAPPINGS 整合性
# ══════════════════════════════════════════════════════════════════

class TestNodeMappingsConsistency:
    def test_mappings_not_empty(self):
        assert len(NODE_CLASS_MAPPINGS) > 0

    def test_all_node_ids_have_display_names(self):
        missing = set(NODE_CLASS_MAPPINGS) - set(NODE_DISPLAY_NAME_MAPPINGS)
        assert not missing, f"表示名がないノード: {missing}"

    def test_no_orphan_display_names(self):
        orphans = set(NODE_DISPLAY_NAME_MAPPINGS) - set(NODE_CLASS_MAPPINGS)
        assert not orphans, f"対応するノードがない表示名: {orphans}"

    def test_node_ids_are_valid_identifiers(self):
        """ComfyUI のノード ID は識別子として有効な文字列である必要がある"""
        for node_id in NODE_CLASS_MAPPINGS:
            assert node_id.isidentifier() or node_id.replace("_", "").isalnum(), (
                f"無効なノード ID: '{node_id}'"
            )

    def test_node_ids_unique(self):
        ids = list(NODE_CLASS_MAPPINGS.keys())
        assert len(ids) == len(set(ids)), "ノード ID に重複があります"

    def test_display_names_are_strings(self):
        for name, display in NODE_DISPLAY_NAME_MAPPINGS.items():
            assert isinstance(display, str)
            assert len(display) > 0


# ══════════════════════════════════════════════════════════════════
# ComfyUI 標準データ型との整合性
# ══════════════════════════════════════════════════════════════════

class TestComfyUIDataTypes:
    """ComfyUI が認識する標準データ型（STRING/INT/FLOAT/BOOLEAN）の
    使用が正しいことを確認する"""

    VALID_PRIMITIVE_TYPES = {"STRING", "INT", "FLOAT", "BOOLEAN"}

    def test_input_types_use_valid_primitives_or_lists(self):
        for node_id, node_class in NODE_CLASS_MAPPINGS.items():
            types = node_class.INPUT_TYPES()
            for section in ("required", "optional"):
                for name, spec in types.get(section, {}).items():
                    type_spec = spec[0]
                    is_valid = (
                        isinstance(type_spec, list)
                        or type_spec in self.VALID_PRIMITIVE_TYPES
                    )
                    assert is_valid, f"{node_id}.{name}: 不正な型指定 '{type_spec}'"

    def test_float_inputs_have_min_max(self):
        """FLOAT 型の入力には min/max が設定されているべき（GUI スライダー用）"""
        warnings = []
        for node_id, node_class in NODE_CLASS_MAPPINGS.items():
            types = node_class.INPUT_TYPES()
            for section in ("required", "optional"):
                for name, spec in types.get(section, {}).items():
                    if spec[0] == "FLOAT" and len(spec) > 1:
                        config = spec[1]
                        if "min" not in config or "max" not in config:
                            warnings.append(f"{node_id}.{name}")
        # 警告のみ（必須ではないが推奨）
        if warnings:
            print(f"\n[INFO] min/max 未設定の FLOAT 入力: {warnings}")


# ══════════════════════════════════════════════════════════════════
# IS_CHANGED 動作確認
# ══════════════════════════════════════════════════════════════════

class TestIsChangedBehavior:
    """ノードの再実行制御（IS_CHANGED）が正しく機能することを確認する"""

    @pytest.mark.parametrize("node_id,node_class", list(NODE_CLASS_MAPPINGS.items()))
    def test_is_changed_exists_or_default(self, node_id, node_class):
        # IS_CHANGED は任意実装。実装されていれば呼び出し可能であることを確認
        if hasattr(node_class, "IS_CHANGED"):
            result = node_class.IS_CHANGED()
            # NaN もしくは比較可能な値であればよい
            assert result is not None
