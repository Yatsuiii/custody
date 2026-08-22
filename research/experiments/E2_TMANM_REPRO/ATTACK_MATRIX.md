# E2 — Attack Taxonomy Matrix

Classified against actual source code read at the pinned commit
(`63f1359d677efbe1a65b982b2a54cabfec97f1e1`), never inferred from the
paper's prose alone. "IMPLEMENTED" means real, executable code exists that
constructs the scenario and measures a pass/fail outcome — not that this
experiment ran it (LLM-backed runs are BLOCKED, see `REPRODUCTION.md`;
where the repo's own already-logged `results/*.json` covers a case, that
is noted separately as self-reported).

| # | Attack | Classification | Evidence |
|---|---|---|---|
| A | Summarization laundering | **IMPLEMENTED** | `code/laundering.py`'s `summarize` channel: `summarize(scn["poison"], model)` calls a real LLM (`llm.gen`) to paraphrase the poison, then labels the result `true_origin="agent_from_untrusted", edge_untrusted=False` — a genuine, LLM-generated paraphrase, not a scripted string swap. Self-reported result: laundered against `lineage` (68.3% ASR) and `trust_score` (68.3%), defeated by `tma_nm` (0%). |
| B | Paraphrase laundering | **IMPLEMENTED** (same mechanism as A) | Structurally identical code path — TMA-NM does not distinguish "summarization" from "paraphrase" as separate attack classes; both are the `summarize` channel. No separate paraphrase-specific scenario exists beyond this. |
| C | Trusted-tool echo | **IMPLEMENTED** | `code/laundering.py`'s `tool_echo` channel: constructs an item labelled as if returned by a trusted lookup tool, but carrying the attacker's value (`true_origin="tool_echo_untrusted"`). Self-reported result: laundered against `lineage`/`trust_score`/`capability_ifc` (63.3% each), defeated by `tma_nm` (0%). Also separately exercised at the multi-turn, real-tool-call level in `code/multiturn.py` (a `lookup_web` tool tagged untrusted vs. `lookup_registry` tagged trusted, value-level taint propagated across turns) and in `code/headtohead.py`'s reproduction of "Trojan Hippo," which the README states defeats the `lineage` baseline specifically (78.5% ASR, "lineage gives no protection on the Trojan Hippo exfiltration"). |
| D | Cross-agent relay | **NOT PRESENT** | Every scenario in this repository is single-agent: one `MemoryMonitor`/one agent persona across sessions (`t_write` session index) or across tool-call turns within one session (`multiturn.py`). Nowhere does the harness construct two distinct agent identities where one agent's output becomes another, structurally different agent's input — Custody's actual cross-department fleet pattern (`live_chain.py`, `live_fleet.py`) has no analog here. Confirmed by reading every scenario-construction function in `code/*.py`: none takes more than one agent/persona parameter. |
| E | Manufactured corroboration | **IMPLEMENTED** | `code/laundering.py`'s `corroborate` channel: two untrusted items independently asserting the same value (`indep_trusted=False` on both, so TMA-NM's Sybil-resistant elevation correctly refuses them). Self-reported result: `tma_nm` and `lineage` both hold at 0% here (the one channel `lineage` happens to also defend, since a purely-untrusted-sourced duplicate never earns a trusted edge in this baseline's own logic); `trust_score`/`capability_ifc`/`none` remain vulnerable (52.5%). A materially harder variant exists: `code/stress_independence.py`'s S3 ("two correlated compromises, shared domain") — two genuinely *trusted* principals, but both dependent on the same compromised upstream domain, testing whether naive corroboration-counting is fooled by *correlated*, not just duplicated-untrusted, sources. This is a stronger, more relevant test than the base `corroborate` channel and is IMPLEMENTED as its own script. |
| F | Authority amplification through transformation | **IMPLEMENTED** (subsumed by A/C, not a separate scenario) | This is the general property the whole benchmark measures, not a distinct channel: the ablation study (README: "removing origin binding restores attacks") is the direct test that authority must not increase via transformation. No standalone "amplification" scenario exists beyond what A and C already construct. |
| G | Source identity loss | **DESCRIBED-BUT-NOT-IMPLEMENTED as its own scenario** | The *effect* of source-identity loss is what channels A/C simulate (`edge_untrusted=False`, i.e. the true untrusted origin is no longer visible to a naive defense), but there is no scenario that specifically attacks *identity/metadata itself* (e.g. forging an origin tag, corrupting a stored record's provenance field after the fact). `memory.py`'s own threat-model comment states plainly: "Set by the trusted monitor; the adversary cannot forge it (threat model, Section 3)" — i.e. this is an explicit **assumption**, not a tested attack surface. Directly comparable to Custody's own case P (`CURRENT_CUSTODY_REDTEAM.md`), which found the identical assumption in Custody's own trusted-computing-base. |
| H | Indirect memory poisoning | **IMPLEMENTED** | The `direct` channel in `laundering.py` (unlaundered poison sitting as untrusted memory) and the entire `agent_bench.py`/`benchmark.py` scenario set are this attack class by definition — untrusted content written now, later drives a consequential action. Self-reported: `none`/`capability_ifc` both at 83.3% ASR on `direct`; `tma_nm`/`trust_score`/`lineage` all correctly hold at 0% here (this is the *easy* case every defense class in the paper is designed to catch — laundering is what separates them). |
| I | Delayed/sleeper activation | **IMPLEMENTED** | `code/test_monitor.py::test_sleeper_blocked` (independently reproduced by this experiment, PASS): an item is written in session A, two further unrelated sessions pass, then a consequential action is attempted — the exact "write now, trigger much later" pattern. This is also structural to the harness's `t_write` session-index design generally, not a one-off test. |
| J | Mixed-source derived memory | **NOT PRESENT as tested; closest analog is E, but structurally different** | No scenario constructs one memory item whose *content* is a genuine textual synthesis of two distinct upstream sources (Custody's E0/E1 case: "root_A + root_B → derived_AB, one record"). `corroborate` (E) and `stress_independence.py`'s multi-source settings are structurally different: they present the monitor with **multiple separate items** each independently asserting the same value, evaluated as a set, never one item whose own content was synthesized from two parents' text. TMA-NM's data model (`MemoryItem`) has no `derived_from`/lineage field at all — it does not track derivation edges, by design (see `NOVELTY_MATRIX.md` update below), so a "mixed-source derived memory" scenario is not just untested, it is **not representable** in TMA-NM's own data model as currently implemented. |

## Summary

IMPLEMENTED: 6 (A, B, C, E, H, I) · NOT PRESENT: 2 (D, J) ·
DESCRIBED-BUT-NOT-IMPLEMENTED: 1 (G) · subsumed, not separately scored: 1 (F)

**The single most load-bearing finding for Custody's own thesis**: TMA-NM's
`MemoryItem` (`code/memory.py`) carries no derivation/lineage field of any
kind. Authority is `origin` (an `IntEnum`, fixed at write time) plus a flat
`corroborations: list[item_id]` populated only by `elevate()`. There is no
`derived_from`, no ancestor graph, no traversal. This is not an oversight —
it is the paper's central design choice (avoid lineage precisely because
lineage is provably malleable) — but it means TMA-NM's harness has **no
representation at all** for the two things Custody's own architecture is
built around: a derivation *graph* and *retroactive* revocation over it.
Case J (mixed-source derived memory) is not just untested by TMA-NM, it
is architecturally foreign to it.
