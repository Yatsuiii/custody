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

.PHONY: help lint test check hardening-check serve image gates verify-deploy incident gui cost demo revoke isolate revision-spike live-memory-bank live-memory-deletion memory-deletion-gates live-auditor auditor-gates live-review review-gates live-onboarding onboarding-gates live-escalation escalation-gates live-narration narration-gates live-fleet fleet-gates live-chain chain-gates live-g1 live-registry-attack registry-gates live-revision-binding revision-binding-gates setup-gateway deploy-gateway-probe live-gateway gateway-gates live-model-armor model-armor-gates live-observability observability-gates clean

help:
	@echo "make lint    ruff over the tree"
	@echo "make test    the offline suite ($(PYTHON))"
	@echo "make check   lint + test"
	@echo "make hardening-check  check + deterministic incident/demo preflight"
	@echo "make serve   the control plane locally on :8080"
	@echo "make image   build the Cloud Run container and check the pins hold"
	@echo "make gates   PASS/FAIL per gate, judged from proof-out/"
	@echo "make verify-deploy  what the deployed pages actually serve, vs the local build"
	@echo "make incident  the judge-facing narrative: trust incident, blast radius, lineage, revoke, evidence"
	@echo "make gui       renders web/incident.html, same data as make incident, open in a browser"
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
	@echo "make live-onboarding prove Gemini drafts a vouch request without granting it"
	@echo "make onboarding-gates independently judge the live Onboarding artifact"
	@echo "make live-escalation prove Gemini drafts a post-revocation notice without revoking"
	@echo "make escalation-gates independently judge the live Escalation artifact"
	@echo "make live-narration prove a second modality: the Reviewer's verdict, spoken via Cloud Text-to-Speech"
	@echo "make narration-gates independently judge the live Narration artifact"
	@echo "make live-fleet prove the fleet claim at N=5: a tool shared by two departments, revoked once, pulled from both"
	@echo "make fleet-gates independently judge the live fleet artifact"
	@echo "make live-chain prove a genuine live cross-department derived_from chain, sales -> support -> finance"
	@echo "make chain-gates independently judge the live chain artifact"
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

hardening-check: check
	@$(PYTHON) scripts/incident.py
	@$(PYTHON) scripts/cost.py
	@$(PYTHON) scripts/demo.py
	@$(PYTHON) scripts/revoke.py
	@$(PYTHON) scripts/isolate.py
	@$(PYTHON) scripts/gates.py

serve:
	@$(PYTHON) -m custody.control_plane

image:
	docker build -t custody:local .

gates:
	@$(PYTHON) scripts/gates.py

# Networked on purpose, so deliberately not part of `make check`.
verify-deploy:
	@$(PYTHON) scripts/verify_deploy.py

incident:
	@$(PYTHON) scripts/incident.py

gui:
	@$(PYTHON) scripts/render_gui.py
	@$(PYTHON) scripts/render_architecture.py

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

live-onboarding:
	@$(PYTHON) scripts/live_onboarding.py

onboarding-gates:
	@$(PYTHON) scripts/onboarding_gates.py

live-escalation:
	@$(PYTHON) scripts/live_escalation.py

escalation-gates:
	@$(PYTHON) scripts/escalation_gates.py

live-narration:
	@$(PYTHON) scripts/live_narration.py

narration-gates:
	@$(PYTHON) scripts/narration_gates.py

live-fleet:
	@$(PYTHON) scripts/live_fleet.py

fleet-gates:
	@$(PYTHON) scripts/fleet_gates.py

live-chain:
	@$(PYTHON) scripts/live_chain.py

chain-gates:
	@$(PYTHON) scripts/chain_gates.py

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
