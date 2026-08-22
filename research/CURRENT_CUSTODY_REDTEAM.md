# Current Custody: Red-Team Analysis

Grounded in `custody/*.py` as of branch `research/memory-poisoning-thesis`
(parent `hardening/fleet-track-pre-submission`). Every verdict cites the
code path that produces it, not README prose. README claims are treated as
hypotheses to verify, not evidence.

Two structural facts drive almost every verdict below and are stated once
here rather than re-derived twenty times:

1. **Trust is a per-tool-name (or per-tool-revision-digest) boolean, never
   time-bounded.** `ToolTrust.of()` (`custody/origin.py:194-197`) and
   `TrustCatalog.trust_for()` (`custody/catalog.py:160-167`) answer
   trusted/untrusted from the current grant set only. `Grant.vouched_at`
   (`custody/catalog.py:33`) is stored but never read by any trust decision
   — it is evidentiary, not load-bearing. There is no trust epoch, validity
   interval, or "trusted from t0 to t1" concept anywhere in the codebase.
2. **Derivation edges are populated by exactly two mechanisms**: (a)
   same-invocation taint propagation, one boolean flip per invocation
   (`custody/origin.py:330-334`, tracked in the `tainted` dict), and (b)
   exact-content-SHA-256 match against an already-admitted record via
   `CustodyGraph.resolve` (`custody/graph.py:187-197`), consulted only when
   a `load_memory`-class tool response's *exact* text matches. Anything that
   changes the wording, blends two sources, or arrives outside a
   structurally visible `function_response` event produces no edge at all.

