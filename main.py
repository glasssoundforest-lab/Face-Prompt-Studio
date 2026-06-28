"""
main.py — Face Prompt Studio デバッグ・テスト実行エントリポイント

使い方:
  python main.py              # 全テスト実行
  python main.py --unit       # ユニットテストのみ
  python main.py --smoke      # スモークテスト（動作確認）
  python main.py --list       # テスト一覧表示
  python main.py -v           # 詳細出力
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
import time
from pathlib import Path

# ── パス設定 ──────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent
CORE     = ROOT / "fps-core"
TESTS    = ROOT / "fps-tools" / "tests"
UNIT     = TESTS / "unit"

sys.path.insert(0, str(CORE))


# ══════════════════════════════════════════════════════════════════════
# ANSI カラー
# ══════════════════════════════════════════════════════════════════════

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_GREY   = "\033[90m"

def ok(s):    return f"{_GREEN}{_BOLD}{s}{_RESET}"
def fail(s):  return f"{_RED}{_BOLD}{s}{_RESET}"
def warn(s):  return f"{_YELLOW}{s}{_RESET}"
def info(s):  return f"{_CYAN}{s}{_RESET}"
def dim(s):   return f"{_GREY}{s}{_RESET}"
def bold(s):  return f"{_BOLD}{s}{_RESET}"


# ══════════════════════════════════════════════════════════════════════
# ヘッダー表示
# ══════════════════════════════════════════════════════════════════════

def print_header():
    print()
    print(bold("=" * 62))
    print(bold("  Face Prompt Studio — Debug Runner"))
    print(bold("  v0.2.0-dev / Sprint 1"))
    print(bold("=" * 62))
    print()


# ══════════════════════════════════════════════════════════════════════
# スモークテスト（コンポーネント単体の生死確認）
# ══════════════════════════════════════════════════════════════════════

def run_smoke_tests(verbose: bool = False) -> dict:
    """各コンポーネントが import・基本動作できるか確認する"""
    results = {}

    print(info("── Smoke Tests ──────────────────────────────────────────"))
    print()

    # ── Step 2: ConfigManager ─────────────────────────────────────
    label = "Step 2  ConfigManager"
    try:
        from config.manager import ConfigManager, ConfigError

        cm = ConfigManager()
        cm.set("test.key", "hello")
        assert cm.get("test.key") == "hello"
        assert cm.get("missing", "default") == "default"

        # デフォルト設定ファイルがあれば読み込む
        default_cfg = ROOT / "fps-data" / "config.default.json"
        if default_cfg.exists():
            cm2 = ConfigManager(default_path=default_cfg)
            version = cm2.get("fps.version")
            if verbose:
                print(dim(f"    fps.version = {version}"))
            assert version is not None

        results[label] = ("PASS", None)
        print(f"  {ok('PASS')}  {label}")
    except Exception as e:
        results[label] = ("FAIL", str(e))
        print(f"  {fail('FAIL')}  {label}")
        print(f"         {warn(str(e))}")

    # ── Step 3: FPSLogger ─────────────────────────────────────────
    label = "Step 3  FPSLogger"
    try:
        import tempfile, logging as _logging
        from fps_logging.logger import FPSLogger, get_logger

        # シングルトンリセット
        FPSLogger._instance = None
        root = _logging.getLogger("fps")
        root.handlers.clear()

        with tempfile.TemporaryDirectory() as td:
            fl = FPSLogger()
            fl.setup(log_dir=td, level="DEBUG", to_console=False, to_file=True)
            logger = fl.get("smoke")
            logger.info("smoke test")
            _logging.getLogger("fps").handlers[0].flush()
            log_file = Path(td) / "fps.log"
            assert log_file.exists()
            content = log_file.read_text()
            assert "smoke test" in content
            if verbose:
                print(dim(f"    log: {log_file.name} OK"))

        results[label] = ("PASS", None)
        print(f"  {ok('PASS')}  {label}")

        # クリーンアップ
        FPSLogger._instance = None
        root = _logging.getLogger("fps")
        root.handlers.clear()

    except Exception as e:
        results[label] = ("FAIL", str(e))
        print(f"  {fail('FAIL')}  {label}")
        print(f"         {warn(str(e))}")

    # ── 未実装コンポーネントのプレースホルダー ──────────────────
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


# ══════════════════════════════════════════════════════════════════════
# ユニットテスト（pytest 呼び出し）
# ══════════════════════════════════════════════════════════════════════

def run_unit_tests(verbose: bool = False) -> tuple[int, int, float]:
    """pytest を subprocess で実行してユニットテストを走らせる"""
    print(info("── Unit Tests ───────────────────────────────────────────"))
    print()

    test_files = sorted(UNIT.glob("test_*.py"))
    if not test_files:
        print(warn("  テストファイルが見つかりません: fps-tools/tests/unit/test_*.py"))
        print()
        return 0, 0, 0.0

    if verbose:
        for f in test_files:
            print(dim(f"  {f.relative_to(ROOT)}"))
        print()

    args = [
        sys.executable, "-m", "pytest",
        str(UNIT),
        "-v" if verbose else "-q",
        "--tb=short",
        "--no-header",
        f"--rootdir={ROOT}",
    ]

    start = time.perf_counter()
    result = subprocess.run(args, capture_output=not verbose, text=True)
    elapsed = time.perf_counter() - start

    output = result.stdout or ""
    stderr = result.stderr or ""

    # 結果行を抽出
    passed = failed = 0
    for line in output.splitlines():
        if "passed" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "passed":
                    try: passed = int(parts[i - 1])
                    except: pass
                if p == "failed":
                    try: failed = int(parts[i - 1])
                    except: pass

    if not verbose:
        # コンパクト表示：FAILした場合は詳細を出す
        if result.returncode != 0:
            print(output)
            if stderr:
                print(stderr)
        else:
            # テスト名を1行ずつ表示
            for line in output.splitlines():
                if "PASSED" in line:
                    name = line.split("::")[1].split(" ")[0] if "::" in line else line
                    print(f"  {ok('✓')} {dim(name)}")
                elif "FAILED" in line:
                    print(f"  {fail('✗')} {line}")
            print()

    return passed, failed, elapsed


# ══════════════════════════════════════════════════════════════════════
# テスト一覧表示
# ══════════════════════════════════════════════════════════════════════

def list_tests():
    print(info("── Test Files ───────────────────────────────────────────"))
    print()
    test_files = sorted(UNIT.glob("test_*.py"))
    if not test_files:
        print(warn("  テストファイルなし"))
        return

    args = [
        sys.executable, "-m", "pytest",
        str(UNIT), "--collect-only", "-q", "--no-header",
        f"--rootdir={ROOT}",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if "::" in line:
            parts = line.strip().split("::")
            file_  = parts[0].replace("fps-tools/tests/unit/", "")
            class_ = parts[1] if len(parts) > 1 else ""
            test_  = parts[2] if len(parts) > 2 else ""
            print(f"  {dim(file_)}  {_CYAN}{class_}{_RESET}::{test_}")
    print()


# ══════════════════════════════════════════════════════════════════════
# サマリー表示
# ══════════════════════════════════════════════════════════════════════

def print_summary(smoke: dict, passed: int, failed: int, elapsed: float):
    print(bold("=" * 62))
    print(bold("  SUMMARY"))
    print(bold("=" * 62))
    print()

    # スモークテスト集計
    s_pass    = sum(1 for v in smoke.values() if v[0] == "PASS")
    s_fail    = sum(1 for v in smoke.values() if v[0] == "FAIL")
    s_pending = sum(1 for v in smoke.values() if v[0] == "PENDING")

    print(f"  Smoke Tests  : "
          f"{ok(f'{s_pass} PASS')}  "
          f"{(fail(f'{s_fail} FAIL') if s_fail else dim('0 FAIL'))}  "
          f"{dim(f'{s_pending} PENDING')}")

    print(f"  Unit Tests   : "
          f"{ok(f'{passed} PASS')}  "
          f"{(fail(f'{failed} FAIL') if failed else dim('0 FAIL'))}  "
          f"{dim(f'{elapsed:.2f}s')}")

    total_fail = s_fail + failed
    print()
    if total_fail == 0:
        print(f"  {ok('ALL TESTS PASSED')} ✅")
    else:
        print(f"  {fail(f'{total_fail} FAILURE(S) DETECTED')} ❌")
    print()

    # 実装状況
    print(bold("  Sprint 1 — Implementation Status"))
    print()
    steps = [
        ("Step 1", "Repository Structure",  "✅ DONE",    "main"),
        ("Step 2", "ConfigManager",         "✅ DONE",    "feature/config-manager"),
        ("Step 3", "FPSLogger",             "✅ DONE",    "feature/logger"),
        ("Step 4", "DictionaryManager",     "🔲 NEXT",    "—"),
        ("Step 5", "RuleManager",           "🔲 TODO",    "—"),
        ("Step 6", "PresetManager",         "🔲 TODO",    "—"),
        ("Step 7", "Cache",                 "🔲 TODO",    "—"),
        ("Step 8", "Backup",                "🔲 TODO",    "—"),
        ("Step 9", "Pipeline (10-stage)",   "🔲 TODO",    "—"),
        ("Step 10","ComfyUI Adapter",       "🔲 TODO",    "—"),
    ]
    for step, name, status, branch in steps:
        status_str = ok(status) if "DONE" in status else (
            info(status) if "NEXT" in status else dim(status)
        )
        print(f"  {dim(step):<10} {name:<24} {status_str}  {dim(branch)}")
    print()
    print(bold("=" * 62))
    print()


# ══════════════════════════════════════════════════════════════════════
# エントリポイント
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Face Prompt Studio — Debug Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              python main.py            全テスト実行
              python main.py --smoke    スモークテストのみ
              python main.py --unit     ユニットテストのみ
              python main.py --list     テスト一覧表示
              python main.py -v         詳細出力
        """),
    )
    parser.add_argument("--smoke",  action="store_true", help="スモークテストのみ実行")
    parser.add_argument("--unit",   action="store_true", help="ユニットテストのみ実行")
    parser.add_argument("--list",   action="store_true", help="テスト一覧を表示")
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細出力")
    args = parser.parse_args()

    print_header()

    smoke_results = {}
    passed = failed = 0
    elapsed = 0.0

    if args.list:
        list_tests()
        return

    if args.smoke:
        smoke_results = run_smoke_tests(args.verbose)
    elif args.unit:
        passed, failed, elapsed = run_unit_tests(args.verbose)
    else:
        # デフォルト: 全実行
        smoke_results = run_smoke_tests(args.verbose)
        passed, failed, elapsed = run_unit_tests(args.verbose)

    print_summary(smoke_results, passed, failed, elapsed)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
