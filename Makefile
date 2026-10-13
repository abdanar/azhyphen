# Configuration

.DEFAULT_GOAL := help

PYTHON ?= python3
LUALATEX ?= lualatex
XELATEX ?= xelatex

# MSYS2's POSIX tools must precede Windows commands with the same name
# (notably find.exe). Leave the user's tool precedence unchanged on Unix.
ifeq ($(OS),Windows_NT)
export PATH := /usr/bin:$(PATH)
endif

-include local.mk

# Paths

PACKAGE_DIR := tex/latex/azhyphen
PATTERN_FILE := $(PACKAGE_DIR)/azhyphen.pat.txt
XETEX_LOADER := $(PACKAGE_DIR)/azhyphen-xetex.tex

SYNC_SCRIPT := scripts/sync_data.py
CHECK_SCRIPT := scripts/check_repository.py
VERSION_SCRIPT := scripts/update_version.py
XETEX_LANGUAGE_SCRIPT := scripts/xetex_language.py
VERIFY_INSTALL_SCRIPT := scripts/verify_install.sh

RUNTIME_REQUIRED := \
	$(PACKAGE_DIR)/azhyphen.sty \
	$(PACKAGE_DIR)/azhyphen.lua \
	$(PACKAGE_DIR)/azhyphen-version.tex

RUNTIME_OPTIONAL := $(PACKAGE_DIR)/azhyphen.hyp.txt

.PHONY: \
	help \
	version check-version \
	doc ctan release-check clean-dist \
	sync import \
	validate-state validate-data check \
	test test-lua test-xe test-real test-sync install-smoke \
	update \
	install uninstall \
	clean

# Help

help:
	@printf '%s\n' \
		'azhyphen development targets' \
		'' \
		'  make sync            Synchronize patterns, statistics, and generated files' \
		'  make update          Synchronize and run the complete validation pipeline' \
		'  make test            Run LuaLaTeX and XeLaTeX fixture/runtime tests' \
		'  make test-real       Test the bundled real patterns with both engines' \
		'  make test-sync       Test synchronization and generated-file tooling' \
		'  make validate-state  Validate synchronized generated state' \
		'  make check           Check generated state and repository consistency' \
		'  make doc             Compile the package manual in build/doc/' \
		'  make ctan            Build and validate dist/azhyphen-<VERSION>.zip' \
		'  make release-check   Run all tests and CTAN release validation' \
		'  make clean-dist      Remove generated release archives' \
		'  make install         Install and verify in the user TeX tree' \
		'  make uninstall       Remove azhyphen from the user TeX tree' \
		'  make clean           Remove generated test and TeX build artifacts' \
		'  make version         Refresh files generated from VERSION' \
		'' \
		'Data refreshes require PATTERNS=... and STATS=... (or local.mk).' \
		'Override PYTHON, LUALATEX, and XELATEX when alternate tools are needed.'

# Version generation

version:
	@$(PYTHON) $(VERSION_SCRIPT)

check-version:
	@$(PYTHON) $(VERSION_SCRIPT) --check


# Synchronization

sync:
	@test -n "$(PATTERNS)" || { \
		echo "error: configure PATTERNS in local.mk or on the make command line" >&2; \
		exit 2; \
	}
	@test -n "$(STATS)" || { \
		echo "error: configure STATS in local.mk or on the make command line" >&2; \
		exit 2; \
	}
	@$(PYTHON) $(SYNC_SCRIPT) \
		--patterns "$(PATTERNS)" \
		--stats "$(STATS)" \
		$(if $(SYNC_REPORT),--report "$(SYNC_REPORT)") \
		$(if $(SYNC_QUIET),--quiet)

# Backward-compatible alias.
import: sync

# Validation

validate-state:
	@$(PYTHON) $(CHECK_SCRIPT) --data-only $(if $(QUIET),--quiet)

# Backward-compatible alias.
validate-data: validate-state

check: check-version
	@$(PYTHON) $(CHECK_SCRIPT) \
		$(if $(PATTERNS),--source "$(PATTERNS)") \
		$(if $(STATS),--stats-source "$(STATS)") \
		$(if $(QUIET),--quiet)

# Tests

test: test-lua test-xe

test-lua:
	@LUALATEX="$(LUALATEX)" sh tests/run-tests.sh

test-xe:
	@LUALATEX="$(LUALATEX)" XELATEX="$(XELATEX)" \
		sh tests/run-xetex-tests.sh fixture

test-real: validate-state
	@LUALATEX="$(LUALATEX)" sh tests/run-real-tests.sh
	@LUALATEX="$(LUALATEX)" XELATEX="$(XELATEX)" \
		sh tests/run-xetex-tests.sh real

test-sync:
	@$(PYTHON) tests/test_xetex_language.py
	@$(PYTHON) tests/test_sync_data.py
	@$(PYTHON) tests/test_sync.py
	@$(PYTHON) tests/test_readme_stats.py
	@$(PYTHON) tests/test_version.py
	@$(PYTHON) tests/test_public_repository.py
	@$(PYTHON) tests/test_ctan.py

# Release construction never synchronizes data or modifies source files.
doc: check-version validate-state
	@$(PYTHON) scripts/build_ctan.py doc --lualatex "$(LUALATEX)"

ctan: check
	@$(PYTHON) scripts/build_ctan.py ctan --lualatex "$(LUALATEX)" --xelatex "$(XELATEX)"

# Sequential recursive calls also avoid competing format builds under make -j.
release-check:
	@$(MAKE) --no-print-directory test-sync
	@$(MAKE) --no-print-directory test
	@$(MAKE) --no-print-directory test-real
	@$(MAKE) --no-print-directory install-smoke
	@$(MAKE) --no-print-directory ctan
	@$(MAKE) --no-print-directory check
	@git diff --check
	@git diff --cached --check

