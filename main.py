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

def ok(s):      return f"\033[32m{_BOLD}{s}{_R}"
def fail(s):    return f"\033[31m{_BOLD}{s}{_R}"
def warn(s):    return f"\033[33m{s}{_R}"
def info(s):    return f"\033[36m{s}{_R}"
def dim(s):     return f"\033[90m{s}{_R}"
def bold(s):    return f"{_BOLD}{s}{_R}"
def header(s):  return f"\033[34m{_BOLD}{s}{_R}"


# ══════════════════════════════════════════════════════════════════
# ユーティリティ
# ══════════════════════════════════════════════════════════════════

def _run(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=capture, text=True)


def _tool_available(tool: str) -> bool:
    r = _run([sys.executable, "-m", tool, "--version"])
    return r.returncode == 0


def print_header():
    print()
    print(bold("=" * 64))
    print(bold("  Face Prompt Studio — Debug Runner"))
    print(bold("  v0.5.0-planning  |  Sprint 1"))
    print(bold("=" * 64))
    print()


# ══════════════════════════════════════════════════════════════════
# SMOKE TESTS — コンポーネント生死確認
# ══════════════════════════════════════════════════════════════════

def run_smoke_tests(verbose: bool = False) -> dict[str, tuple[str, str | None]]:
    print(header("── Smoke Tests ─────────────────────────────────────────"))
    print()
    results: dict[str, tuple[str, str | None]] = {}

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
        results[label] = ("PASS", None)
        print(f"  {ok('PASS')}  {label}")
    except Exception as e:
        results[label] = ("FAIL", str(e))
        print(f"  {fail('FAIL')}  {label}")
        if verbose:
            print(f"         {warn(str(e))}")

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
            logger = fl.get("smoke")
            logger.info("smoke test")
            _log.getLogger("fps").handlers[0].flush()
            content = (Path(td) / "fps.log").read_text()
            assert "smoke test" in content
            if verbose:
                print(dim("    fps.log 書き込み確認 OK"))

        FPSLogger._instance = None
        _log.getLogger("fps").handlers.clear()
        results[label] = ("PASS", None)
        print(f"  {ok('PASS')}  {label}")
    except Exception as e:
        results[label] = ("FAIL", str(e))
        print(f"  {fail('FAIL')}  {label}")
        if verbose:
            print(f"         {warn(str(e))}")

    # ── Step 4〜10: 未実装プレースホルダー ────────────────────
    pending = [
        "Step 4  DictionaryManager",
        "Step 5  RuleManager",
        "Step 6  PresetManager",
        "Step 7  Cache",
        "Step 8  Backup",
        "Step 9  Pipeline (10-stage)",
        "Step 10 ComfyUI Adapter",
    ]
    for label in pending:
        results[label] = ("PENDING", None)
        print(f"  {dim('----')}  {dim(label)}  {dim('(未実装)')}")

    print()
    return results


# ══════════════════════════════════════════════════════════════════
# UNIT TESTS — pytest 実行
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
            "--cov-fail-under=80",
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
                except: pass
            if p == "failed":
                try: failed = int(parts[i - 1])
                except: pass

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
# QUALITY CHECKS — lint / format / typecheck
# ══════════════════════════════════════════════════════════════════

QualityResult = tuple[str, int, str]   # (label, returncode, output)


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
    args = [sys.executable, "-m", "mypy",
            str(CORE / "config" / "manager.py"),
            str(CORE / "fps_logging" / "logger.py"),
            "--ignore-missing-imports",
            "--no-error-summary"]
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
        icon  = ok("PASS") if code == 0 else fail("FAIL")
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

def list_tests():
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
    smoke:   dict[str, tuple[str, str | None]],
    passed:  int,
    failed:  int,
    elapsed: float,
    quality: list[QualityResult],
):
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
        ("Step 1",  "Repository Structure",    "✅ DONE",    "main"),
        ("Step 2",  "ConfigManager",            "✅ DONE",    "feature/config-manager"),
        ("Step 3",  "FPSLogger",                "✅ DONE",    "feature/logger"),
        ("Step 4",  "DictionaryManager",        "🔲 NEXT",    "feature/dictionary-manager"),
        ("Step 5",  "RuleManager",              "🔲 TODO",    "—"),
        ("Step 6",  "PresetManager",            "🔲 TODO",    "—"),
        ("Step 7",  "Cache",                    "🔲 TODO",    "—"),
        ("Step 8",  "Backup",                   "🔲 TODO",    "—"),
        ("Step 9",  "Pipeline (10-stage)",      "🔲 TODO",    "—"),
        ("Step 10", "ComfyUI Adapter",          "🔲 TODO",    "—"),
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

def main():
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
              python main.py --lint     Ruff lint
              python main.py --format   Black フォーマットチェック
              python main.py --typecheck mypy 型チェック
              python main.py --check    lint + format + typecheck
              python main.py --list     テスト一覧
              python main.py -v         詳細出力
        """),
    )
    parser.add_argument("--all",        action="store_true", help="全チェック実行")
    parser.add_argument("--smoke",      action="store_true", help="スモークテストのみ")
    parser.add_argument("--unit",       action="store_true", help="ユニットテストのみ")
    parser.add_argument("--cov",        action="store_true", help="カバレッジ付きテスト")
    parser.add_argument("--lint",       action="store_true", help="Ruff lint")
    parser.add_argument("--format",     action="store_true", help="Black フォーマットチェック")
    parser.add_argument("--typecheck",  action="store_true", help="mypy 型チェック")
    parser.add_argument("--check",      action="store_true", help="lint + format + typecheck")
    parser.add_argument("--list",       action="store_true", help="テスト一覧")
    parser.add_argument("-v","--verbose",action="store_true", help="詳細出力")
    args = parser.parse_args()

    print_header()

    smoke_res: dict[str, tuple[str, str | None]] = {}
    quality_res: list[QualityResult] = []
    passed = failed = 0
    elapsed = 0.0

    if args.list:
        list_tests()
        return

    # モード振り分け
    run_tests   = args.all or args.smoke or args.unit or args.cov or not any([
        args.smoke, args.unit, args.cov, args.lint,
        args.format, args.typecheck, args.check, args.all,
    ])
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