| Case | Verdict | Why (code-grounded) |
|---|---|---|
| A. Direct malicious-memory writes | **PARTIAL** | Tool-authored malicious writes: PASS — default-deny `ToolTrust` (`origin.py:184-197`, `catalog.py:160-167`) means an unvouched tool is UNTRUSTED by construction. User-authored malicious writes: **NOT REPRESENTABLE** — `author == USER_AUTHOR` is unconditionally `Trust.TRUSTED` (`origin.py:345-346`) with no content check of any kind; Custody's origin model answers *where content structurally entered*, never *is this content safe*, so a malicious "user" turn (compromised account, forged client) is trusted by axiom. |
| B. Indirect prompt injection entering memory | **PASS** | Same-invocation taint (`origin.py:330-366`) labels the model's restatement of a hostile tool response `DERIVED`/`UNTRUSTED`; `split_session` (`custody/service.py:140-153`) withholds the whole event. Demonstrated by `make demo`. |
| C. Sleeper/delayed triggers | **PARTIAL** | If the poisoning tool was already untrusted at write time, `instruction_eligible()` (`origin.py:122-128`) stays `False` forever — a delayed retrieval is still refused at `ExportGateway` (`action.py:85-95`). But there is no temporal/behavioral sleeper-pattern detector anywhere: trust is a single write-time snapshot with no re-evaluation over time absent a manual `demote`+`revoke`. A sleeper written while the source was *legitimately* trusted (case J/K) persists as trusted indefinitely with no automatic decay. |
| D. Summarization laundering | **PARTIAL** | In-invocation: PASS by design (docstring `origin.py:8-12`). Cross-invocation: `take_custody`'s `tainted`/`lineage` dicts are local to one call over one session's events (`origin.py:229-240`) and do not persist across sessions except via exact-hash `resolve()`. A paraphrase changes the hash, `resolve()` returns `None`, and the content is re-judged as fresh against `trust.of(runtime_name)` — usually UNTRUSTED (fail-closed, safe but loses the lineage edge needed for *surgical* future revocation). **Structural blind spot**: Custody only inspects `Event.content.parts`; any retrieved-memory content a downstream system injects into model context outside a structural `function_response` event is invisible to `take_custody` end to end. |
| E. Paraphrase laundering | **PARTIAL** | Same mechanism and same verdict as D — paraphrase is a special case of cross-invocation summarization from Custody's point of view; no separate handling exists. |
| F. Trusted-tool echo laundering | **FAIL — externally confirmed, 2026-08-22** (was code-reading FAIL; now measured, `research/experiments/E2A_TMANM_TOOL_ECHO/`) | `verdict = trust.of(runtime_name)` (`origin.py:325`) is a pure tool-*identity* lookup; it never inspects what the tool's backend actually returned or where that payload's own data originated. A currently-trusted tool that echoes/relays attacker-influenced upstream data is stamped `Origin.TOOL`, `Trust.TRUSTED` with full confidence, indistinguishable from genuine trusted output. Content provenance and tool-identity trust are conflated by construction. **E2A ran TMA-NM's (arXiv:2606.24322) actual published `tool_echo` attack construction against unchanged Custody**: the attacker's value received identical `Trust.TRUSTED`/`instruction_eligible()==True` standing to a genuinely trusted value and cleared `ExportGateway` with no denial — verdict EXTERNAL-FAIL, code-attributable to a single line (`origin.py:325`), not several interacting mechanisms. A second control confirmed Custody's revision mechanism gives no *write-time* protection either: a pre-issued revocation for an already-known-compromised revision does not stop a matching new write from being admitted trusted. |
| G. Cross-agent propagation | **PARTIAL** | Mechanism proven live for exact-match relay (`live_chain.py`, README lines 726-770): `derived_from` follows a `load_memory` response whose text hash matches an earlier record, across departments. Inherits D/E's fragility — any paraphrase during the relay hop breaks the edge. |
| H. Fake independent corroboration | **FIXED, 2026-08-22** — see `research/experiments/E0_CURRENT_LINEAGE_REPRO/` and `E1_MULTIPARENT_LINEAGE/`. Originally **FAIL**: `lineage` (`origin.py:240`, pre-fix) stored **one** upstream `(record_id, tool, revision)` triple per invocation, overwritten on every subsequent tool-response or model turn. A model turn synthesizing two separately-trusted sources in one invocation got `derived_from = (most_recently_seen_id,)` only — the edge to the *other* source was silently dropped, confirmed by E0's reproduction (`test_a_synthesis_of_two_trusted_sources_keeps_both_parents`, pre-fix behavior recorded in E0's RESULT.md). E1's fix makes `lineage` accumulate every distinct trusted arrival per invocation instead of overwriting; `derived_from` now lists every accumulated predecessor. Verified against 10 attack-case variants, 0 regressions across the full 381-test suite. **Residual gap, unchanged by this fix**: attribution is still all-or-nothing per parent (case S) — a parent contributing only a small substring gets the same full-strength edge as a dominant one — and the fix does not extend past one invocation's exact-hash/taint tracking, so cross-session laundering (D/E/F) is untouched. |
| I. Memory retrieval causing a consequential action | **PASS** | `ExportGateway._judge` (`action.py:80-95`) refuses any export with no citations or with a citation whose `instruction_eligible()` is false. Demonstrated by `make demo`'s export refusal. |
| J. Source trusted initially, compromised later | **PARTIAL** | The mechanism exists and is real: `TrustCatalog.demote` (`catalog.py:137-150`) + the Auditor's `CustodyGraph.revoke` sweep (README "Provenance Auditor" section) removes every descendant of the demoted tool. But granularity is **the entire tool's lifetime**, not a bounded interval — see K. |
| K. Partial compromise interval (trusted 30 days, compromised days 12-18) | **FAIL** | No trust epoch exists to bound a revocation to a sub-interval (see structural fact 1, above). `descendants_for_revision` (`graph.py:111-135`) can isolate by *tool-definition-schema digest*, but a supply-chain/backend-data compromise that leaves the tool's declared schema untouched produces an identical `source_revision` before, during, and after the compromise window — days 1-11, 12-18, and 19-30 are indistinguishable to `_revoke`. This is the sharpest gap in the system and the one the candidate research thesis targets directly. |
| L. Source revision replaced while preserving schema | **FAIL / NOT REPRESENTABLE** | `ToolDefinition.revision = _digest(self.definition)` (`custody/revision.py:94-95`) hashes the *declared schema*, and `RUNTIME_DRIFT` (`revision.py:43-49`) additionally checks the *serving Cloud Run image digest* — but neither inspects the tool's upstream/backend data source. A schema-and-image-stable tool whose underlying data source is swapped or compromised produces no detectable signal anywhere in `custody/revision.py`. |
| M. Mixed benign + compromised derivation | **PARTIAL** | Within one invocation: conservative fail-closed (any untrusted arrival taints the whole invocation, `origin.py:330-334`) — safe, but total: no partial/weighted attribution is representable (see S), unchanged by the H/R fix. Across multiple *trusted* sources within one invocation, the missing-edge failure this row originally described was the same `lineage` bug as H/R and is now fixed (see `research/experiments/E1_MULTIPARENT_LINEAGE/`) — a synthesis of two trusted-at-write-time sources now correctly carries edges to both, so it is no longer possible for one of them to go missing silently. |
| N. Cycles / repeated retrieval and rewriting | **PASS** | `_walk` (`graph.py:137-147`) only ever adds a `record_id` to `found` once (`r.id not in found` guard), so termination is guaranteed. `derived_from` edges can only point to already-existing records at construction time (single forward pass over `events`, `origin.py:242-289`), so a true cycle cannot be constructed through this API at all. |
| O. Unknown or missing provenance | **PASS** | `Refusal.NO_INVOCATION` / `NO_AUTHOR` (`origin.py:55-56`, enforced at `:261-268`) refuse outright rather than defaulting to trusted. Default-deny confirmed. |
| P. Provenance metadata tampering | **FAIL (assumption, not a control)** | `author` and `invocation_id` are read directly off the caller-supplied ADK `Event` object (`origin.py:248-249`) with no signature or identity check binding them to anything real. Nothing in `custody/store.py` or `custody/firestore_store.py` authenticates a `CustodyRecord` at rest (protection there is Firestore/SQLite access control, an infra boundary, not a Custody-internal one). Anything with write access upstream of `take_custody`, or direct write access to the store, can forge `author == "user"` and mint an unconditionally trusted record. This is a silently assumed trusted-computing-base boundary today, not a documented one. |
| Q. Trusted principal itself compromised | **FAIL / explicitly out of scope** | `origin.py:345-346` trusts `author == "user"` unconditionally, with no session-risk or identity-confidence signal. There is also no revocation primitive keyed on `author`/principal: `CustodyGraph.descendants` keys strictly on `source_tool` (`graph.py:108`), and user-authored records carry no `source_tool` at all, so a compromised human account's writes cannot be surgically revoked by any existing mechanism. |
| R. Multiple compromised roots converging on one descendant | **FIXED, 2026-08-22** — same fix as H (identical root cause). Verified directly: case 3 (A→X; B→Y; X+Y→Z) and case 9 (divergence/reconvergence, A→X→Z and A→Y→Z) in `E1_MULTIPARENT_LINEAGE/RESULT.md` both confirm revoking *either* of two independent compromised roots now reaches a shared/converged descendant, symmetrically. Pre-fix, only one direction worked (whichever root happened to be processed last). |
| S. One poisoned ancestor, weakly contributing to a mostly-benign memory | **PARTIAL** | Taint is boolean, not weighted (`origin.py:330-334`): a 95%-benign/5%-poisoned-derived memory is quarantined wholesale. Safe (no false-trust), but there is no representation of partial contribution, so the precision/collateral-damage tradeoff Phase 6 needs a metric for cannot even be computed from current data — the system has no notion of "how much" a given ancestor contributed. |
| T. Repair after poison already influenced a decision | **FAIL / explicit non-goal** | `graph.revoke`/`revoke_revision` (`graph.py:149-183`) delete descendant *records*, and `RevokingMemoryBankGraph` propagates that to live Memory Bank deletion — but nothing links a past `ExportGateway.Decision` (`action.py:42-56`) or any other consequential action back to the records that authorized it. An export already allowed before a later revocation cannot be identified, flagged, or rolled back by anything in this codebase. |

