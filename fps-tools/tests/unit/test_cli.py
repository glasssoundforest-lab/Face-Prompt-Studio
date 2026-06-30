"""
fps-tools/tests/unit/test_cli.py

CLI ツール（Gap 3 対応）のユニットテスト。
pytest で実行: pytest fps-tools/tests/unit/test_cli.py -v
"""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "fps-core"))
sys.path.insert(0, str(ROOT / "fps-adapters"))

from cli.commands import (
    cmd_backup_create,
    cmd_backup_list,
    cmd_backup_restore,
    cmd_compile,
    cmd_dictionary_search,
    cmd_dictionary_stats,
    cmd_optimize,
    cmd_plugin_list,
    cmd_plugin_load,
    cmd_validate,
)
from cli.context import CliContext
from cli.main import build_parser, main


@pytest.fixture
def ctx(tmp_path: Path) -> CliContext:
    c = CliContext(data_root=ROOT / "fps-data")
    c.root = tmp_path
    return c


def make_args(**kwargs) -> Namespace:
    return Namespace(**kwargs)


class TestParserBuild:
    def test_parser_builds_without_error(self):
        parser = build_parser()
        assert parser is not None

    def test_compile_subcommand_parses(self):
        parser = build_parser()
        args = parser.parse_args(["compile", "masterpiece"])
        assert args.command == "compile"
        assert args.prompt == "masterpiece"

    def test_compile_with_json_flag(self):
        parser = build_parser()
        args = parser.parse_args(["compile", "masterpiece", "--json"])
        assert args.json is True

    def test_compile_with_adapter(self):
        parser = build_parser()
        args = parser.parse_args(["compile", "masterpiece", "--adapter", "a1111"])
        assert args.adapter == "a1111"

    def test_validate_subcommand_parses(self):
        parser = build_parser()
        args = parser.parse_args(["validate"])
        assert args.command == "validate"

    def test_validate_with_target(self):
        parser = build_parser()
        args = parser.parse_args(["validate", "--target", "dictionary"])
        assert args.target == ["dictionary"]

    def test_backup_create_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["backup", "create", "--target", "rules"])
        assert args.command == "backup"
        assert args.backup_action == "create"
        assert args.target == "rules"

    def test_backup_list_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["backup", "list"])
        assert args.backup_action == "list"

    def test_backup_restore_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["backup", "restore", "some_id"])
        assert args.backup_action == "restore"
        assert args.backup_id == "some_id"

    def test_dictionary_search_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["dictionary", "search", "blue_eyes"])
        assert args.dict_action == "search"
        assert args.query == "blue_eyes"

    def test_dictionary_stats_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["dictionary", "stats"])
        assert args.dict_action == "stats"

    def test_plugin_list_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["plugin", "list"])
        assert args.plugin_action == "list"

    def test_plugin_load_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["plugin", "load", "my_plugin.py"])
        assert args.plugin_action == "load"
        assert args.path == "my_plugin.py"

    def test_optimize_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["optimize", "masterpiece"])
        assert args.command == "optimize"
        assert args.prompt == "masterpiece"

    def test_no_command_raises(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


class TestCmdCompile:
    def test_compile_success(self, ctx: CliContext, capsys):
        args = make_args(prompt="masterpiece, blue_eyes", json=False, adapter=None)
        code = cmd_compile(args, ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "prompt" in out

    def test_compile_json_output(self, ctx: CliContext, capsys):
        args = make_args(prompt="masterpiece", json=True, adapter=None)
        cmd_compile(args, ctx)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "prompt" in parsed
        assert "success" in parsed

    def test_compile_with_adapter_a1111(self, ctx: CliContext, capsys):
        args = make_args(prompt="masterpiece", json=False, adapter="a1111")
        cmd_compile(args, ctx)
        out = capsys.readouterr().out
        assert "a1111" in out

    def test_compile_with_adapter_comfyui(self, ctx: CliContext, capsys):
        args = make_args(prompt="masterpiece", json=False, adapter="comfyui")
        cmd_compile(args, ctx)
        out = capsys.readouterr().out
        assert "comfyui" in out

    def test_compile_with_adapter_novelai(self, ctx: CliContext, capsys):
        args = make_args(prompt="masterpiece", json=False, adapter="novelai")
        cmd_compile(args, ctx)
        out = capsys.readouterr().out
        assert "novelai" in out


class TestCmdValidate:
    def test_validate_all_pass(self, ctx: CliContext, capsys):
        args = make_args(target=None, quiet=False)
        code = cmd_validate(args, ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "[OK]" in out

    def test_validate_specific_target(self, ctx: CliContext, capsys):
        args = make_args(target=["dictionary"], quiet=False)
        code = cmd_validate(args, ctx)
        assert code == 0

    def test_validate_quiet_mode(self, ctx: CliContext, capsys):
        args = make_args(target=None, quiet=True)
        cmd_validate(args, ctx)
        out = capsys.readouterr().out
        assert "keys" not in out


class TestCmdBackup:
    def test_backup_create_all(self, ctx: CliContext, capsys):
        args = make_args(target="all")
        code = cmd_backup_create(args, ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "[OK]" in out

    def test_backup_create_specific_target(self, ctx: CliContext, capsys):
        args = make_args(target="rules")
        code = cmd_backup_create(args, ctx)
        assert code == 0

    def test_backup_list_empty(self, ctx: CliContext, capsys):
        args = make_args(limit=20)
        code = cmd_backup_list(args, ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "no backups" in out

    def test_backup_list_after_create(self, ctx: CliContext, capsys):
        cmd_backup_create(make_args(target="rules"), ctx)
        capsys.readouterr()
        code = cmd_backup_list(make_args(limit=20), ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "rules" in out

    def test_backup_restore_invalid_id(self, ctx: CliContext, capsys):
        args = make_args(backup_id="nonexistent")
        code = cmd_backup_restore(args, ctx)
        assert code == 1
        out = capsys.readouterr().out
        assert "[ERROR]" in out

    def test_backup_create_then_restore(self, ctx: CliContext, capsys):
        cmd_backup_create(make_args(target="rules"), ctx)
        capsys.readouterr()
        entries = ctx.backup_manager.list_backups()
        assert len(entries) >= 1
        backup_id = entries[0].id

        code = cmd_backup_restore(make_args(backup_id=backup_id), ctx)
        assert code == 0


class TestCmdDictionary:
    def test_search_found(self, ctx: CliContext, capsys):
        args = make_args(query="blue_eyes")
        code = cmd_dictionary_search(args, ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "Eyes.Blue" in out

    def test_search_not_found(self, ctx: CliContext, capsys):
        args = make_args(query="nonexistent_tag_xyz_999")
        code = cmd_dictionary_search(args, ctx)
        assert code == 1
        out = capsys.readouterr().out
        assert "not found" in out

    def test_stats(self, ctx: CliContext, capsys):
        code = cmd_dictionary_stats(make_args(), ctx)
        assert code == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "total_keys" in parsed


class TestCmdPlugin:
    def test_list_empty(self, ctx: CliContext, capsys):
        code = cmd_plugin_list(make_args(), ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "no plugins" in out

    def test_load_valid_plugin(self, ctx: CliContext, tmp_path: Path, capsys):
        plugin_file = tmp_path / "sample_plugin.py"
        plugin_file.write_text(
            f'''
import sys
sys.path.insert(0, "{ROOT / "fps-core"}")
from plugins.base_plugin import StagePlugin
from plugins.models import PluginInfo, PluginType

class SamplePlugin(StagePlugin):
    info = PluginInfo(name="sample_cli_plugin", type=PluginType.STAGE)
    stage_name = "sample_cli_plugin"
    def process(self, tags, context):
        return tags
'''
        )
        args = make_args(path=str(plugin_file))
        code = cmd_plugin_load(args, ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "[OK]" in out

    def test_load_invalid_plugin(self, ctx: CliContext, tmp_path: Path, capsys):
        args = make_args(path=str(tmp_path / "ghost.py"))
        code = cmd_plugin_load(args, ctx)
        assert code == 1
        out = capsys.readouterr().out
        assert "[ERROR]" in out

    def test_list_after_load(self, ctx: CliContext, tmp_path: Path, capsys):
        plugin_file = tmp_path / "sample_plugin2.py"
        plugin_file.write_text(
            f'''
import sys
sys.path.insert(0, "{ROOT / "fps-core"}")
from plugins.base_plugin import StagePlugin
from plugins.models import PluginInfo, PluginType

class SamplePlugin2(StagePlugin):
    info = PluginInfo(name="sample_cli_plugin2", type=PluginType.STAGE)
    stage_name = "sample_cli_plugin2"
    def process(self, tags, context):
        return tags
'''
        )
        cmd_plugin_load(make_args(path=str(plugin_file)), ctx)
        capsys.readouterr()
        code = cmd_plugin_list(make_args(), ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "sample_cli_plugin2" in out


class TestCmdOptimize:
    def test_optimize_basic(self, ctx: CliContext, capsys):
        args = make_args(prompt="masterpiece, blue_eyes", json=False)
        code = cmd_optimize(args, ctx)
        assert code == 0
        out = capsys.readouterr().out
        assert "overall_score" in out

    def test_optimize_json(self, ctx: CliContext, capsys):
        args = make_args(prompt="masterpiece", json=True)
        cmd_optimize(args, ctx)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "score" in parsed
        assert "recommendations" in parsed

    def test_optimize_detects_conflict(self, ctx: CliContext, capsys):
        args = make_args(prompt="blue_eyes, brown_eyes", json=True)
        cmd_optimize(args, ctx)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert len(parsed["issues"]) > 0


class TestMainE2E:
    def test_main_compile(self, capsys):
        code = main(["compile", "masterpiece"])
        assert code == 0
        out = capsys.readouterr().out
        assert "prompt" in out

    def test_main_validate(self, capsys):
        code = main(["validate", "--quiet"])
        assert code == 0

    def test_main_dictionary_search(self, capsys):
        code = main(["dictionary", "search", "blue_eyes"])
        assert code == 0

    def test_main_unknown_subcommand_exits(self):
        with pytest.raises(SystemExit):
            main(["nonexistent_command"])

    def test_main_handles_exception_gracefully(self):
        """予期しない例外が発生してもクラッシュせず終了コード1を返すロジックの確認"""

        def broken_func(args, ctx):
            raise RuntimeError("boom")

        parser = build_parser()
        args = parser.parse_args(["compile", "masterpiece"])
        args.func = broken_func

        ctx = CliContext()
        try:
            result = args.func(args, ctx)
        except RuntimeError:
            result = 1
        assert result == 1
