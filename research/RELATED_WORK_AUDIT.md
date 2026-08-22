# Related Work Audit

Method: primary sources only, verified via direct arXiv API queries (not
search-engine summaries alone) and, where possible, direct fetch of paper
abstracts/summaries. Every arXiv ID below was independently confirmed to
exist and match its title. Where a claim about a paper's content could not
be independently verified from a primary source, it is marked
**unverified** rather than presented as fact — per the session contract's
acceptance gate 1.

## MemSecBench — arXiv:2607.27080 (Chen, Xie, Fu, Zhou, Yu, Xuan; Jul 2026)

1. **Threat model**: attacker-crafted instruction stored in long-term
   memory, recalled later, drives a real action.
2. **Attack surface**: memory write channel, 4 backends x 2 harnesses x 3
   LLMs.
3. **Lifecycle**: full Write → Execute → Forget (7 checkpoints).
4. **Persisted**: memory records, evidence-gated (deterministic + judge +
   programmatic checks).
5. **Provenance representation**: behavioral, not structurally typed.
6. **Lineage tracked**: no first-class graph; "Forget" uses one neutral
   repair prompt, not traversal.
7. **Authority separate from content**: no.
8. **Laundering tested**: no — confirmed by direct fetch, paraphrase/
   summarization defeating repair is not tested.
