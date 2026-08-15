"""Render the secondary "architecture and evidence" page.

The incident page (`make gui`) covers exactly one thing: G3, the blast-
radius/revocation story. Everything else this project has live-proven — R1,
R2, S1, G1/G2/G4/G5, M1, O1, D1/D2, the N=25 fleet, the Provenance Auditor,
the Custody Reviewer — has no GUI surface until this page. It reads two
kinds of evidence, both already on disk, neither re-verified live at render
time:

1. G1-G5: `scripts/gates.py` is offline and fast (it regenerates G2-G4's
   demo fixtures deterministically and reads G1/G5 back from disk), so its
   real stdout is captured and parsed here, not re-derived.
2. R1, R2, S1, M1, O1, D1/D2, Auditor, Reviewer, Fleet: each already has a
   `proof-out/live-*.json` artifact from a real run against Google Cloud.
   This script reads each file's own self-reported `proof_id`,
   `captured_at`, and `claim_boundary` directly. It does NOT re-run the
   corresponding `scripts/*_gates.py` script, several of which make live
   Cloud Logging/Registry calls and will hang or fail without credentials
   in this environment -- re-running them here would make `make gui`
   flaky and, worse, would silently swap a static replay for a live claim
   this script cannot actually stand behind at arbitrary render time.
   Missing files are shown as "not yet proven" rather than skipped
   silently.

    make gui
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import (  # noqa: E402
    auditor_gates,
    chain_gates,
    fleet_gates,
    gateway_gates,
    memory_deletion_gates,
    model_armor_gates,
    narration_gates,
    observability_gates,
    registry_gates,
    review_gates,
    revision_binding_gates,
)

OUT_HTML = REPO_ROOT / "web" / "architecture.html"
PROOF_OUT = REPO_ROOT / "proof-out"

#: A stored revision string carries an algorithm tag, but a live-proof
#: artifact does not. So "does this artifact still pass its own claim" is
#: answered the same way `tests/test_stored_artifacts.py` already answers it
#: for `make check`: run the artifact's own offline judge, here at render
#: time instead of test time. Every judge below is pure (evidence dict in,
#: bool dict out) -- none of the `*_live` siblings that make live calls.
JUDGE_FN = {
    "R1": registry_gates.judge,
    "R2": revision_binding_gates.judge,
    "S1": gateway_gates.judge,
    "M1": model_armor_gates.judge,
    "O1": observability_gates.judge,
    "D1/D2": memory_deletion_gates.judge,
    "Auditor": auditor_gates.judge_offline,
    "Reviewer": review_gates.judge_offline,
    "Narration": narration_gates.judge_offline,
    "Fleet N=25": fleet_gates.judge_offline,
    "F1": chain_gates.judge_offline,
}

#: A judge reports its own freshness separately from every substantive
#: gate, because "captured a while ago" and "no longer proves the claim"
#: are different failures needing different chips. Same set
#: `tests/test_stored_artifacts.py` exempts from its own pass/fail check.
FRESHNESS_KEYS = {"fresh_live_evidence", "fresh_bounded_live_evidence"}


def evidence_state(judge, data: dict, now: datetime) -> str:
    """PASS, STALE (only freshness gates fail), or FAILING (something else does)."""
    try:
        gates = judge(data, now=now)
    except (KeyError, TypeError, ValueError):
        return "failing"
    failing = {name for name, passed in gates.items() if not passed}
    if not failing:
        return "pass"
    if failing <= FRESHNESS_KEYS:
        return "stale"
    return "failing"

GATE_LINE = re.compile(r"^\s*\[(?P<state>PASS|FAIL|BLOCKED)\s*\]\s*(?P<title>.+)$")


@dataclass(frozen=True)
class GateResult:
    state: str
    title: str
    detail: str


@dataclass(frozen=True)
class LiveProof:
    id: str
    title: str
    category: str
    script: str
    filename: str


LIVE_PROOFS = [
    LiveProof("R1", "Revision-aware admission", "Discovery & lifecycle",
              "scripts/live_registry_attack.py", "live-registry-attack.json"),
    LiveProof("R2", "Dispatch bound to the tools/list that authorized it", "Discovery & lifecycle",
              "scripts/live_revision_binding.py", "live-revision-binding.json"),
    LiveProof("S1", "Agent Gateway allow/deny enforcement", "Security & governance",
              "scripts/live_gateway.py", "live-gateway.json"),
    LiveProof("M1", "Model Armor content screening", "Security & governance",
              "scripts/live_model_armor.py", "live-model-armor.json"),
    LiveProof("O1", "Agent Observability, trace carries the custody digest", "Telemetry",
              "scripts/live_observability.py", "live-observability.json"),
    LiveProof("D1/D2", "Selective deletion from live Memory Bank", "Execution & state",
              "scripts/live_memory_deletion.py", "live-memory-deletion.json"),
    LiveProof("Auditor", "Demote now, revoke later, on the Scheduler's own clock", "Fleet & agents",
              "scripts/live_auditor.py", "live-auditor.json"),
    LiveProof("Reviewer", "Gemini drafts a verdict on a quarantined item", "Fleet & agents",
              "scripts/live_review.py", "live-review.json"),
    LiveProof("Narration", "The Reviewer's verdict, spoken aloud via Cloud Text-to-Speech", "Fleet & agents",
              "scripts/live_narration.py", "live-narration.json"),
    LiveProof("Fleet N=25", "A tool shared across departments, revoked once, pulled from both", "Fleet & agents",
              "scripts/live_fleet.py", "live-fleet.json"),
    LiveProof("F1", "A genuine live derived_from chain, sales -> support -> finance", "Fleet & agents",
              "scripts/live_chain.py", "live-chain.json"),
]

CATEGORY_ORDER = ["Discovery & lifecycle", "Execution & state", "Security & governance", "Telemetry", "Fleet & agents"]


def run_gates() -> list[GateResult]:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "gates.py")],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
    )
    lines = proc.stdout.splitlines()
    results: list[GateResult] = []
    for i, line in enumerate(lines):
        m = GATE_LINE.match(line)
        if not m:
            continue
        detail = lines[i + 1].strip() if i + 1 < len(lines) else ""
        results.append(GateResult(state=m.group("state"), title=m.group("title").strip(), detail=detail))
    return results


def age_string(captured_at: str, now: datetime) -> str:
    try:
        then = datetime.fromisoformat(captured_at)
    except ValueError:
        return "unknown"
    delta = now - then
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{int(delta.total_seconds() / 60)} min ago"
    if hours < 48:
        return f"{hours:.0f}h ago"
    return f"{delta.days}d ago"


def _short(s: str | None, n: int = 12) -> str:
    if not s:
        return "n/a"
    return s if len(s) <= n else s[:n] + "…"


# Each function turns one proof-out artifact's own nested evidence into a
# small visual replay -- the actual blocked prompt, the actual before/after
# facts, the actual denial reason -- instead of a paragraph describing it.
# A missing expected field degrades to `None` (rendered as "widget
# unavailable") rather than a fabricated placeholder.

def widget_r1(data: dict) -> dict | None:
    governed = data.get("governed", {})
    denial = governed.get("selected_denial", {})
    if not denial:
        return None
    return {
        "type": "pair",
        "a": {"label": "Registry-approved digest", "value": _short(denial.get("expected_revision"), 18), "state": "safe"},
        "b": {"label": "observed live tools/list digest", "value": _short(denial.get("observed_revision"), 18), "state": "danger"},
        "note": "blocked before dispatch: " + str(denial.get("reason")) +
                " — dispatch counter held at " + str(governed.get("dispatch_count_after")),
    }


def widget_r2(data: dict) -> dict | None:
    dm = data.get("digest_mismatch_control", {}).get("denial_log", {}).get("jsonPayload", {})
    rp = data.get("replay_control", {}).get("denial_log", {}).get("jsonPayload", {})
    pc = data.get("positive_control", {})
    if not (dm and rp and pc):
        return None
    return {
        "type": "timeline",
        "steps": [
            {"label": "accepted dispatch", "state": "safe",
             "detail": "valid v1 token, dispatch_count " + str(pc.get("dispatch_count_before")) + " → " + str(pc.get("dispatch_count_after"))},
            {"label": "denied: digest_mismatch", "state": "danger",
             "detail": "the v1 token presented after the server redeployed to v2; dispatch_count held at " + str(dm.get("dispatch_count"))},
            {"label": "denied: replayed", "state": "danger",
             "detail": "the same valid token presented a second time; dispatch_count held at " + str(rp.get("dispatch_count"))},
        ],
    }


def widget_s1(data: dict) -> dict | None:
    allow = data.get("allow_control", {})
    deny = data.get("deny_control", {})
    if not (allow and deny):
        return None
    return {
        "type": "pair",
        "a": {"label": "allow-list includes lookup_customer", "value": "200 OK · trace " + _short(allow.get("trace_id"), 14), "state": "safe"},
        "b": {"label": "allow-list excludes lookup_customer", "value": "403 Forbidden · trace " + _short(deny.get("trace_id"), 14), "state": "danger"},
    }


def widget_m1(data: dict) -> dict | None:
    mal = data.get("malicious_control", {})
    clean = data.get("clean_control", {})
    if not (mal and clean):
        return None
    return {
        "type": "pair_text",
        "a": {"label": "jailbreak / PI prompt — " + str(mal.get("result", {}).get("filterMatchState")),
              "value": mal.get("prompt"), "state": "danger"},
        "b": {"label": "clean prompt — " + str(clean.get("result", {}).get("filterMatchState")),
              "value": clean.get("prompt"), "state": "safe"},
    }


def widget_o1(data: dict) -> dict | None:
    if not data.get("trace_id"):
        return None
    return {
        "type": "chips",
        "chips": [
            {"label": "trace_id", "value": _short(data.get("trace_id"), 20)},
            {"label": "span_id", "value": data.get("span_id")},
            {"label": "custody_digest", "value": _short(data.get("custody_digest"), 20)},
        ],
    }


def widget_d1d2(data: dict) -> dict | None:
    before = data.get("before_facts")
    after = data.get("after_facts")
    if before is None or after is None:
        return None
    return {"type": "diff_list", "label_before": "before revoke", "label_after": "after revoke",
            "before": before, "after": after}


def widget_auditor(data: dict) -> dict | None:
    before = data.get("before_demotion", {})
    mid = data.get("after_demotion_before_sweep", {})
    after = data.get("after_sweep", {})
    if not (before and mid and after):
        return None
    return {
        "type": "timeline",
        "steps": [
            {"label": "before demotion", "state": "safe", "detail": "trusted, revocation_id: " + str(before.get("revocation_id"))},
            {"label": "demoted, before the auditor's next sweep", "state": "warn",
             "detail": "still unrevoked (revocation_id: " + str(mid.get("revocation_id")) + ") — demotion and revocation are genuinely decoupled"},
            {"label": "after the auditor's sweep", "state": "danger", "detail": "revoked at " + str(after.get("revoked_at"))},
        ],
    }


def widget_review(data: dict) -> dict | None:
    q = data.get("quarantined_text")
    v = data.get("verdict", {}).get("summary")
    if not (q and v):
        return None
    return {
        "type": "pair_text",
        "a": {"label": "quarantined — withheld from memory", "value": q, "state": "danger"},
        "b": {"label": "Gemini's drafted verdict", "value": v, "state": "safe"},
    }


def widget_narration(data: dict) -> dict | None:
    v = data.get("verdict", {}).get("summary")
    narration = data.get("narration", {})
    audio_path = narration.get("audio_path")
    if not (v and audio_path):
        return None
    audio_file = REPO_ROOT / audio_path
    if not audio_file.exists():
        return None
    audio_b64 = base64.b64encode(audio_file.read_bytes()).decode("ascii")
    return {
        "type": "audio",
        "label": "Gemini's verdict, spoken via Cloud Text-to-Speech",
        "text": v,
        "src": "data:audio/mpeg;base64," + audio_b64,
    }


def widget_fleet(data: dict) -> dict | None:
    shared = data.get("shared_tool_departments")
    untouched = data.get("untouched_departments")
    if not (shared and untouched):
        return None
    return {
        "type": "groups",
        "a": {"label": "revoked (used the shared tool)", "state": "danger", "items": list(shared)},
        "b": {"label": "untouched (used a different tool)", "state": "safe", "items": list(untouched.keys())},
    }


def widget_chain(data: dict) -> dict | None:
    departments = data.get("departments")
    sibling = data.get("sibling")
    if not (departments and sibling):
        return None
    removed = [
        f"{dept}: {departments[dept]['restatement'][:60]}..."
        for dept in ("sales", "support", "finance")
        if dept in departments
    ]
    untouched = [
        f"{dept}: own conversational memory" for dept in departments
    ] + [f"{sibling.get('user_id', 'sibling')}: independent tool-origin memory"]
    return {
        "type": "groups",
        "a": {"label": "revoked (the derived_from chain)", "state": "danger", "items": removed},
        "b": {"label": "untouched (unrelated to the chain tool)", "state": "safe", "items": untouched},
    }


WIDGET_FN = {
    "R1": widget_r1, "R2": widget_r2, "S1": widget_s1, "M1": widget_m1, "O1": widget_o1,
    "D1/D2": widget_d1d2, "Auditor": widget_auditor, "Reviewer": widget_review, "Narration": widget_narration,
    "Fleet N=25": widget_fleet, "F1": widget_chain,
}


def load_live_evidence(now: datetime) -> list[dict]:
    rows = []
    for proof in LIVE_PROOFS:
        path = PROOF_OUT / proof.filename
        if not path.exists():
            rows.append({
                "id": proof.id, "title": proof.title, "category": proof.category,
                "script": proof.script, "status": "missing", "has_evidence": False,
                "proof_id": None,
                "captured_at": None, "age": None, "claim_boundary": None, "widget": None,
            })
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            rows.append({
                "id": proof.id, "title": proof.title, "category": proof.category,
                "script": proof.script, "status": "malformed", "has_evidence": False,
                "proof_id": None,
                "captured_at": None, "age": None, "claim_boundary": None, "widget": None,
            })
            continue
        rows.append({
            "id": proof.id, "title": proof.title, "category": proof.category,
            "script": proof.script,
            "status": evidence_state(JUDGE_FN[proof.id], data, now),
            "has_evidence": True,
            "proof_id": data.get("proof_id"), "captured_at": data.get("captured_at"),
            "age": age_string(data["captured_at"], now) if data.get("captured_at") else None,
            "claim_boundary": data.get("claim_boundary"),
            "widget": WIDGET_FN[proof.id](data),
        })
    return rows


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Custody — architecture and evidence</title>
<style>
  :root {
    --bg: #f4f3ee; --panel: #fdfcf9; --panel-2: #f8f6f0;
    --line: #e0ddd2; --line-soft: #ecebe3;
    --ink: #1e1c17; --ink-dim: #6b6858; --ink-faint: #9b9786;
    --accent: #3f6e52; --accent-dim: rgba(63, 110, 82, 0.1);
    --danger: #b5432e; --danger-dim: rgba(181, 67, 46, 0.09);
    --warn: #a5761f; --warn-dim: rgba(165, 118, 31, 0.1);
    --sans: -apple-system, "Segoe UI", Roboto, system-ui, sans-serif;
    --mono: "IBM Plex Mono", "SF Mono", "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans); font-size: 13px; line-height: 1.55; }
  .mono { font-family: var(--mono); }
  a { color: var(--accent); }
  .shell { max-width: 980px; margin: 0 auto; padding: 26px 28px 90px; }
  .topline { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; flex-wrap: wrap; gap: 10px; }
  .topline nav a { color: var(--ink-dim); font-size: 12px; margin-left: 14px; }
  .topline nav a:hover { color: var(--accent); }
  h1 { font-size: 22px; margin: 0; }
  p.lede { color: var(--ink-dim); font-size: 13px; max-width: 70ch; margin: 10px 0 26px; }

  .gate-row { display: flex; gap: 12px; align-items: baseline; padding: 12px 0; border-bottom: 1px solid var(--line-soft); }
  .gate-row:last-child { border-bottom: none; }
  .state-pill { font-family: var(--mono); font-size: 9.5px; font-weight: 700; text-transform: uppercase; padding: 3px 8px; border-radius: 3px; flex: none; width: 62px; text-align: center; }
  .state-pill.PASS { background: var(--accent-dim); color: var(--accent); }
  .state-pill.FAIL { background: var(--danger-dim); color: var(--danger); }
  .state-pill.BLOCKED { background: var(--warn-dim); color: var(--warn); }
  .gate-row .g-title { font-weight: 600; }
  .gate-row .g-detail { color: var(--ink-dim); font-size: 12px; margin-top: 3px; }

  section.block { margin-bottom: 30px; }
  section.block h2 { font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-faint); margin: 0 0 12px; }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 18px 22px; }

  .category { margin-bottom: 22px; }
  .category h3 { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-faint); margin: 0 0 8px; }
  .proof-card { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 14px 18px; margin-bottom: 10px; }
  .proof-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  .proof-id { font-family: var(--mono); font-weight: 700; color: var(--accent); font-size: 12px; }
  .proof-title { font-weight: 600; margin-left: 8px; }
  .proof-meta { font-family: var(--mono); font-size: 10.5px; color: var(--ink-faint); }
  .proof-scope { margin-top: 10px; font-size: 10.5px; color: var(--ink-faint); border-top: 1px dashed var(--line-soft); padding-top: 8px; }
  .proof-scope b { color: var(--ink-dim); font-weight: 600; }
  .proof-script { margin-top: 8px; font-family: var(--mono); font-size: 10.5px; color: var(--ink-faint); }
  .status-tag { font-family: var(--mono); font-size: 9.5px; text-transform: uppercase; padding: 2px 7px; border-radius: 3px; }
  .status-tag.pass { background: var(--accent-dim); color: var(--accent); }
  .status-tag.stale { background: var(--warn-dim); color: var(--warn); }
  .status-tag.missing { background: var(--warn-dim); color: var(--warn); }
  .status-tag.malformed { background: var(--danger-dim); color: var(--danger); }
  .status-tag.failing { background: var(--danger-dim); color: var(--danger); }

  /* --- widgets: the actual replay, not a description of it --- */
  .widget { margin-top: 12px; }
  .w-pair, .w-pair-text, .w-groups { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .w-box { border-radius: 5px; padding: 10px 12px; border: 1px solid var(--line); }
  .w-box.safe { background: var(--accent-dim); border-color: rgba(63,110,82,0.3); }
  .w-box.danger { background: var(--danger-dim); border-color: rgba(181,67,46,0.3); }
  .w-box .w-label { font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-faint); margin-bottom: 6px; }
  .w-box.safe .w-label { color: var(--accent); }
  .w-box.danger .w-label { color: var(--danger); }
  .w-box .w-value { font-family: var(--mono); font-size: 11.5px; color: var(--ink); word-break: break-word; }
  .w-box .w-text { font-size: 12px; color: var(--ink); line-height: 1.45; }
  .w-note { margin-top: 8px; font-family: var(--mono); font-size: 10.5px; color: var(--ink-dim); }
  .w-audio audio { width: 100%; margin-top: 10px; }

  .w-timeline { display: flex; flex-direction: column; gap: 0; }
  .w-step { display: flex; gap: 10px; padding: 7px 0; }
  .w-step .w-dot { width: 9px; height: 9px; border-radius: 50%; margin-top: 3px; flex: none; }
  .w-step .w-dot.safe { background: var(--accent); }
  .w-step .w-dot.warn { background: var(--warn); }
  .w-step .w-dot.danger { background: var(--danger); }
  .w-step .w-slabel { font-weight: 600; font-size: 12px; }
  .w-step .w-sdetail { font-family: var(--mono); font-size: 10.5px; color: var(--ink-dim); margin-top: 2px; }

  .w-chips { display: flex; gap: 8px; flex-wrap: wrap; }
  .w-chip { border: 1px solid var(--line); border-radius: 4px; padding: 5px 9px; font-family: var(--mono); font-size: 10.5px; }
  .w-chip .w-clabel { color: var(--ink-faint); text-transform: uppercase; font-size: 8.5px; letter-spacing: 0.04em; display: block; }

  .w-diff-list { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .w-diff-list .w-col .w-collabel { font-size: 9.5px; text-transform: uppercase; color: var(--ink-faint); margin-bottom: 6px; }
  .w-diff-list ul { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 5px; }
  .w-diff-list li { font-size: 11.5px; padding: 5px 8px; border-radius: 3px; background: var(--panel-2); border: 1px solid var(--line-soft); }
  .w-diff-list .removed { text-decoration: line-through; color: var(--ink-faint); background: var(--danger-dim); border-color: rgba(181,67,46,0.25); }
  .w-groups ul { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 5px; }
  .w-groups li { font-family: var(--mono); font-size: 11px; padding: 4px 8px; border-radius: 3px; background: var(--panel-2); }
  .w-unavailable { font-size: 11px; color: var(--ink-faint); font-style: italic; margin-top: 8px; }

  @media (max-width: 640px) {
    .w-pair, .w-pair-text, .w-groups, .w-diff-list { grid-template-columns: 1fr; }
  }

  footer { margin-top: 20px; color: var(--ink-faint); font-size: 11px; }
  footer a { color: var(--ink-faint); text-decoration: underline; }
</style>
</head>
<body>
<div class="shell">
  <div class="topline">
    <h1>Architecture &amp; evidence</h1>
    <nav><a href="incident.html">&larr; Dependency map</a></nav>
  </div>
  <p class="lede">
    The dependency map covers one incident: G3, the blast-radius and revocation
    story. Everything below is proven, separately, against real Google Cloud
    infrastructure or a fast offline fixture &mdash; none of it is re-verified
    by loading this page. Each row reads its own captured evidence file; a
    missing or stale file is labeled as such, not hidden.
  </p>

  <section class="block" id="gates">
    <h2>Core acceptance gates (offline, from scripts/gates.py)</h2>
    <div class="panel" id="gate-list"></div>
  </section>

  <section class="block" id="live">
    <h2>Live capability proofs (Google Cloud, captured separately)</h2>
    <div id="proof-categories"></div>
  </section>

  <footer>
    Generated by <code class="mono">scripts/render_architecture.py</code>. Run
    <code class="mono">make check</code> for the offline gates and
    <code class="mono">make live-*</code> (see <code class="mono">make help</code>)
    to refresh any live proof. See <a href="https://github.com/Yatsuiii/custody/blob/main/README.md">README.md</a> for
    the full product-mapping table and <a href="https://github.com/Yatsuiii/custody/blob/main/DECISIONS.md">DECISIONS.md</a>
    for the corrections behind each claim_boundary.
  </footer>
</div>

<script id="gate-data" type="application/json">__GATE_DATA__</script>
<script id="proof-data" type="application/json">__PROOF_DATA__</script>
<script>
(function () {
  "use strict";
  const gates = JSON.parse(document.getElementById("gate-data").textContent);
  const proofs = JSON.parse(document.getElementById("proof-data").textContent);
  const $ = (id) => document.getElementById(id);

  const gateList = $("gate-list");
  gates.forEach((g) => {
    const row = document.createElement("div");
    row.className = "gate-row";
    row.innerHTML =
      '<span class="state-pill ' + g.state + '">' + g.state + "</span>" +
      '<div><div class="g-title">' + g.title + "</div>" +
      '<div class="g-detail">' + g.detail + "</div></div>";
    gateList.appendChild(row);
  });

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function renderWidget(w) {
    if (!w) return '<div class="w-unavailable">no replay available for this artifact\\u2019s current shape</div>';
    if (w.type === "pair") {
      return '<div class="widget w-pair">' +
        '<div class="w-box ' + w.a.state + '"><div class="w-label">' + esc(w.a.label) + '</div><div class="w-value">' + esc(w.a.value) + "</div></div>" +
        '<div class="w-box ' + w.b.state + '"><div class="w-label">' + esc(w.b.label) + '</div><div class="w-value">' + esc(w.b.value) + "</div></div>" +
        "</div>" + (w.note ? '<div class="w-note">' + esc(w.note) + "</div>" : "");
    }
    if (w.type === "pair_text") {
      return '<div class="widget w-pair-text">' +
        '<div class="w-box ' + w.a.state + '"><div class="w-label">' + esc(w.a.label) + '</div><div class="w-text">' + esc(w.a.value) + "</div></div>" +
        '<div class="w-box ' + w.b.state + '"><div class="w-label">' + esc(w.b.label) + '</div><div class="w-text">' + esc(w.b.value) + "</div></div>" +
        "</div>";
    }
    if (w.type === "timeline") {
      return '<div class="widget w-timeline">' + w.steps.map((s) =>
        '<div class="w-step"><div class="w-dot ' + s.state + '"></div><div><div class="w-slabel">' + esc(s.label) +
        '</div><div class="w-sdetail">' + esc(s.detail) + "</div></div></div>").join("") + "</div>";
    }
    if (w.type === "chips") {
      return '<div class="widget w-chips">' + w.chips.map((c) =>
        '<div class="w-chip"><span class="w-clabel">' + esc(c.label) + "</span>" + esc(c.value) + "</div>").join("") + "</div>";
    }
    if (w.type === "diff_list") {
      const beforeItems = w.before.map((item) => {
        const stillThere = w.after.includes(item);
        return "<li" + (stillThere ? "" : ' class="removed"') + ">" + esc(item) + "</li>";
      }).join("");
      const afterItems = w.after.map((item) => "<li>" + esc(item) + "</li>").join("");
      return '<div class="widget w-diff-list">' +
        '<div class="w-col"><div class="w-collabel">' + esc(w.label_before) + '</div><ul>' + beforeItems + "</ul></div>" +
        '<div class="w-col"><div class="w-collabel">' + esc(w.label_after) + '</div><ul>' + afterItems + "</ul></div>" +
        "</div>";
    }
    if (w.type === "audio") {
      return '<div class="widget w-audio">' +
        '<div class="w-box safe"><div class="w-label">' + esc(w.label) + '</div><div class="w-text">' + esc(w.text) + "</div>" +
        '<audio controls preload="none" src="' + w.src + '"></audio>' +
        "</div></div>";
    }
    if (w.type === "groups") {
      return '<div class="widget w-groups">' +
        '<div class="w-box ' + w.a.state + '"><div class="w-label">' + esc(w.a.label) + '</div><ul>' +
        w.a.items.map((i) => "<li>" + esc(i) + "</li>").join("") + "</ul></div>" +
        '<div class="w-box ' + w.b.state + '"><div class="w-label">' + esc(w.b.label) + '</div><ul>' +
        w.b.items.map((i) => "<li>" + esc(i) + "</li>").join("") + "</ul></div>" +
        "</div>";
    }
    return "";
  }

  const byCategory = {};
  proofs.forEach((p) => { (byCategory[p.category] = byCategory[p.category] || []).push(p); });
  const cats = $("proof-categories");
  Object.keys(byCategory).forEach((cat) => {
    const wrap = document.createElement("div");
    wrap.className = "category";
    wrap.innerHTML = "<h3>" + cat + "</h3>";
    byCategory[cat].forEach((p) => {
      const card = document.createElement("div");
      card.className = "proof-card";
      const meta = p.has_evidence
        ? p.proof_id + " &middot; captured " + p.age + " (" + p.captured_at + ")"
        : p.status === "missing" ? "no proof-out artifact on disk" : "artifact could not be parsed";
      card.innerHTML =
        '<div class="proof-head"><div><span class="proof-id">' + p.id + '</span><span class="proof-title">' + p.title + "</span></div>" +
        '<span class="status-tag ' + p.status + '">' + p.status + "</span></div>" +
        '<div class="proof-meta">' + meta + "</div>" +
        (p.has_evidence ? renderWidget(p.widget) : "") +
        (p.claim_boundary ? '<div class="proof-scope"><b>Scope:</b> ' + esc(p.claim_boundary) + "</div>" : "") +
        '<div class="proof-script">' + p.script + "</div>";
      wrap.appendChild(card);
    });
    cats.appendChild(wrap);
  });
})();
</script>
</body>
</html>
"""


def main() -> int:
    now = datetime.now(UTC)
    gates = run_gates()
    proofs = load_live_evidence(now)

    html = TEMPLATE.replace(
        "__GATE_DATA__",
        json.dumps([{"state": g.state, "title": g.title, "detail": g.detail} for g in gates]),
    )
    html = html.replace("__PROOF_DATA__", json.dumps(proofs))

    OUT_HTML.parent.mkdir(exist_ok=True)
    OUT_HTML.write_text(html)
    print(f"  wrote {OUT_HTML.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
