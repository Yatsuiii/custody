# E2C — Plan

## Question

E2B showed a benign paraphrase and a malicious paraphrase both get blocked
via the same `resolve()`-miss → default-deny fallback. This experiment
isolates the mechanistic claim underneath that finding: is exact-content
identity genuinely the load-bearing bridge current Custody uses to
reconstruct cross-invocation ancestry, such that *any* change to the
retrieved text — not just a semantic paraphrase — breaks it? This is not
an attack benchmark; no adversary is modeled. It is a falsifier for one
specific mechanistic hypothesis.

## H_E2C (fixed before execution)

Current cross-invocation ancestry reconstruction is content-identity
fragile: exact content → ancestry recovered; changed content (however
small the change) → ancestry lost. Falsified if a trivial, non-semantic
change (Case B) behaves differently from a semantic paraphrase (Case C) —
that would mean something more nuanced than pure exact-match is happening.
Also falsified/incomplete if Case A itself fails, which would mean E2B's
interpretation needs revisiting at the retrieval-path level, not the
matching level.

## Step 1 — existing test coverage, inspected before writing anything new

`tests/test_graph.py:207-268`, class `RetrievalIsAttributedAsACitation`,
three tests. Answering the six required questions directly from the code
(re-run in isolation, confirmed passing: `python -m unittest
tests.test_graph.RetrievalIsAttributedAsACitation -v` → 3/3 ok):

1. **What scenario does it exercise?**
   `test_a_retrieval_matching_the_graph_inherits_its_lineage`
   (`tests/test_graph.py:212-242`): a trusted tool (`crm_lookup`) writes
   `"balance: 500"` in one `take_custody` call (invocation `inv-1`), the
   resulting record is added to a `CustodyGraph`. A separate,
   later `take_custody` call, a different invocation (`inv-2`, via the
   `retrieval()` helper at line 197), retrieves the **exact same string**
   `"balance: 500"` via a `load_memory`-tagged response, once without a
   resolver (control) and once with `resolver=graph`.
2. **Does it cross invocation/session boundaries?** Yes — two separate
   `take_custody` calls, two distinct `invocation_id`s (`inv-1`, `inv-2`),
   exactly the boundary this experiment also needs.
3. **Is the retrieved content byte-identical?** Yes, exactly —
   `retrieval("balance: 500")` reuses the literal string the write used.
   This is precisely Case A's shape.
4. **Is trust/derived_from asserted?** Yes:
   `self.assertIs(after.record.trust, Trust.TRUSTED)` and
   `self.assertEqual(after.record.derived_from, (looked_up.record.id,))`.
5. **Does it reach `instruction_eligible()`/`ExportGateway`?** No — it
   asserts `.trust` and `.derived_from` directly, never calls
   `instruction_eligible()` or constructs an `Export`/`ExportGateway`
   decision. (Trivially implied, since `instruction_eligible()` is just
   `self.trust is Trust.TRUSTED`, but not itself exercised.)
6. **Does it already prove the whole H_E2C hypothesis?** No — it proves
   only the **exact-match positive control** (Case A's claim, at the
   record level) and, via `test_an_unresolved_retrieval_stays_untrusted`
   (`:259-268`), a related-but-distinct case (content that was **never
   written at all**, not a *changed version* of something that was — this
   is closer to this experiment's Case D than to Case B or C). It does
   not test a trivial non-semantic format change (Case B) or a semantic
   paraphrase of content that genuinely was written and trusted (Case C)
   at all. **Verdict on this step: existing coverage answers Case A and
   is reused directly as the positive control (not re-derived from
   scratch); Cases B, C, D require new, minimal test code**, per the
   user's own branching instruction.

## Experiment matrix

One trusted root fact, one shared `CustodyGraph`, written once by a
genuinely trusted tool in Session/Invocation 1, then retrieved in four
different forms across a fresh Invocation 2-5 (one per case, same graph):

- **Root (Session 1)**: `"Acme's payment account is ACCT-SAFE-11."`,
  written by a trusted tool.
- **Case A — exact retrieval**: `"Acme's payment account is ACCT-SAFE-11."`
  (byte-identical).
- **Case B — trivial format change**: `"Acme's payment account is
  ACCT-SAFE-11"` (final period removed; a single-character, non-semantic
  change).
- **Case C — semantic paraphrase**: `"For payment processing, use account
  ACCT-SAFE-11 for Acme."` (same proposition, different wording — the
  same shape as E2B's benign Control C, for continuity).
- **Case D — unrelated text**: `"Globex support hours are 9am-5pm ET,
  Monday through Friday."` (a different proposition entirely; must not
  inherit any authority from the root fact).

Every case measured identically: `resolve()` hit (checked directly, not
inferred), `origin`, `trust`, `derived_from`, `instruction_eligible()`,
and the `ExportGateway` decision for an export citing the resulting
record with the root fact's actionable value (`ACCT-SAFE-11` for A/B/C;
Case D's own unrelated content for D, since citing it for a payment action
would itself be a category error worth surfacing if it ever happened).

## No semantic inference, stated as a hard constraint

No embeddings, fuzzy matching, token overlap, LLM judgement, or string
normalization beyond whatever `custody/origin.py`'s actual `digest()`
(plain `hashlib.sha256`) already does. No `derived_from` edge is ever set
by hand — every edge observed must come from real `take_custody`/
`CustodyGraph.resolve` execution, exactly as in E2A/E2B.

## Verdict taxonomy, fixed before execution

- **EXACT-MATCH-DEPENDENCY-CONFIRMED**: Case A preserves ancestry/
  authority; both B and C lose it, through the same mechanism.
- **EXACT-MATCH-DEPENDENCY-PARTIAL**: some transformations survive and
  others do not — characterize the exact boundary (e.g., if B somehow
  survives while C does not, that would indicate something other than
  pure byte-for-byte SHA-256 matching is in play, which would be a
  significant, surprising code-reading correction).
- **HYPOTHESIS-REJECTED**: Case A itself fails — the E2B interpretation
  would need revisiting at the retrieval-path level, not the matching
  level.
- **EXISTING-TEST-SUFFICIENT**: not expected to apply here, since Step 1
  already established the existing test does not cover B/C/D — recorded
  as a live option only if this experiment's own execution somehow shows
  otherwise.

## What this experiment will not do

No production edits. No defense design or proposal, regardless of result.
No claim beyond what is directly measured on these four cases.
