"""
fps-adapters/cli/main.py — Face Prompt Studio CLI

ComfyUI を起動せずにプロンプト変換・検証・バックアップ等を行う
コマンドラインツール。

使い方:
  fps compile "masterpiece, blue_eyes"
  fps compile "masterpiece" --json --adapter comfyui
  fps validate
  fps validate --target dictionary
  fps backup create --target all
  fps backup list
  fps backup restore <backup_id>
  fps dictionary search blue_eyes
  fps dictionary stats
  fps plugin list
  fps plugin load my_plugin.py
  fps optimize "masterpiece, blue_eyes, brown_eyes"
"""

from __future__ import annotations

import argparse
import sys

from .commands import (
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
from .context import CliContext


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fps",
        description="Face Prompt Studio — Command Line Interface",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── compile ──────────────────────────────────────────────
    p_compile = subparsers.add_parser("compile", help="プロンプトをコンパイルする")
    p_compile.add_argument("prompt", help="DSL形式のプロンプト文字列")
    p_compile.add_argument("--json", action="store_true", help="JSON形式で出力")
    p_compile.add_argument(
        "--adapter",
        choices=["comfyui", "a1111", "novelai"],
        default=None,
        help="指定アダプター形式での出力も追加表示する",
    )
    p_compile.set_defaults(func=cmd_compile)

    # ── validate ─────────────────────────────────────────────
    p_validate = subparsers.add_parser("validate", help="辞書/ルール/プリセットを検証する")
    p_validate.add_argument(
        "--target",
        action="append",
        choices=["dictionary", "rules", "presets"],
        help="検証対象を指定（複数指定可、省略時は全て）",
    )
    p_validate.add_argument("--quiet", action="store_true", help="成功時の詳細を省略")
    p_validate.set_defaults(func=cmd_validate)

    # ── backup ───────────────────────────────────────────────
    p_backup = subparsers.add_parser("backup", help="バックアップを管理する")
    backup_sub = p_backup.add_subparsers(dest="backup_action", required=True)

    p_backup_create = backup_sub.add_parser("create", help="バックアップを作成する")
    p_backup_create.add_argument(
        "--target",
        choices=["all", "dictionary", "rules", "presets"],
        default="all",
    )
    p_backup_create.set_defaults(func=cmd_backup_create)

    p_backup_list = backup_sub.add_parser("list", help="バックアップ一覧を表示する")
    p_backup_list.add_argument("--limit", type=int, default=20)
    p_backup_list.set_defaults(func=cmd_backup_list)

    p_backup_restore = backup_sub.add_parser("restore", help="バックアップをリストアする")
    p_backup_restore.add_argument("backup_id", help="リストアするバックアップID")
    p_backup_restore.set_defaults(func=cmd_backup_restore)

    # ── dictionary ───────────────────────────────────────────
    p_dict = subparsers.add_parser("dictionary", help="辞書を操作する")
    dict_sub = p_dict.add_subparsers(dest="dict_action", required=True)

    p_dict_search = dict_sub.add_parser("search", help="タグを検索する")
    p_dict_search.add_argument("query", help="検索するタグ名")
    p_dict_search.set_defaults(func=cmd_dictionary_search)

    p_dict_stats = dict_sub.add_parser("stats", help="辞書統計を表示する")
    p_dict_stats.set_defaults(func=cmd_dictionary_stats)

    # ── plugin ───────────────────────────────────────────────
    p_plugin = subparsers.add_parser("plugin", help="プラグインを管理する")
    plugin_sub = p_plugin.add_subparsers(dest="plugin_action", required=True)

    p_plugin_list = plugin_sub.add_parser("list", help="ロード済みプラグイン一覧")
    p_plugin_list.set_defaults(func=cmd_plugin_list)

    p_plugin_load = plugin_sub.add_parser("load", help="プラグインをロードする")
    p_plugin_load.add_argument("path", help="プラグインファイルのパス")
    p_plugin_load.set_defaults(func=cmd_plugin_load)

    # ── optimize ─────────────────────────────────────────────
    p_optimize = subparsers.add_parser("optimize", help="プロンプト品質を分析する")
    p_optimize.add_argument("prompt", help="分析対象プロンプト")
    p_optimize.add_argument("--json", action="store_true", help="JSON形式で出力")
    p_optimize.set_defaults(func=cmd_optimize)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ctx = CliContext()
    try:
        return args.func(args, ctx)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
