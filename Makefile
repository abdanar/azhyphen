# Friendly shortcuts; every operation is implemented in portable Python.
PYTHON ?= python3
.PHONY: update test check stats ctan clean install uninstall
update test check stats ctan clean install uninstall:
	$(PYTHON) scripts/azhyphen.py $@
