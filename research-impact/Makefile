# Keel. Its own targets, its own interpreter, its own proof directory. Nothing
# here reaches outside this directory, because the other project in this
# repository has to keep working exactly as it did.

PYTHON ?= python3

# The benchmark's live leg needs the Vertex SDK, which the engine deliberately
# does not. LIVE_PYTHON points at an interpreter that has it.
LIVE_PYTHON ?= ../.venv/bin/python
KEEL_PROJECT ?= project-988bc9fe-092c-4b32-90c

.PHONY: help lint test check gate judge all bench-stub bench-dev \
	lock-holdout bench-holdout bench-judge clean

help:
	@echo "make check       lint + the offline suite"
	@echo "make gate        run the phase 2 loop, write proof-out/phase2.json"
	@echo "make judge       read that artifact back, PASS/FAIL per gate"
	@echo "make all         check, gate, judge, in that order"
	@echo "make bench-stub    F1 harness offline, no calls, no result"
	@echo "make bench-dev     F1 dev suite live, frozen, diagnosis only"
	@echo "make lock-holdout  recompute and hash the holdout ground truth"
	@echo "make bench-holdout F1 holdout live, four configurations"
	@echo "make bench-judge   recompute both from the raw model answers"

lint:
	ruff check keel bench scripts tests

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

check: lint test

gate:
	$(PYTHON) scripts/phase2_gate.py

judge:
	$(PYTHON) scripts/phase2_judge.py

all: check gate judge

bench-stub:
	$(PYTHON) scripts/f1_bench.py --mode stub --suite holdout --runs 3 \
		--configs A:v1,A:v2,B:v1,B:v2

# The dev suite. Frozen: it diagnosed the boundary failure, so it may never be
# the source of a headline number again. Re-runnable, never re-tuned against.
bench-dev:
	$(LIVE_PYTHON) scripts/f1_bench.py --mode live --suite dev --runs 3 \
		--workers 5 --project $(KEEL_PROJECT) --configs A:v1,B:v1

lock-holdout:
	$(PYTHON) scripts/lock_holdout.py

bench-holdout:
	$(LIVE_PYTHON) scripts/f1_bench.py --mode live --suite holdout --runs 3 \
		--workers 6 --project $(KEEL_PROJECT) --configs A:v1,A:v2,B:v1,B:v2

bench-judge:
	$(PYTHON) scripts/f1_judge.py proof-out/f1-dev.json
	$(PYTHON) scripts/f1_judge.py proof-out/f1-holdout.json

clean:
	rm -rf proof-out/*.json
