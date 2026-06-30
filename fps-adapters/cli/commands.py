"""
fps-adapters/cli/commands.py — CLI サブコマンド実装

各サブコマンドはこの関数群が担う。main.py からはここを呼ぶだけ。
全関数は終了コード（0=成功, 1=失敗）を返す。
"""

from __future__ import annotations

import argparse
import json

from .context import CliContext


def _print(s: str = "") -> None:
    print(s)


# ══════════════════════════════════════════════════════════════════
# compile — プロンプト変換
# ══════════════════════════════════════════════════════════════════


def cmd_compile(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps compile "<prompt>"` — プロンプトをコンパイルする"""
    result = ctx.pipeline_manager.compile(args.prompt)

    if args.json:
        output = {
            "success": result.success,
            "prompt": result.prompt,
            "negative": result.negative,
            "tag_count": result.tag_count,
            "errors": result.errors,
        }
        _print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        _print(f"prompt   : {result.prompt}")
        _print(f"negative : {result.negative}")
        _print(f"tags     : {result.tag_count}")
        if result.errors:
            _print("errors:")
            for e in result.errors:
                _print(f"  - {e}")

    if args.adapter:
        _emit_adapter_output(result, args.adapter)

    return 0 if result.success else 1


def _emit_adapter_output(result, adapter_name: str) -> None:
    """指定アダプターでの出力も追加表示する"""
    from typing import Any

    adapter: Any
    try:
        if adapter_name == "comfyui":
            from comfyui.adapter import ComfyUIAdapter

            adapter = ComfyUIAdapter(api_version="v1")
        elif adapter_name == "a1111":
            from a1111.adapter import A1111Adapter

            adapter = A1111Adapter()
        elif adapter_name == "novelai":
            from novelai.adapter import NovelAIAdapter

            adapter = NovelAIAdapter()
        else:
            _print(f"[WARN] unknown adapter: {adapter_name}")
            return

        out = adapter.convert(result)
        _print(f"\n--- {adapter_name} ---")
        _print(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception as e:
        _print(f"[ERROR] adapter '{adapter_name}' failed: {e}")


# ══════════════════════════════════════════════════════════════════
# validate — 辞書/ルール/プリセットの検証
# ══════════════════════════════════════════════════════════════════


def cmd_validate(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps validate` — 辞書/ルール/プリセットを検証する"""
    all_errors: dict[str, list[str]] = {}

    targets = args.target or ["dictionary", "rules", "presets"]

    if "dictionary" in targets:
        errors = ctx.dictionary_manager.validate()
        if errors:
            all_errors["dictionary"] = errors

    if "rules" in targets:
        errors = ctx.rule_manager.validate()
        if errors:
            all_errors["rules"] = errors

    if "presets" in targets:
        errors = ctx.preset_manager.validate()
        if errors:
            all_errors["presets"] = errors

    if not all_errors:
        _print("[OK] all validations passed")
        if not args.quiet:
            _print(f"  dictionary: {ctx.dictionary_manager.statistics()['total_keys']} keys")
            _print(f"  rules     : {ctx.rule_manager.statistics()['total_rules']} rules")
            _print(f"  presets   : {ctx.preset_manager.statistics()['total_presets']} presets")
        return 0

    _print("[FAILED] validation errors found:")
    for target, errors in all_errors.items():
        _print(f"\n  --- {target} ---")
        for e in errors:
            _print(f"    - {e}")
    return 1


# ══════════════════════════════════════════════════════════════════
# backup — バックアップ管理
# ══════════════════════════════════════════════════════════════════


def cmd_backup_create(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps backup create [--target TARGET]`"""
    from backup.models import BackupTarget

    target_map = {
        "all": BackupTarget.ALL,
        "dictionary": BackupTarget.DICTIONARY,
        "rules": BackupTarget.RULES,
        "presets": BackupTarget.PRESETS,
    }
    target = target_map.get(args.target, BackupTarget.ALL)
    result = ctx.backup_manager.backup(target)

    if result.success:
        _print(f"[OK] backup created: {result.entry_count} entries, {result.total_bytes} bytes")
        return 0
    _print("[FAILED] backup errors:")
    for e in result.errors:
        _print(f"  - {e}")
    return 1


def cmd_backup_list(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps backup list`"""
    entries = ctx.backup_manager.list_backups()
    if not entries:
        _print("(no backups)")
        return 0
    for e in entries[: args.limit]:
        _print(f"{e.id}  [{e.target}]  {e.created_at_str}  ({e.size_kb:.1f}KB)")
    return 0


def cmd_backup_restore(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps backup restore <id>`"""
    try:
        result = ctx.backup_manager.restore(args.backup_id)
    except Exception as e:
        _print(f"[ERROR] {e}")
        return 1

    if result.success:
        _print(f"[OK] restored: {[str(p) for p in result.restored_files]}")
        return 0
    _print("[FAILED] restore errors:")
    for err in result.errors:
        _print(f"  - {err}")
    return 1


# ══════════════════════════════════════════════════════════════════
# dictionary — 辞書検索
# ══════════════════════════════════════════════════════════════════


def cmd_dictionary_search(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps dictionary search <query>`"""
    result = ctx.dictionary_manager.lookup(args.query)
    if result.found:
        _print(f"found   : {args.query}")
        _print(f"resolved: {result.resolved}")
        _print(f"category: {result.category}")
        _print(f"weight  : {result.weight}")
        return 0
    _print(f"not found: {args.query}")
    return 1


def cmd_dictionary_stats(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps dictionary stats`"""
    stats = ctx.dictionary_manager.statistics()
    _print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


# ══════════════════════════════════════════════════════════════════
# plugin — プラグイン管理
# ══════════════════════════════════════════════════════════════════


def cmd_plugin_list(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps plugin list`"""
    names = ctx.plugin_manager.list_names()
    if not names:
        _print("(no plugins loaded)")
        return 0
    for name in names:
        _print(name)
    return 0


def cmd_plugin_load(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps plugin load <path>`"""
    try:
        count = ctx.plugin_manager.load_from_file(args.path)
        _print(f"[OK] loaded {count} plugin(s) from {args.path}")
        return 0
    except Exception as e:
        _print(f"[ERROR] {e}")
        return 1


# ══════════════════════════════════════════════════════════════════
# optimize — プロンプト品質分析
# ══════════════════════════════════════════════════════════════════


def cmd_optimize(args: argparse.Namespace, ctx: CliContext) -> int:
    """`fps optimize "<prompt>"`"""
    pipeline_result = ctx.pipeline_manager.compile(args.prompt)
    opt_result = ctx.optimizer_manager.analyze_pipeline_result(pipeline_result)

    if args.json:
        output = {
            "score": opt_result.score.to_dict(),
            "issues": [
                {"type": str(i.type), "severity": str(i.severity), "message": i.message}
                for i in opt_result.issues
            ],
            "recommendations": opt_result.recommendations,
        }
        _print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        _print(f"overall_score: {opt_result.score.overall_score}")
        _print(f"coverage     : {opt_result.score.coverage_score}")
        _print(f"balance      : {opt_result.score.balance_score}")
        _print(f"redundancy   : {opt_result.score.redundancy_score}")
        if opt_result.issues:
            _print("\nissues:")
            for i in opt_result.issues:
                _print(f"  [{i.severity}] {i.message}")
        _print("\nrecommendations:")
        for r in opt_result.recommendations:
            _print(f"  - {r}")

    return 0
