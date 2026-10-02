PYTHON ?= python3
LUALATEX ?= lualatex
XELATEX ?= xelatex

-include local.mk

PACKAGE_DIR := tex/latex/azhyphen
PATTERN_FILE := $(PACKAGE_DIR)/azhyphen.pat.txt
RUNTIME_REQUIRED := $(PACKAGE_DIR)/azhyphen.sty $(PACKAGE_DIR)/azhyphen.lua
RUNTIME_OPTIONAL := $(PACKAGE_DIR)/azhyphen.hyp.txt
XETEX_LOADER := $(PACKAGE_DIR)/azhyphen-xetex.tex

.PHONY: sync import validate-data test test-lua test-xe test-real \
	install-smoke check update test-sync clean install uninstall

sync:
	@test -n "$(PATTERNS)" || { \
		echo "error: configure PATTERNS in local.mk or on the make command line" >&2; \
		exit 2; \
	}
	@$(PYTHON) scripts/import_patterns.py "$(PATTERNS)" \
		$(if $(SYNC_REPORT),--report "$(SYNC_REPORT)") \
		$(if $(SYNC_QUIET),--quiet)

import: sync

validate-data:
	@$(PYTHON) scripts/check_repository.py --data-only $(if $(QUIET),--quiet)

test: test-lua test-xe

test-lua:
	@LUALATEX="$(LUALATEX)" sh tests/run-tests.sh

test-real: validate-data
	@LUALATEX="$(LUALATEX)" sh tests/run-real-tests.sh
	@LUALATEX="$(LUALATEX)" XELATEX="$(XELATEX)" \
		sh tests/run-xetex-tests.sh real

test-xe:
	@LUALATEX="$(LUALATEX)" XELATEX="$(XELATEX)" \
		sh tests/run-xetex-tests.sh fixture

install-smoke: validate-data
	@LUALATEX="$(LUALATEX)" XELATEX="$(XELATEX)" sh tests/install-smoke.sh

check:
	@$(PYTHON) scripts/check_repository.py \
		$(if $(PATTERNS),--source "$(PATTERNS)") $(if $(QUIET),--quiet)

update:
	@test -n "$(PATTERNS)" || { \
		echo "error: configure PATTERNS in local.mk or run make update PATTERNS=..." >&2; \
		exit 2; \
	}
	@set -eu; \
	report="$$(mktemp "$${TMPDIR:-/tmp}/azhyphen-update.XXXXXX")"; \
	trap 'rm -f "$$report"' EXIT HUP INT TERM; \
	$(MAKE) --no-print-directory sync PATTERNS="$(PATTERNS)" \
		SYNC_REPORT="$$report" SYNC_QUIET=1; \
	$(MAKE) --no-print-directory validate-data QUIET=1; \
	$(MAKE) --no-print-directory test; \
	$(MAKE) --no-print-directory test-real QUIET=1; \
	$(MAKE) --no-print-directory install-smoke QUIET=1; \
	$(MAKE) --no-print-directory check PATTERNS="$(PATTERNS)" QUIET=1; \
	$(PYTHON) scripts/import_patterns.py --print-report "$$report"; \
	printf '\n'; \
	printf '%s\n' \
		'✓ data validation' \
		'✓ pattern synchronization' \
		'✓ metadata' \
		'✓ deterministic XeTeX loader' \
		'✓ LuaLaTeX fixture/runtime tests' \
		'✓ XeLaTeX fixture/runtime tests' \
		'✓ LuaLaTeX and XeLaTeX real-pattern tests' \
		'✓ installation smoke test' \
		'✓ repository consistency' \
		'' \
		'azhyphen is up to date.'

test-sync:
	@$(PYTHON) tests/test_sync.py

clean:
	@find . -not -path './.git/*' -type f \
		\( -name '*.aux' -o -name '*.log' -o -name '*.out' \
		-o -name '*.pdf' -o -name '*.xdv' -o -name '*.dvi' \
		-o -name '*.fmt' -o -name '*.fls' -o -name '*.toc' \
		-o -name '*.synctex.gz' \) -delete
	@find scripts tests -type d -name __pycache__ -prune -exec rm -rf {} +
	@find "$(PACKAGE_DIR)" -maxdepth 1 -type f \
		\( -name '.azhyphen*.tmp' -o -name 'azhyphen*.tmp' \) -delete

install: $(RUNTIME_REQUIRED)
	@test -s "$(PATTERN_FILE)" || { \
		echo "error: synchronize production patterns before installing (make sync)" >&2; \
		exit 1; \
	}
	@test -s "$(XETEX_LOADER)" || { \
		echo "error: generated XeTeX loader is missing (run make sync)" >&2; \
		exit 1; \
	}
	@$(PYTHON) scripts/check_repository.py --data-only --quiet
	@set -e; \
	texmfhome="$$(kpsewhich -var-value=TEXMFHOME)"; \
	test -n "$$texmfhome" || { echo "error: kpsewhich returned an empty TEXMFHOME" >&2; exit 1; }; \
	dest="$$texmfhome/tex/latex/azhyphen"; \
	mkdir -p "$$dest"; \
	install -m 0644 $(RUNTIME_REQUIRED) $(PATTERN_FILE) $(XETEX_LOADER) "$$dest/"; \
	if test -f "$(RUNTIME_OPTIONAL)"; then install -m 0644 "$(RUNTIME_OPTIONAL)" "$$dest/"; fi; \
	$(PYTHON) scripts/xetex_language.py install --texmfhome "$$texmfhome"; \
	echo "Installed azhyphen in $$dest"
	@LUALATEX="$(LUALATEX)" XELATEX="$(XELATEX)" sh scripts/verify_install.sh

uninstall:
	@set -e; \
	texmfhome="$$(kpsewhich -var-value=TEXMFHOME)"; \
	test -n "$$texmfhome" || { echo "error: kpsewhich returned an empty TEXMFHOME" >&2; exit 1; }; \
	$(PYTHON) scripts/xetex_language.py uninstall --texmfhome "$$texmfhome"; \
	dest="$$texmfhome/tex/latex/azhyphen"; \
	rm -f "$$dest/azhyphen.sty" "$$dest/azhyphen.lua" \
		"$$dest/azhyphen.pat.txt" "$$dest/azhyphen.hyp.txt" \
		"$$dest/azhyphen-xetex.tex" \
		"$$dest/.azhyphen-xetex-state.json" \
		"$$dest/.azhyphen-language.dat.backup"; \
	rmdir "$$dest" 2>/dev/null || true; \
	echo "Removed installed azhyphen files from $$dest"