clean-dist:
	@$(PYTHON) scripts/build_ctan.py clean-dist

install-smoke: validate-state
	@LUALATEX="$(LUALATEX)" XELATEX="$(XELATEX)" \
		sh tests/install-smoke.sh

# Full update pipeline

update:
	@test -n "$(PATTERNS)" || { \
		echo "error: configure PATTERNS in local.mk or run make update PATTERNS=..." >&2; \
		exit 2; \
	}
	@test -n "$(STATS)" || { \
		echo "error: configure STATS in local.mk or run make update STATS=..." >&2; \
		exit 2; \
	}
	@set -eu; \
	report="$$(mktemp "$${TMPDIR:-/tmp}/azhyphen-update.XXXXXX")"; \
	trap 'rm -f "$$report"' EXIT HUP INT TERM; \
	$(MAKE) --no-print-directory sync \
		PATTERNS="$(PATTERNS)" \
		STATS="$(STATS)" \
		SYNC_REPORT="$$report" \
		SYNC_QUIET=1; \
	$(MAKE) --no-print-directory validate-state QUIET=1; \
	$(MAKE) --no-print-directory test-sync; \
	$(MAKE) --no-print-directory test; \
	$(MAKE) --no-print-directory test-real QUIET=1; \
	$(MAKE) --no-print-directory install-smoke QUIET=1; \
	$(MAKE) --no-print-directory check \
		PATTERNS="$(PATTERNS)" \
		STATS="$(STATS)" \
		QUIET=1; \
	$(PYTHON) $(SYNC_SCRIPT) --print-report "$$report"; \
	printf '\n'; \
	printf '%s\n' \
		'✓ coordinated pattern and statistics synchronization' \
		'✓ synchronization and generated-file tooling tests' \
		'✓ canonical metadata, XeTeX loader, and README statistics' \
		'✓ generated package version and public release metadata' \
		'✓ LuaLaTeX and XeLaTeX fixture/runtime tests' \
		'✓ LuaLaTeX and XeLaTeX real-pattern tests' \
		'✓ user-level installation smoke test' \
		'✓ repository consistency' \
		'' \
		'azhyphen is up to date.'

# Installation

install: $(RUNTIME_REQUIRED)
	@test -s "$(PATTERN_FILE)" || { \
		echo "error: synchronize production patterns before installing (make sync)" >&2; \
		exit 1; \
	}
	@test -s "$(XETEX_LOADER)" || { \
		echo "error: generated XeTeX loader is missing (run make sync)" >&2; \
		exit 1; \
	}
	@$(PYTHON) $(CHECK_SCRIPT) --data-only --quiet
	@set -eu; \
	texmfhome="$$(kpsewhich -var-value=TEXMFHOME)"; \
	test -n "$$texmfhome" || { \
		echo "error: kpsewhich returned an empty TEXMFHOME" >&2; \
		exit 1; \
	}; \
	dest="$$texmfhome/tex/latex/azhyphen"; \
	mkdir -p "$$dest"; \
	install -m 0644 \
		$(RUNTIME_REQUIRED) \
		$(PATTERN_FILE) \
		$(XETEX_LOADER) \
		"$$dest/"; \
	if test -f "$(RUNTIME_OPTIONAL)"; then \
		install -m 0644 "$(RUNTIME_OPTIONAL)" "$$dest/"; \
	fi; \
	$(PYTHON) $(XETEX_LANGUAGE_SCRIPT) install --texmfhome "$$texmfhome"; \
	echo "Installed azhyphen in $$dest"
	@LUALATEX="$(LUALATEX)" XELATEX="$(XELATEX)" \
		sh $(VERIFY_INSTALL_SCRIPT)

uninstall:
	@set -eu; \
	texmfhome="$$(kpsewhich -var-value=TEXMFHOME)"; \
	test -n "$$texmfhome" || { \
		echo "error: kpsewhich returned an empty TEXMFHOME" >&2; \
		exit 1; \
	}; \
	$(PYTHON) $(XETEX_LANGUAGE_SCRIPT) uninstall --texmfhome "$$texmfhome"; \
	dest="$$texmfhome/tex/latex/azhyphen"; \
	rm -f \
		"$$dest/azhyphen.sty" \
		"$$dest/azhyphen.lua" \
		"$$dest/azhyphen-version.tex" \
		"$$dest/azhyphen.pat.txt" \
		"$$dest/azhyphen.hyp.txt" \
		"$$dest/azhyphen-xetex.tex" \
		"$$dest/.azhyphen-xetex-state.json" \
		"$$dest/.azhyphen-language.dat.backup"; \
	rmdir "$$dest" 2>/dev/null || true; \
	echo "Removed installed azhyphen files from $$dest"

# Cleanup

clean:
	@$(PYTHON) scripts/build_ctan.py clean
	@set -eu; \
	for input in tests/*.tex; do \
		name="$${input##*/}"; name="$${name%.tex}"; \
		for directory in . tests; do \
			for suffix in aux log out pdf xdv dvi fmt fls toc synctex.gz fdb_latexmk; do \
				rm -f "$$directory/$$name.$$suffix"; \
			done; \
		done; \
	done
	@find scripts tests -type d -name __pycache__ -prune -exec rm -rf {} +
	@find . -not -path './.git/*' -type f \
		\( \
			-name '.azhyphen*.tmp' \
			-o -name '.model-stats.json.*.tmp' \
			-o -name '.README.md.*.tmp' \
		\) -delete
