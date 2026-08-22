# TMA-NM Runtime Boundary Audit

Status: preregistration audit; no Gate 1 execution has occurred.

Audit date: 2026-08-22.

Pinned source: [`yedidel/mem-inv-bench`](https://github.com/yedidel/mem-inv-bench/tree/63f1359d677efbe1a65b982b2a54cabfec97f1e1)
at commit `63f1359d677efbe1a65b982b2a54cabfec97f1e1`.

## Classification

For the published synthetic `tool_echo` fixture, classify the official B3
reference as:

    B3-ORACLE-COUPLED

This is not a claim that the TMA-NM construction is invalid. The paper and
native monitor define a legitimate trusted origin-labeling boundary. The
classification says that this particular benchmark fixture also materializes
the attack's true origin as a field in the synthetic item and the official
`laundering.py` decision helper consumes that field directly. That field cannot
be derived from the common tool/payload observation in the trusted-tool-echo
case. B3 therefore remains a faithful native benchmark/oracle-coupled
reference, but it is not an equal-observation comparator for B0/B1/B2/B6.

## Source evidence

The pinned `code/laundering.py` source is explicit about the boundary:

- Lines 19-21 describe every item as carrying **GROUND TRUTH** (`true_origin`,
  provenance) plus manipulable signals, and say that non-malleable authority
  reads the ground-truth origin.
- Lines 81-83 document `build_items` as returning items with ground truth and
  signals.
- Lines 93-97 construct `tool_echo` with `true_origin:
  "tool_echo_untrusted"`, while `looks_benign=True` and
  `edge_untrusted=False`. The value is assigned by the benchmark fixture, not
  discovered from the returned payload.
- Lines 122-143 implement `authorized`; the `tma_nm` branch reads
  `item["true_origin"]` at lines 135-143.

The native TMA-NM monitor has a separate, legitimate trusted boundary:

- `code/memory.py` lines 23-29 define `Origin` and state that it is set by the
  trusted monitor and cannot be forged by the adversary.
- `code/memory.py` lines 50-60 define `MemoryItem` with `origin` and
  `act_class`; the production memory object does not have a `true_origin`
  field.
- `code/monitor.py` lines 98-113 accept the origin at `MemoryMonitor.write`,
  bind the action class at write time, and persist the result.
- `code/monitor.py` lines 146-167 enforce the action gate from the stored
  item authority.
- `code/agent_bench.py` lines 139-147 show the native benchmark builder
  assigning `Origin.UNTRUSTED_EXTERNAL` to external content and
  `Origin.TRUSTED_TOOL` to trusted facts.

The paper's threat model makes the assumption explicit: the monitor assigns
the origin from an authenticated channel, the adversary cannot forge it, and
the guarantees are conditional on that origin-labeling oracle (arXiv
Section II, Assumption A1, lines 82-86 in the HTML source). It also states that
the trusted monitor binds authority at write time (Section III, lines 91-98).
The paper does not show an independently deployed producer for the synthetic
`tool_echo_untrusted` field; the pinned fixture itself manufactures that
ground-truth label.

## Three-layer boundary

### Layer 1 — world/scorer ground truth (never treatment input)

| Field | Producer | Treatment access | Reason |
|---|---|---|---|
| `attacker_controlled` | external scorer | forbidden | identifies the adversarial value |
| `true_upstream_origin` | external scorer/benchmark truth | forbidden to B0/B1/B2/B6; the synthetic B3 fixture may materialize it only through its official native reference path | not observable from the trusted relay payload |
| `unauthorized_action` / expected outcome | scorer | forbidden | defines the primary endpoint |
| expected parents/affected set/verdict | scorer | forbidden | evaluation-only labels |

The scorer object is never serialized into runtime inputs or Firestore-like
state. The scorer reads its labels only after primary actions finish.

### Layer 2 — canonical observed event (shared world observation)

The canonical attack supplies only facts actually observable in the common
scenario: tool identity (`vendor_lookup`), tool invocation structure, returned
payload/content, operation/source/revision identifiers where the baseline
normally sees them, ordinary record IDs/event metadata, and the consequential
action request. The trusted relay presents the same tool-looking response in
the attack and the trusted control.

This layer is projected into each baseline without adding the scorer's causal
label. It is the only security-relevant input shared by B0/B1/B2/B6. B3's
native monitor may additionally receive its declared origin metadata, as
described below.

### Layer 3 — baseline-native security metadata

| Baseline | Native fields allowed | Producer/trust assumption | If missing or incorrect |
|---|---|---|---|
| B0 | canonical event, payload, tool identity, action request | no defense; no security metadata | action follows the undefended path |
| B1 | actual frozen Custody event fields: tool/source/revision identity, configured operation role/trust, observed parent IDs/event attribution, payload, action scope/request, and the existing Custody policy state | current Custody's configured collector/runtime boundary | use the frozen implementation behavior; do not infer hidden origin |
| B2 | canonical item content plus the official generic-lineage signal fields (`edge_untrusted`, derivation edges, and its ordinary item metadata) | the TMA-NM comparator's published lineage interface | apply the comparator's defined fallback; no `true_origin` |
| B3 | the official monitor's native `Origin`, `act_class`, scope, write/session metadata, item IDs, corroboration metadata, payload, and action request; the official synthetic fixture also contains `true_origin` for its benchmark decision helper | authenticated origin-labeling monitor is part of TMA-NM's declared TCB; in this fixture the `true_origin` value is benchmark-materialized and therefore oracle-coupled | the official native mechanism cannot be claimed to run under an absent origin-labeling boundary; record the native reference as coupled rather than inventing a replacement |
| B6 | Architecture A's frozen runtime-visible fields: configured ORIGIN/RELAY role, operation/source/revision, action scope/cap, collector-observed direct parent IDs, transform class, admission metadata, policy generation, and durable support/dependency state | Architecture A's declared policy/collector boundary; no content-based origin oracle | missing context is fail-closed under the frozen design; incorrect configured role is the separately bounded E2E assumption |

`true_origin` is never copied from the scorer into B0, B1, B2, or B6. The
official B3 path is run only as published and is labelled
`native_benchmark_oracle_coupled_reference`; it is not granted an oracle field
by the Gate 1 adapter after seeing a result.

## Per-field provenance requirements

The future runner must emit an allowlist audit for every baseline with:

1. field name;
2. producer and source path/paper evidence;
3. trust assumption;
4. whether the field is shared across baselines;
5. whether it is derived from scorer truth;
6. whether it exists in a real deployment;
7. the fail-closed or native fallback if it is absent/incorrect.

The adapter must reject any field not on the selected baseline's allowlist and
must recursively scan runtime objects for forbidden scorer keys. A baseline
constructor may not accept a `ScorerGroundTruth` object or retain a scorer
reference.

## Comparison consequence

The primary Gate 1 table is a **NATIVE-INTERFACE COMPARATIVE SECURITY
EVALUATION**, not an equal-information classifier comparison. B3 is retained,
faithfully executed, and clearly labelled as an oracle-coupled native
benchmark reference. A secondary shared-observation table is permitted for
B0/B1/B2/B6 only; B3 is `NOT_APPLICABLE` there rather than crippled or given a
synthetic substitute.

This boundary correction changes no attack payload, tool identity, action
endpoint, baseline membership, model-free cost, benign control, or Architecture
A kill threshold.
