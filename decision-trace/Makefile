PYTHON ?= $(shell \
	if [ -x .venv/bin/python ]; then \
		printf '%s' .venv/bin/python; \
	else \
		command -v python3; \
	fi)

.PHONY: help check test test-live demo

help:
	@echo "make check      deterministic release tests + authority-proof demo"
	@echo "make test       tests that need no network or cloud credentials"
	@echo "make test-live  explicitly credentialed integration tests"
	@echo "make demo       emit a proof from the frozen evidence corpus"

check: test demo

test:
	$(PYTHON) -m pytest -m "not live" -q

test-live:
	$(PYTHON) -m pytest -m live -v

demo:
	$(PYTHON) scripts/release_demo.py