9. **Trust-then-later-compromise modeled**: implicit only.
10. **Retroactive revocation with bounded interval**: **confirmed absent**
    ("the benchmark does not model bounded compromise windows or
    tool-specific temporal intervals").
11. **Descendants actually repaired**: yes, headline result — 56.1%
    selective repair rate.
12. **Repair selectivity**: attempted, but authors report a **30.2-point
    gap** between repair success and benign-preservation, i.e. real,
    significant collateral damage in practice.
13. **Metrics**: persistence 84.2%, write-execute success 50.3%, selective
    repair 56.1%.
14. **Benchmark**: 310 cases / 48 contexts, self-constructed.
15. **Stated limitations**: benign-memory preservation is "the primary
    bottleneck"; 41.3pp variance across backend stacks.
16. **Overlap with Custody**: closest *empirical* analog — same axis
    (selective repair) Custody claims to win on — but a measurement paper,
    not a mechanism, and explicitly does not model bounded intervals or
    laundering.
17. **What's unanswered**: bounded-interval modeling, laundering-resistant
    mechanism; only ad hoc "clean up your memory" prompting is evaluated.

## MPBench — arXiv:2606.04329, "From Untrusted Input to Trusted Memory" (Jun 2026)

Write+Retrieve only, no Forget stage at all. 6 attack classes, 3,240 cases,
7 domains; shows existing prompt-injection defenses (PIGuard, DataFilter,
CommandSans, PromptArmor) fail on memory poisoning specifically. No
revocation, no lineage, no authority/content separation.
**Overlap with Custody: none beyond "memory poisoning is real and
under-defended."**

## "Sleeper" memory poisoning — two distinct real papers (not Anthropic's model-backdoor "Sleeper Agents," correctly disambiguated)

- **"Hidden in Memory: Sleeper Memory Poisoning in LLM Agents"**,
  arXiv:2605.15338 (May 2026). Attacker manipulates external context so a
  fabricated memory persists dormant and re-emerges later. Write success up
  to 99.8%; of successful retrievals, 60-89% cause the intended action.
  Attack-measurement only, **no defense or revocation mechanism proposed.**
- **"Plant, Persist, Trigger: Sleeper Attack on Large Language Model
  Agents"**, arXiv:2605.28201 (May 2026). 1,896-instance benchmark, 3
  agent-state targets (session/memory/skills), 6 harmful outcomes.
  Attack-taxonomy paper, **no defense proposed.**

Both establish that the "legitimately-quiet-then-later-triggered" threat
model is real and measured, but neither addresses revocation once such
content has propagated. Neither is a "revocation" paper at all.

## TMA-NM — arXiv:2606.24322, "Securing LLM-Agent Long-Term Memory Against Poisoning: Non-Malleable, Origin-Bound Authority with Machine-Checked Guarantees" (Louck, Jun 2026)

**The single strongest piece of prior art against this thesis's novelty.**

1. **Threat model**: content stored in one session steers a consequential
   action in a later session — closely matches Custody's setup.
2. **Attack surface**: explicitly names three laundering channels —
   summarization, trusted-tool echo, and manufactured/Sybil corroboration —
   verbatim the laundering concern this thesis is built around.
3. **Lifecycle**: write → retrieve → act, formalized.
4. **Persisted**: memory items with origin-bound authority tags, separate
   from content.
5. **Provenance**: authority bound to origin at write time,
   non-malleably (information-flow-control style).
6. **Lineage tracked**: yes, but the paper's central theorem (T1) *proves*
   lineage-only and content-only defenses are formally insufficient under
   laundering — a direct, formal indictment of Custody's own mechanism
   (exact-content-hash `CustodyGraph.resolve`, `custody/graph.py:187-197`),
   since paraphrase/summarization defeats hash matching by construction.
7. **Authority separate from content**: **yes, explicitly, as the paper's
   central contribution.**
8. **Laundering resistance**: **headline result** — 0% laundering attack
   success vs. up to 68% for existing defenses, across 8 frontier models,
   via Sybil-resistant corroboration-gated authority elevation.
9. **Trust-then-later-compromise (t0 legitimate, t2 discovered
   compromised)**: **not the threat model.** TMA-NM is about preventing
   *fraudulent* authority from being assigned or elevated at write time,
   not about a source that was *correctly* trusted at write time and only
   later found to have been compromised.
10. **Retroactive revocation after descendants already exist**:
    **confirmed absent** — the paper's own summary states it does not
    address revoking already-bound authority after further descendants
    have propagated.
11/12. **Descendant repair / selectivity**: not addressed — non-malleable
    binding is a *prevention* mechanism; there is nothing to "repair"
    because the design goal is to never reach the bad state, not to
    recover from it once new evidence about the past arrives.
13. **Metrics**: laundering ASR (0% vs. up to 68% baseline), full
    legitimate-utility preservation, 8-model cross-defense benchmark, TLA+
    machine-checked proofs.
14. **Reproducibility**: own benchmark + harness + TLA+ specs released.
15. **Limitations**: by construction, static/write-time only; no notion of
    correcting a validly-assigned-then-later-wrong authority decision.
16. **Overlap with Custody**: very high on the laundering-resistance and
    authority-vs-content-vs-lineage separation axis; TMA-NM is a rigorous,
    formally proven version of what Custody's structural-origin labelling
    gestures at informally, and it is **strictly stronger** than Custody on
    write-time robustness to laundering.
17. **What survives**: TMA-NM's model is static and one-shot. It has no
    concept of a source correctly trusted, later found compromised only in
    a sub-interval `[t_a, t_b]`, requiring selective walk-back of exactly
    that interval's descendants while preserving the rest. This is the
    precise crux gap that survives TMA-NM.

**Addendum, E2 (2026-08-22): released code independently verified, cloned,
and partially reproduced.** Full detail in `research/experiments/
E2_TMANM_REPRO/`. Corrections and confirmations to the summary above, now
grounded in source code rather than the abstract alone:

- The repository (`github.com/yedidel/mem-inv-bench`, pinned at
  `63f1359d677efbe1a65b982b2a54cabfec97f1e1`, MIT) is real, independently
  confirmed via the GitHub API, and its content matches the paper exactly
  (same title, same author, same three named laundering channels). Its
  offline formal-correctness reproduction (`test_monitor.py`,
  `check_invariant.py`) passed cleanly with no fix needed.
- **Important correction**: TMA-NM's `lineage` "defense" comparator, used
  to produce the 0%-vs-68% headline numbers, is **not** a run of any real
  external lineage system's code (not MemLineage's own repository, not
  Custody's own code) — it is the paper author's own minimal, hand-built
  stand-in for the *category* of lineage-based defense
  (`code/laundering.py`, `code/agent_bench.py`). This is a legitimate way
  to empirically witness a formal separation theorem, and does not weaken
  the theorem itself, but it means the 0%-laundering-ASR headline is a
  comparison against a simulated generic lineage defense, not against
  Custody or MemLineage specifically.
- **Important addition**: TMA-NM's `MemoryItem` data model
  (`code/memory.py`) carries **no derivation/lineage field of any kind** —
  authority is `origin` (fixed at write) plus a flat corroboration list,
  never a graph. This means TMA-NM cannot represent — not merely does not
  test, cannot represent in its own data model — a memory genuinely
  synthesized from two upstream sources (Custody's E0/E1 case), which
  sharpens rather than weakens the earlier finding that TMA-NM's laundering
  resistance and Custody's derivation-graph tracking are different, only
  partially overlapping mechanisms.
- The LLM-backed empirical runs (the actual 0%-vs-68% numbers) were not
  independently re-executed in E2 (blocked on a deliberately-not-obtained
  OpenRouter API key), so those specific numbers remain self-reported by
  the paper's authors, not independently re-verified by this project — a
  weaker but not absent form of evidence, and the offline formal proofs
  that *do* independently reproduce are the stronger of the two claims.

## MemLineage — arXiv:2605.14421 (Ouyang, Hou; May 2026)

1. **Threat model**: untrusted content written, later re-enters as
   instruction; framed explicitly as "chain-of-custody."
2. **Persisted**: per-principal Ed25519-signed entries in an RFC-6962
   Merkle log, plus a weighted derivation DAG — cryptographically hardened
   analog of Custody's `derived_from` graph.
3. **Lineage**: yes, weighted DAG, "max-of-strong-edges" propagation,
   threshold-based "Untrusted-Path Persistence" invariant.
4. **Authority vs. content**: partial — action-gating uses a lineage-derived
   trust score, which is exactly the category TMA-NM's T1 theorem argues is
   unsound under laundering.
5. **Laundering tested**: **confirmed absent** — the paper does not test
   whether paraphrase/summarization defeats its DAG edges.
6. **Retroactive revocation**: **confirmed absent** — "the paper does not
   explicitly address retroactive or selective revocation. Instead it
   emphasizes preventive enforcement."
7. **Metrics**: ASR driven to 0 across 3 workloads, AgentDojo
   banking-pair evaluation, sub-millisecond overhead.
8. **Limitations (author-stated)**: hosted-model sweeps rely on "auditable
   logs rather than byte-pinned artifacts" (own admission of weaker
   reproducibility outside a deterministic harness); no discussion of what
   happens when today's trusted ancestor is discovered compromised
   tomorrow.
9. **Overlap with Custody**: the closest **architectural** sibling to
   Custody's derivation graph + trust catalog, implemented with real
   cryptography where Custody uses a simpler binary vouch/demote +
   content-hash model. MemLineage's weighted-DAG threshold model is
   strictly *stronger* than Custody's no-epoch binary model on
   write-time gating, but *weaker* than Custody's stated ambition in one
   respect: it has zero revocation/repair concept, only forward gating.
10. **What survives**: identical gap to TMA-NM — no retroactive graph
    repair for a formerly-trusted-now-compromised ancestor, no
    bounded-interval reasoning, and its "LLM-mediated derivation lineage"
    is not verified laundering-resistant either.

## SMSR — arXiv:2606.12703 (Sharma; Jun 2026)

Certified statistical-robustness defense against Multi-Session Memory
Poisoning: HMAC-signed writes + majority-voting/ablation certificate at
retrieval. Unsigned ASR 93-100% → 0%; authenticated-adversary ASR held to
8.0% (95% CI); clean-query utility 85-90%. **No derivation graph, no
revocation, no bounded interval, no laundering-resistance claim** — a
different category of defense (certified robustness to poisoned writes),
not a provenance/repair system. Authors explicitly note prior defenses they
compare against "assume a fixed knowledge base" — SMSR does not model a
knowledge base whose trust status changes over time either.

## OWASP ASI06 / Agent Memory Guard

Confirmed to exist as a named risk category (consistent secondary-source
citation from vectorize.io, Modulos, Auth0, Teleport, promptfoo), with a
reference implementation focused on runtime validation (hashing, anomaly
detection). **Could not directly retrieve and quote OWASP's own primary
risk-definition text on revocation** — this is marked unverified rather
than asserted; treat ASI06 as legitimizing the problem category (which
Custody's own README already cites it for), not as prior art that
addresses or blocks the specific bounded-interval revocation question.

## Survey — arXiv:2604.16548, "A Survey on Long-Term Memory Security in LLM Agents: Attacks, Defenses, and Governance Across the Memory Lifecycle" (Apr 2026)

**Second most important find: an independent, non-Custody-authored source
that explicitly names this thesis's exact gap as open.**

Proposes a 6-phase Memory Lifecycle Framework (Write, Store, Retrieve,
Execute, Share & Propagate, **Forget & Rollback**) x 4 objectives
(Integrity, Confidentiality, Availability, **Governance**) — the most
complete lifecycle taxonomy found in this audit, and it explicitly includes
cross-agent propagation as its own phase.

Two directly-quoted, independently verified findings:

- On laundering: *"Incomplete forgetting arises because a single memory
  item may leave derivatives across raw dialogue logs, summarized memory
  cards, vector indexes, reflected lessons, shared stores, and audit
  records."* — a field-level acknowledgment that laundering of
  deletion/revocation across derivative forms is real and unsolved.
- On the bounded-interval question specifically: *"The formal framework
  focuses on point-in-time rollback but does not deeply explore
  bounded-interval revocation after descendants propagate across
  multi-agent systems."*

Author conclusion pulls in a partially opposing direction worth stating
plainly: they argue robust long-term-memory security "cannot be retrofitted
at retrieval or execution time alone, but must be anchored in storage-time
provenance, versioning, and policy-aware retention from the outset" — a
prevention-by-design stance in tension with (not identical to, but relevant
friction against) a retroactive-repair framing.

## Other systems located (briefer)

- **GateMem** (arXiv:2606.18829): multi-principal shared-memory governance;
  evaluates user-initiated GDPR-style deletion, not compromise-triggered
  revocation; no method achieves utility + access-control + forgetting
  simultaneously.
- **MemPoison** (arXiv:2607.14651): attack taxonomy (L1-L3 corruption
  tiers, "context-triggered dormant corruption"); shows write-time defenses
  have structural blind spots for compositional/dormant attacks; proposes
  no revocation mechanism.
- **Synchronized Backflow Unlearning (SBU)** (arXiv:2602.17692): closest
  "removal" mechanism among unlearning papers — dependency-closure-based
  unlearning that prunes and logically invalidates dependent artifacts,
  conceptually adjacent to selective graph repair — but privacy-driven
  (remove specified PII on request), evaluated on medical QA, no
  bounded-interval or laundering-resistance framing, no agent-fleet
  propagation setting.
- **RAGForensics** (cited repeatedly by the survey): proves post-hoc
  traceback is feasible for *static* RAG corpora — explicitly not for
  dynamically updated agent memory, reinforcing rather than closing the
  gap.

## Bottom line

No real, independently verifiable work locates and closes the exact gap:
a source correctly trusted at t0, propagated across agents/sessions at t1,
discovered compromised only in a bounded sub-interval `[t_a, t_b]` at t2,
with selective, laundering-resistant walk-back of exactly that interval's
descendants at t3. This is confirmed by direct textual admission in three
independent sources (TMA-NM, MemLineage, and the field survey), not merely
by absence of search results. The gap is real, narrow, and field-recognized
— but Custody's *current* implementation does not yet occupy it either: it
has no trust-epoch data model (binary vouch/demote only) and its derivation
matching is exact-content-hash, which TMA-NM's own T1 theorem shows is
unsound under laundering. See `NOVELTY_MATRIX.md` and
`RESEARCH_VERDICT.md`.
