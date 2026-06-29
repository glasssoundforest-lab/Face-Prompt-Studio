"""
main.py — Face Prompt Studio ローカルデバッグ・テスト実行エントリポイント

使い方:
  python main.py              全テスト実行（smoke + unit）
  python main.py --unit       ユニットテストのみ
  python main.py --smoke      スモークテストのみ
  python main.py --lint       Ruff lint チェック
  python main.py --format     Black フォーマットチェック
  python main.py --typecheck  mypy 型チェック
  python main.py --check      lint + format + typecheck
  python main.py --list       テスト一覧表示
  python main.py --cov        カバレッジ付きテスト
  python main.py -v           詳細出力
  python main.py --all        全チェック（test + lint + format + typecheck）
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
import time
from pathlib import Path

# ── パス設定 ──────────────────────────────────────────────────────
ROOT  = Path(__file__).parent
CORE  = ROOT / "fps-core"
TESTS = ROOT / "fps-tools" / "tests"
UNIT  = TESTS / "unit"

sys.path.insert(0, str(CORE))


# ══════════════════════════════════════════════════════════════════
# ANSI カラー
# ══════════════════════════════════════════════════════════════════

_R = "\033[0m"
_BOLD = "\033[1m"

def ok(s):    return f"\033[32m{_BOLD}{s}{_R}"
def fail(s):  return f"\033[31m{_BOLD}{s}{_R}"
def warn(s):  return f"\033[33m{s}{_R}"
def info(s):  return f"\033[36m{s}{_R}"
def dim(s):   return f"\033[90m{s}{_R}"
def bold(s):  return f"{_BOLD}{s}{_R}"
def header(s):return f"\033[34m{_BOLD}{s}{_R}"


# ══════════════════════════════════════════════════════════════════
# ユーティリティ
# ══════════════════════════════════════════════════════════════════

def _run(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=capture, text=True)


def _tool_available(tool: str) -> bool:
    return _run([sys.executable, "-m", tool, "--version"]).returncode == 0


def print_header() -> None:
    print()
    print(bold("=" * 64))
    print(bold("  Face Prompt Studio — Debug Runner"))
    print(bold("  v0.5.0-planning  |  Sprint 1"))
    print(bold("=" * 64))
    print()


# ══════════════════════════════════════════════════════════════════
# SMOKE TESTS
# ══════════════════════════════════════════════════════════════════

SmokeResults = dict[str, tuple[str, str | None]]


def _smoke_pass(smoke: SmokeResults, label: str) -> None:
    smoke[label] = ("PASS", None)
    print(f"  {ok('PASS')}  {label}")


def _smoke_fail(smoke: SmokeResults, label: str, e: Exception, verbose: bool) -> None:
    smoke[label] = ("FAIL", str(e))
    print(f"  {fail('FAIL')}  {label}")
    if verbose:
        print(f"         {warn(str(e))}")


def run_smoke_tests(verbose: bool = False) -> SmokeResults:
    print(header("── Smoke Tests ─────────────────────────────────────────"))
    print()
    smoke: SmokeResults = {}

    # ── Step 2: ConfigManager ──────────────────────────────────
    label = "Step 2  ConfigManager"
    try:
        from config.manager import ConfigManager

        cm = ConfigManager()
        cm.set("test.key", "hello")
        assert cm.get("test.key") == "hello"
        assert cm.get("missing", "default") == "default"
        cfg_path = ROOT / "fps-data" / "config.default.json"
        if cfg_path.exists():
            cm2 = ConfigManager(default_path=cfg_path)
            assert cm2.get("fps.version") is not None
            if verbose:
                print(dim(f"    fps.version = {cm2.get('fps.version')}"))
        _smoke_pass(smoke, label)
    except Exception as e:
        _smoke_fail(smoke, label, e, verbose)

    # ── Step 3: FPSLogger ──────────────────────────────────────
    label = "Step 3  FPSLogger"
    try:
        import logging as _log
        import tempfile
        from fps_logging.logger import FPSLogger

        FPSLogger._instance = None
        _log.getLogger("fps").handlers.clear()
        with tempfile.TemporaryDirectory() as td:
            fl = FPSLogger()
            fl.setup(log_dir=td, level="DEBUG", to_console=False, to_file=True)
            lg = fl.get("smoke")
            lg.info("smoke test")
            _log.getLogger("fps").handlers[0].flush()
            content = (Path(td) / "fps.log").read_text()
            assert "smoke test" in content
            if verbose:
                print(dim("    fps.log 書き込み確認 OK"))
        FPSLogger._instance = None
        _log.getLogger("fps").handlers.clear()
        _smoke_pass(smoke, label)
    except Exception as e:
        _smoke_fail(smoke, label, e, verbose)

    # ── Step 4: DictionaryManager ──────────────────────────────
    label = "Step 4  DictionaryManager"
    try:
        from dictionary.manager import DictionaryManager

        data_root = ROOT / "fps-data" / "dictionaries"
        dm = DictionaryManager(
            system_dir=data_root / "system",
            user_dir=data_root / "user",
        )
        dm.load()
        r = dm.lookup("masterpiece")
        assert r.found is True
        assert r.resolved == "Quality.High"
        if verbose:
            stats = dm.statistics()
            print(dim(f"    total_keys={stats['total_keys']}  categories={dm.categories()}"))
        _smoke_pass(smoke, label)
    except Exception as e:
        _smoke_fail(smoke, label, e, verbose)

    # ── Step 5: RuleManager ────────────────────────────────────
    label = "Step 5  RuleManager"
    try:
        from rules.manager import RuleManager
        from rules.models import ActionType, ConditionOp, Rule, RuleAction, RuleCondition

        rm = RuleManager(rule_dir=ROOT / "fps-data" / "rules")
        rm.load()
        test_rule = Rule(
            id="smoke_weight",
            action=RuleAction(type=ActionType.WEIGHT, value=1.5),
            conditions=[RuleCondition(op=ConditionOp.TAG, value="masterpiece")],
        )
        rm.add_rule(test_rule)
        test_tags = [{"tag": "masterpiece", "category": "quality", "weight": 1.0}]
        applied_tags, apply_results = rm.apply(test_tags)
        assert applied_tags[0]["weight"] == 1.5
        assert apply_results[0].applied is True
        if verbose:
            stats = rm.statistics()
            print(dim(f"    rules={stats['total_rules']}  applied weight={applied_tags[0]['weight']}"))
        _smoke_pass(smoke, label)
    except Exception as e:
        _smoke_fail(smoke, label, e, verbose)

    # ── Step 6: PresetManager ──────────────────────────────────
    label = "Step 6  PresetManager"
    try:
        from preset.manager import PresetManager
        from preset.models import Preset, PresetSource, PresetTag

        data_root = ROOT / "fps-data" / "presets"
        pm = PresetManager(
            system_dir=data_root / "system",
            user_dir=data_root / "user",
        )
        pm.load()
        stats = pm.statistics()
        assert stats["total_presets"] > 0
        preset = pm.get("anime_portrait")
        assert preset.tag_count > 0
        applied = pm.apply("anime_portrait")
        assert len(applied["tags"]) > 0
        if verbose:
            print(dim(f"    presets={stats['total_presets']}  tags={preset.tag_count}"))
        _smoke_pass(smoke, label)
    except Exception as e:
        _smoke_fail(smoke, label, e, verbose)

    # ── Step 7: Cache ──────────────────────────────────────────
    label = "Step 7  Cache"
    try:
        from cache.manager import CacheManager
        cm = CacheManager(max_size=128, default_ttl=3600)
        cm.set("lookup", "masterpiece", {"resolved": "Quality.High"})
        result = cm.get("lookup", "masterpiece")
        assert result == {"resolved": "Quality.High"}
        cm.set_lookup("blue_eyes", {"resolved": "Eyes.Blue"})
        assert cm.get_lookup("blue_eyes") is not None
        stats = cm.statistics()
        assert stats["hits"] >= 1
        if verbose:
            print(dim(f"    size={stats['total_size']}  hit_rate={stats['hit_rate']:.0%}"))
        _smoke_pass(smoke, label)
    except Exception as e:
        _smoke_fail(smoke, label, e, verbose)

    # ── Step 8: Backup ────────────────────────────────────────
    label = "Step 8  Backup"
    try:
        from backup.manager import BackupManager
        from backup.models import BackupTarget

        data_root = ROOT / "fps-data"
        bm = BackupManager(
            backup_dir  = ROOT / "backup",
            max_count   = 3,
            source_dirs = {
                BackupTarget.RULES:      data_root / "rules",
                BackupTarget.DICTIONARY: data_root / "dictionaries",
                BackupTarget.PRESETS:    data_root / "presets",
            },
        )
        bm.setup()
        result = bm.backup(BackupTarget.RULES)
        assert result.success is True
        stats = bm.statistics()
        if verbose:
            print(dim(f"    backups={stats['total_backups']}  bytes={stats['total_bytes']}"))
        _smoke_pass(smoke, label)
    except Exception as e:
        _smoke_fail(smoke, label, e, verbose)

    # ── Step 9: Pipeline ──────────────────────────────────────
    label = "Step 9  Pipeline (10-stage)"
    try:
        from pipeline.manager import PipelineManager

        pm_test = PipelineManager()
        result  = pm_test.compile("(quality:high), blue_eyes, [bad hands]")
        assert result.success is True
        assert result.stage_count == 10
        assert len(result.tags) >= 1
        if verbose:
            print(dim(f"    stages={pm_test.statistics()['run_count']} run  tags={result.tag_count}"))
        _smoke_pass(smoke, label)
    except Exception as e:
        _smoke_fail(smoke, label, e, verbose)

    # ── Step 10: ComfyUI Adapter ───────────────────────────────
    label = "Step 10 ComfyUI Adapter"
    try:
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "fps-adapters"))
        from comfyui.adapter import ComfyUIAdapter
        from pipeline.manager import PipelineManager as _PM2

        _pm2     = _PM2()
        _result2 = _pm2.compile("(quality:high), blue_eyes")
        adp      = ComfyUIAdapter(api_version="v1")
        out_v1   = adp.convert(_result2)
        assert "prompt" in out_v1 and "tags" in out_v1
        adp_v2  = ComfyUIAdapter(api_version="v2")
        out_v2  = adp_v2.convert(_result2)
        assert "nodes" in out_v2
        if verbose:
            print(dim(f"    v1 prompt='{out_v1['prompt'][:40]}'"))
        _smoke_pass(smoke, label)
    except Exception as e:
        _smoke_fail(smoke, label, e, verbose)

    print()
    return smoke


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS
# ══════════════════════════════════════════════════════════════════

def run_unit_tests(
    verbose: bool = False,
    coverage: bool = False,
) -> tuple[int, int, float]:
    print(header("── Unit Tests ──────────────────────────────────────────"))
    print()

    if not list(UNIT.glob("test_*.py")):
        print(warn("  テストファイルなし: fps-tools/tests/unit/test_*.py"))
        print()
        return 0, 0, 0.0

    args = [sys.executable, "-m", "pytest", str(UNIT),
            f"--pythonpath={CORE}", "--tb=short", "--no-header"]
    if verbose:
        args.append("-v")
    else:
        args.append("-q")
    if coverage:
        args += [
            f"--cov={CORE}",
            "--cov-report=term-missing",
            "--cov-report=html:fps-tools/coverage",
            "--cov-fail-under=50",
        ]

    start   = time.perf_counter()
    result  = _run(args, capture=not verbose)
    elapsed = time.perf_counter() - start
    output  = result.stdout or ""

    passed = failed = 0
    for line in output.splitlines():
        parts = line.split()
        for i, p in enumerate(parts):
            if p == "passed":
                try: passed = int(parts[i - 1])
                except Exception: pass
            if p == "failed":
                try: failed = int(parts[i - 1])
                except Exception: pass

    if not verbose:
        for line in output.splitlines():
            if "PASSED" in line:
                name = line.split("::")[-1].split()[0] if "::" in line else line
                print(f"  {ok('✓')}  {dim(name)}")
            elif "FAILED" in line:
                print(f"  {fail('✗')}  {line.strip()}")
        if result.returncode != 0 and not any("FAILED" in l for l in output.splitlines()):
            print(output)
        print()
    else:
        if coverage:
            print(output)

    return passed, failed, elapsed


# ══════════════════════════════════════════════════════════════════
# QUALITY CHECKS
# ══════════════════════════════════════════════════════════════════

QualityResult = tuple[str, int, str]


def run_lint(verbose: bool = False) -> QualityResult:
    label = "Ruff lint"
    if not _tool_available("ruff"):
        return label, 1, "ruff not installed. Run: pip install ruff"
    args = [sys.executable, "-m", "ruff", "check", str(CORE),
            "--select", "E,F,W,I,UP,B", "--output-format", "concise"]
    r = _run(args)
    return label, r.returncode, r.stdout + r.stderr


def run_format_check(verbose: bool = False) -> QualityResult:
    label = "Black format"
    if not _tool_available("black"):
        return label, 1, "black not installed. Run: pip install black"
    args = [sys.executable, "-m", "black", str(CORE),
            "--line-length", "100", "--check", "--quiet"]
    r = _run(args)
    msg = r.stdout + r.stderr
    if r.returncode != 0:
        msg = "フォーマット未適用のファイルあり。'python -m black fps-core' で修正できます。"
    return label, r.returncode, msg


def run_typecheck(verbose: bool = False) -> QualityResult:
    label = "mypy typecheck"
    if not _tool_available("mypy"):
        return label, 1, "mypy not installed. Run: pip install mypy"
    targets = [
        str(CORE / "config" / "manager.py"),
        str(CORE / "fps_logging" / "logger.py"),
        str(CORE / "dictionary" / "manager.py"),
        str(CORE / "rules" / "manager.py"),
        str(CORE / "rules" / "evaluator.py"),
        str(CORE / "rules" / "engine.py"),
    ]
    args = [sys.executable, "-m", "mypy", *targets,
            "--ignore-missing-imports", "--no-error-summary"]
    r = _run(args)
    return label, r.returncode, r.stdout + r.stderr


def run_quality_checks(
    do_lint: bool = True,
    do_format: bool = True,
    do_type: bool = True,
    verbose: bool = False,
) -> list[QualityResult]:
    print(header("── Quality Checks ──────────────────────────────────────"))
    print()
    results: list[QualityResult] = []

    checks: list[tuple[bool, object]] = [
        (do_lint,   run_lint),
        (do_format, run_format_check),
        (do_type,   run_typecheck),
    ]
    for enabled, fn in checks:
        if not enabled:
            continue
        label, code, output = fn(verbose)  # type: ignore[operator]
        icon = ok("PASS") if code == 0 else fail("FAIL")
        print(f"  {icon}  {label}")
        if code != 0 and output.strip():
            for line in output.strip().splitlines()[:10]:
                print(f"         {warn(line)}")
        elif verbose and output.strip() and code == 0:
            for line in output.strip().splitlines()[:5]:
                print(f"         {dim(line)}")
        results.append((label, code, output))

    print()
    return results


# ══════════════════════════════════════════════════════════════════
# TEST LIST
# ══════════════════════════════════════════════════════════════════

def list_tests() -> None:
    print(header("── Test Files ──────────────────────────────────────────"))
    print()
    r = _run([sys.executable, "-m", "pytest", str(UNIT),
              f"--pythonpath={CORE}", "--collect-only", "-q", "--no-header"])
    for line in r.stdout.splitlines():
        if "::" in line:
            parts = line.strip().split("::")
            file_  = Path(parts[0]).name
            class_ = parts[1] if len(parts) > 1 else ""
            test_  = parts[2] if len(parts) > 2 else ""
            print(f"  {dim(file_)}  \033[36m{class_}\033[0m::{test_}")
    print()


# ══════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════

def print_summary(
    smoke:   SmokeResults,
    passed:  int,
    failed:  int,
    elapsed: float,
    quality: list[QualityResult],
) -> None:
    print(bold("=" * 64))
    print(bold("  SUMMARY"))
    print(bold("=" * 64))
    print()

    s_pass    = sum(1 for v in smoke.values() if v[0] == "PASS")
    s_fail    = sum(1 for v in smoke.values() if v[0] == "FAIL")
    s_pending = sum(1 for v in smoke.values() if v[0] == "PENDING")
    q_fail    = sum(1 for _, c, _ in quality if c != 0)

    print(f"  Smoke Tests    {ok(f'{s_pass} PASS')}  "
          f"{fail(f'{s_fail} FAIL') if s_fail else dim('0 FAIL')}  "
          f"{dim(f'{s_pending} PENDING')}")
    print(f"  Unit Tests     {ok(f'{passed} PASS')}  "
          f"{fail(f'{failed} FAIL') if failed else dim('0 FAIL')}  "
          f"{dim(f'{elapsed:.2f}s')}")
    if quality:
        print(f"  Quality        "
              f"{ok(f'{len(quality)-q_fail} PASS')}  "
              f"{fail(f'{q_fail} FAIL') if q_fail else dim('0 FAIL')}")

    total_fail = s_fail + failed + q_fail
    print()
    if total_fail == 0:
        print(f"  {ok('ALL CHECKS PASSED')} ✅")
    else:
        print(f"  {fail(f'{total_fail} FAILURE(S) DETECTED')} ❌")
    print()

    # Sprint 1 実装状況
    print(bold("  Sprint 1 — Implementation Status"))
    print()
    steps = [
        ("Step 1",  "Repository Structure",    "✅ DONE",  "main"),
        ("Step 2",  "ConfigManager",            "✅ DONE",  "feature/config-manager"),
        ("Step 3",  "FPSLogger",                "✅ DONE",  "feature/logger"),
        ("Step CI", "CI / Dev Environment",     "✅ DONE",  "feature/ci-devenv"),
        ("Step 4",  "DictionaryManager",        "✅ DONE",  "feature/dictionary-manager"),
        ("Step 5",  "RuleManager",              "✅ DONE",  "feature/rule-manager"),
        ("Step 6",  "PresetManager",            "✅ DONE",  "feature/preset-manager"),
        ("Step 7",  "Cache",                    "✅ DONE",  "feature/cache"),
        ("Step 8",  "Backup",                   "✅ DONE",   "feature/backup"),
        ("Step 9",  "Pipeline (10-stage)",      "✅ DONE",   "feature/pipeline-adapter"),
        ("Step 10", "ComfyUI Adapter",          "✅ DONE",   "feature/pipeline-adapter"),
    ]
    for step, name, status, branch in steps:
        s = ok(status) if "DONE" in status else (
            info(status) if "NEXT" in status else dim(status))
        print(f"  {dim(step):<10} {name:<26} {s}  {dim(branch)}")

    print()
    print(bold("=" * 64))
    print()
    print(dim("  Quick commands:"))
    print(dim("    python main.py              全テスト"))
    print(dim("    python main.py --check      品質チェック"))
    print(dim("    python main.py --cov        カバレッジ付き"))
    print(dim("    python main.py --all        全チェック"))
    print(dim("    make help                   Makefile コマンド一覧"))
    print()


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Face Prompt Studio — Debug Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              python main.py            全テスト（smoke + unit）
              python main.py --all      全チェック（test + lint + format + typecheck）
              python main.py --smoke    スモークテストのみ
              python main.py --unit     ユニットテストのみ
              python main.py --cov      カバレッジ付きテスト
              python main.py --check    lint + format + typecheck
              python main.py --list     テスト一覧
              python main.py -v         詳細出力
        """),
    )
    parser.add_argument("--all",       action="store_true", help="全チェック実行")
    parser.add_argument("--smoke",     action="store_true", help="スモークテストのみ")
    parser.add_argument("--unit",      action="store_true", help="ユニットテストのみ")
    parser.add_argument("--cov",       action="store_true", help="カバレッジ付きテスト")
    parser.add_argument("--lint",      action="store_true", help="Ruff lint")
    parser.add_argument("--format",    action="store_true", help="Black フォーマットチェック")
    parser.add_argument("--typecheck", action="store_true", help="mypy 型チェック")
    parser.add_argument("--check",     action="store_true", help="lint + format + typecheck")
    parser.add_argument("--list",      action="store_true", help="テスト一覧")
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細出力")
    args = parser.parse_args()

    print_header()

    smoke_res: SmokeResults = {}
    quality_res: list[QualityResult] = []
    passed = failed = 0
    elapsed = 0.0

    if args.list:
        list_tests()
        return

    any_explicit = any([
        args.smoke, args.unit, args.cov, args.lint,
        args.format, args.typecheck, args.check, args.all,
    ])
    run_tests   = args.all or args.smoke or args.unit or args.cov or not any_explicit
    run_quality = args.all or args.check or args.lint or args.format or args.typecheck

    if run_tests or args.smoke:
        smoke_res = run_smoke_tests(args.verbose)
    if run_tests or args.unit or args.cov:
        passed, failed, elapsed = run_unit_tests(
            verbose=args.verbose,
            coverage=args.cov or args.all,
        )
    if run_quality or args.check:
        quality_res = run_quality_checks(
            do_lint   = args.all or args.check or args.lint,
            do_format = args.all or args.check or args.format,
            do_type   = args.all or args.check or args.typecheck,
            verbose   = args.verbose,
        )

    print_summary(smoke_res, passed, failed, elapsed, quality_res)

    total_fail = (
        sum(1 for v in smoke_res.values() if v[0] == "FAIL")
        + failed
        + sum(1 for _, c, _ in quality_res if c != 0)
    )
    sys.exit(1 if total_fail > 0 else 0)


if __name__ == "__main__":
    main()