## Summary count (updated 2026-08-22 after E0/E1)

PASS: 4 (B, I, N, O) · FIXED: 2 (H, R — see E0/E1 experiments) · PARTIAL: 8
(A, C, D, E, G, J, M, S) · FAIL: 5 (F, K, L, P, Q) · NOT REPRESENTABLE
(folded into A/L/T above): 3

M's verdict is now stale in one respect: its "confirmed correctness FAIL"
clause described the same `lineage` bug H/R already named and that bug is
now fixed. M's PARTIAL verdict otherwise stands unchanged — the
conservative whole-invocation taint behavior for genuinely mixed
benign+compromised content was never the bug, and remains exactly as
described.

## The one finding that matters most for the research thesis

**K is a clean, code-verified FAIL, and it is exactly the gap the candidate
thesis names.** Custody already does "retroactive revocation" — that is the
project's existing headline claim, live-proven (`make revoke`,
`make live-fleet`, `make live-chain`) — but every revocation mechanism in
the codebase (`descendants`, `descendants_for_revision`, `revoke`,
`revoke_revision`) operates over the *entire lifetime* of a tool or tool
revision. There is no code path, no data field, and no test anywhere that
scopes a revocation to a bounded compromise interval within a tool's
trusted lifetime. This means the research question cannot honestly be
framed as "does Custody solve memory poisoning" (it does not, and does not
claim to) or even "can Custody revoke retroactively" (it already can, at
tool/revision granularity) — the only defensible framing is the *narrower*
one: **bounded-interval, laundering-resistant retroactive revocation with
selective (not whole-tool) collateral damage.** H and R (silently dropped
multi-parent edges) were the second most important finding: they were
*correctness bugs* in the existing derivation graph, not scope gaps, and
needed fixing regardless of whether the broader research thesis survives —
they meant the current system could already under-count blast radius
silently, on real multi-source synthesis. **Update, 2026-08-22: H and R are
now fixed** (`research/experiments/E0_CURRENT_LINEAGE_REPRO/`,
`E1_MULTIPARENT_LINEAGE/`), on a dedicated branch
(`research/e0-e1-multiparent-lineage`), verified against 10 attack-case
variants with zero regressions across the full test suite. K remains
open and unaddressed — this fix corrects *which* ancestors a record is
connected to, not *when* a tool's trust status applies, so it does not
touch the interval-scoping question at all. The fix does, however, remove
a real doubt about whether the derivation graph was even a sound
foundation to build interval scoping on top of; see
`RESEARCH_VERDICT.md`'s updated reasoning.
