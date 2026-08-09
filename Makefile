# Custody. Everything here runs offline: the core is a pure function, so its
# whole contract is testable without a cloud account or an SDK.

# Prefer the project venv: the ADK conformance tests need google-adk, and they
# are the only thing standing between the duck-typed core and my own fiction.
PYTHON ?= $(shell \
	if [ -x .venv/bin/python ]; then \
		printf '%s' .venv/bin/python; \
	elif [ -x "$$(pyenv root 2>/dev/null)/versions/3.12.13/bin/python" ]; then \
		printf '%s' "$$(pyenv root)/versions/3.12.13/bin/python"; \
	elif command -v python3.12 >/dev/null 2>&1; then \
		command -v python3.12; \
	else \
		command -v python3; \
	fi)

.PHONY: help lint test check gates cost demo revoke isolate clean

help:
	@echo "make lint    ruff over the tree"
	@echo "make test    the offline suite ($(PYTHON))"
	@echo "make check   lint + test"
	@echo "make gates   PASS/FAIL per gate, judged from proof-out/"
	@echo "make cost    what a compromised tool costs, with the graph and without"
	@echo "make demo    the poisoning scenario, with Custody and without"
	@echo "make revoke  G3 offline: revoke a compromised tool across the graph"
	@echo "make isolate G4 offline: cross-department isolation, trust and quarantine"

lint:
	ruff check .

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

check: lint test

gates:
	@$(PYTHON) scripts/gates.py

cost:
	@$(PYTHON) scripts/cost.py

demo:
	@$(PYTHON) scripts/demo.py

revoke:
	@$(PYTHON) scripts/revoke.py

isolate:
	@$(PYTHON) scripts/isolate.py

clean:
	rm -rf .ruff_cache proof-out
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
