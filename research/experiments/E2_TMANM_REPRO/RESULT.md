# E2 — Result

## Verdict: EXTERNAL-HARNESS-PARTIAL

Official code exists, is verifiably real (not a hallucinated or unrelated
repo, not a secondary summary — confirmed via ground-truth `gh api`
calls), and its offline/no-cost formal-correctness reproduction PASSED
cleanly on the first attempt. But only part of the relevant attack
surface is usable without cost, and one whole category Custody most needs
tested (D, cross-agent relay; J, mixed-source derived memory) is not
implemented in this harness at all — so the "yes, run this next" answer
from the brief's own decision tree is not a clean yes.

## 1. Exact official source

Paper: "Securing LLM-Agent Long-Term Memory Against Poisoning:
Non-Malleable, Origin-Bound Authority with Machine-Checked Guarantees,"
Yedidel Louck, arXiv:2606.24322v1, 23 Jun 2026, cs.CR. Code:
`https://github.com/yedidel/mem-inv-bench`, MIT license. Both
independently confirmed via direct arXiv fetch and ground-truth GitHub API
calls (`gh api`), not AI-summarized page renders alone (see
`SOURCE_AUDIT.md` for the exact evidence trail).

## 2. Pinned version/commit

`63f1359d677efbe1a65b982b2a54cabfec97f1e1` (repo's `main` HEAD at audit
time, 2026-06-23). Cloned outside the Custody source tree, not modified.

## 3. Whether it reproduced

**Yes, for the offline/no-cost subset.** `code/test_monitor.py` (5 unit
tests) and `code/check_invariant.py` (an exhaustive, bounded model check
against the real `monitor.py`, including a necessity proof that the
mechanism is load-bearing) both ran to completion with real, correct
output, no environment fix needed. **Blocked, not attempted, for the
LLM-backed subset** (`laundering.py`, `headtohead.py`, `benchmark.py`,
and five other scripts) — all require `OPENROUTER_API_KEY`, which was
deliberately not obtained, per this session's explicit no-spend
constraint. The repository's own already-logged `results/*.json` files
were read as secondary, self-reported evidence (not independently
re-run), and are internally consistent with the README's headline claims.

## 4. Attacks actually implemented

6 of 10 requested classes IMPLEMENTED in real code (A summarization, B
paraphrase — same mechanism as A, C trusted-tool echo, E manufactured
corroboration including a harder correlated-domain variant, H direct/
indirect poisoning, I delayed/sleeper activation). 1 DESCRIBED-BUT-NOT-
IMPLEMENTED as its own scenario (G, source identity loss — assumed away by
the threat model, exactly like Custody's own case P). 2 NOT PRESENT at all
(D cross-agent relay, J mixed-source derived memory) — and J is not just
untested, it is **architecturally unrepresentable** in TMA-NM's data
model, which carries no derivation/lineage field of any kind (see
`ATTACK_MATRIX.md`'s closing finding). Full detail and code citations in
`ATTACK_MATRIX.md`.

## 5. Strongest relevant attack for Custody

**C, trusted-tool echo.** This experiment's own reading of
`code/laundering.py`'s `tool_echo` channel and its self-reported 63.3% ASR
against the paper's `lineage` baseline (and 78.5% against `lineage` on the
"Trojan Hippo" head-to-head reproduction specifically) lines up exactly
with Custody's own red-team case F — a clean, confirmed FAIL where
`ToolTrust.of()` is a pure tool-identity lookup with no notion of the
payload's own provenance. Adapting this specific scenario (only
harness-plumbing work, per `CUSTODY_ADAPTER_MAP.md`) is the cheapest,
highest-confidence next test if this thesis proceeds — not because it
would tell Custody something new (the red-team already found this gap by
code reading alone), but because it would be evidence measured against an
attack construction someone else designed and validated across eight
models, which is stronger than this project's own synthetic reasoning
about itself.

## 6. Whether Custody can be evaluated without changing its security mechanism

**Yes, for A/B/C/E(base)/H/I** — all six can be adapted as pure test-
harness plumbing (translate TMA-NM's flat scenario items into
`FakeEvent`-shaped sequences, then call `take_custody`/`ExportGateway`
instead of the paper's own `authorized()` function), with no change to
`custody/*.py` required to *run* the scenario, only to make Custody
*pass* it — see `CUSTODY_ADAPTER_MAP.md`'s per-case answers, item 8.
**No** for D and J — nothing exists in TMA-NM's harness to adapt from, and
building either from scratch would be design work indistinguishable from
a new benchmark slice (E4), not reuse of an existing one. **Not a fair
comparison** for E's harder correlated-domain variant (S3 in
`stress_independence.py`) — Custody has no corroboration-independence
mechanism to falsify in the first place, so running that specific
scenario against Custody would test for the absence of something Custody
never claimed to have, which the literature audit already established.

## 7. Exact next experiment

Per the brief's own decision tree for PARTIAL: **use the usable subset
first.** Build the minimal test-harness adapter (translation layer only,
no Custody semantic change) for case C (trusted-tool echo) specifically,
run it against current Custody with no LLM calls required (Custody's own
decision is deterministic — `ToolTrust.of()` needs no model, so this
adaptation, unlike TMA-NM's own scenarios, would not even require an
OpenRouter key to execute against Custody's side; only reproducing TMA-
NM's own comparative numbers requires the paid LLM calls). This gives a
concrete, externally-sourced FAIL or PASS for Custody's most exposed
laundering case, before deciding whether D/J genuinely justify a new
benchmark slice (E4) or whether the thesis should narrow further first.
Do not build the adapter as part of this experiment — this is the
recommendation for a subsequent, explicitly authorized step.
