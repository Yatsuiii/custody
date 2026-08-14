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

.PHONY: help lint test check serve image gates cost demo revoke isolate revision-spike live-memory-bank live-memory-deletion memory-deletion-gates live-auditor auditor-gates live-review review-gates live-g1 live-registry-attack registry-gates live-revision-binding revision-binding-gates setup-gateway deploy-gateway-probe live-gateway gateway-gates live-model-armor model-armor-gates live-observability observability-gates clean

help:
	@echo "make lint    ruff over the tree"
	@echo "make test    the offline suite ($(PYTHON))"
	@echo "make check   lint + test"
	@echo "make serve   the control plane locally on :8080"
	@echo "make image   build the Cloud Run container and check the pins hold"
	@echo "make gates   PASS/FAIL per gate, judged from proof-out/"
	@echo "make cost    what a compromised tool costs, with the graph and without"
	@echo "make demo    the poisoning scenario, with Custody and without"
	@echo "make revoke  G3 offline: revoke a compromised tool across the graph"
	@echo "make isolate G4 offline: cross-department isolation, trust and quarantine"
	@echo "make revision-spike five-gate versioned tool-surface experiment"
	@echo "make live-memory-bank live ADK -> Custody -> Vertex Memory Bank proof"
	@echo "make live-memory-deletion prove D2: selective deletion via memory_id-pinned writes"
	@echo "make memory-deletion-gates independently judge the live memory-deletion artifact"
	@echo "make live-auditor prove the real Provenance Auditor: demote now, revoke later, async"
	@echo "make auditor-gates independently judge the live Auditor artifact"
	@echo "make live-review prove the real Custody Reviewer: Gemini reads a quarantined item, drafts a verdict"
	@echo "make review-gates independently judge the live Reviewer artifact"
	@echo "make live-g1 Cloud Run + Gemini 3.5 + ADK/Memory Bank evidence"
	@echo "make live-registry-attack deploy v1/v2 and prove stale Registry blocking"
	@echo "make registry-gates independently judge the live Registry artifact"
	@echo "make live-revision-binding prove R2: dispatch bound to the tools/list that authorized it"
	@echo "make revision-binding-gates independently judge the live revision-binding artifact"
	@echo "make setup-gateway import the three owned Gateway policy resources"
	@echo "make deploy-gateway-probe deploy/update the identity-bound Runtime probe"
	@echo "make live-gateway prove enforced Agent Gateway allow/deny controls"
	@echo "make gateway-gates independently judge the live Gateway artifact"
	@echo "make live-model-armor prove Model Armor blocks a jailbreak, allows clean"
	@echo "make model-armor-gates independently judge the live Model Armor artifact"
	@echo "make live-observability prove a trace carries the admitted custody digest"
	@echo "make observability-gates independently judge the live Observability artifact"

lint:
	ruff check .

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

check: lint test

serve:
	@$(PYTHON) -m custody.control_plane

image:
	docker build -t custody:local .

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

revision-spike:
	@$(PYTHON) scripts/revision_spike.py

live-memory-bank:
	@$(PYTHON) scripts/live_memory_bank.py

live-memory-deletion:
	@$(PYTHON) scripts/live_memory_deletion.py

memory-deletion-gates:
	@$(PYTHON) scripts/memory_deletion_gates.py

live-auditor:
	@$(PYTHON) scripts/live_auditor.py

auditor-gates:
	@$(PYTHON) scripts/auditor_gates.py

live-review:
	@$(PYTHON) scripts/live_review.py

review-gates:
	@$(PYTHON) scripts/review_gates.py

live-g1:
	@$(PYTHON) scripts/live_g1.py

live-registry-attack:
	@$(PYTHON) scripts/live_registry_attack.py

registry-gates:
	@$(PYTHON) scripts/registry_gates.py

live-revision-binding:
	@$(PYTHON) scripts/live_revision_binding.py

revision-binding-gates:
	@$(PYTHON) scripts/revision_binding_gates.py

setup-gateway:
	@$(PYTHON) scripts/setup_gateway.py

deploy-gateway-probe:
	@$(PYTHON) scripts/deploy_gateway_probe.py

live-gateway:
	@$(PYTHON) scripts/live_gateway.py

gateway-gates:
	@$(PYTHON) scripts/gateway_gates.py

live-model-armor:
	@$(PYTHON) scripts/live_model_armor.py

model-armor-gates:
	@$(PYTHON) scripts/model_armor_gates.py

live-observability:
	@$(PYTHON) scripts/live_observability.py

observability-gates:
	@$(PYTHON) scripts/observability_gates.py

clean:
	rm -rf .ruff_cache proof-out
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
