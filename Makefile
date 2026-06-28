# ══════════════════════════════════════════════════════════════════
#  Face Prompt Studio — Makefile
#  使い方: make <target>
# ══════════════════════════════════════════════════════════════════

PYTHON     := python
PYTEST     := $(PYTHON) -m pytest
CORE       := fps-core
TESTS      := fps-tools/tests
UNIT       := $(TESTS)/unit

.DEFAULT_GOAL := help

# ── ヘルプ ────────────────────────────────────────────────────────
.PHONY: help
help:
	@echo ""
	@echo "  Face Prompt Studio — Dev Commands"
	@echo ""
	@echo "  Setup"
	@echo "    make install        開発依存パッケージをインストール"
	@echo ""
	@echo "  Test"
	@echo "    make test           全テスト実行（推奨）"
	@echo "    make test-unit      ユニットテストのみ"
	@echo "    make test-cov       カバレッジレポート付き"
	@echo "    make debug          main.py デバッグランナー"
	@echo ""
	@echo "  Quality"
	@echo "    make lint           Ruff lint チェック"
	@echo "    make format         Black フォーマット"
	@echo "    make typecheck      mypy 型チェック"
	@echo "    make check          lint + format + typecheck 全実行"
	@echo ""
	@echo "  Clean"
	@echo "    make clean          キャッシュ・一時ファイル削除"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────
.PHONY: install
install:
	$(PYTHON) -m pip install -e ".[dev]" --break-system-packages 2>/dev/null || \
	$(PYTHON) -m pip install pytest pytest-cov black ruff mypy pyyaml --break-system-packages

# ── Test ──────────────────────────────────────────────────────────
.PHONY: test
test:
	$(PYTHON) main.py

.PHONY: test-unit
test-unit:
	$(PYTEST) $(UNIT) --pythonpath $(CORE) -v --tb=short

.PHONY: test-cov
test-cov:
	$(PYTEST) $(UNIT) --pythonpath $(CORE) \
		--cov=$(CORE) \
		--cov-report=term-missing \
		--cov-report=html:fps-tools/coverage \
		--cov-fail-under=80 \
		-v

# ── Quality ───────────────────────────────────────────────────────
.PHONY: lint
lint:
	$(PYTHON) -m ruff check $(CORE) --select E,F,W,I,UP,B

.PHONY: format
format:
	$(PYTHON) -m black $(CORE) --line-length 100

.PHONY: format-check
format-check:
	$(PYTHON) -m black $(CORE) --line-length 100 --check

.PHONY: typecheck
typecheck:
	$(PYTHON) -m mypy $(CORE) --ignore-missing-imports

.PHONY: check
check: lint format-check typecheck
	@echo ""
	@echo "  ✅ All quality checks passed."
	@echo ""

# ── Clean ─────────────────────────────────────────────────────────
.PHONY: clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache"   -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info"    -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache"   -exec rm -rf {} + 2>/dev/null || true
	rm -rf fps-tools/coverage
	@echo "  🧹 Cleaned."
