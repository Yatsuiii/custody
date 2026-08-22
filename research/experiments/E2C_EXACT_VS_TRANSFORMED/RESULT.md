# E2C — Result

## Verdict: EXACT-MATCH-DEPENDENCY-CONFIRMED

Case A (byte-identical retrieval) preserves ancestry and authority
completely. Cases B (single-character, non-semantic change) and C
(semantic paraphrase) both lose it completely, through the literal same
code path and identical downstream values. There is no partial-credit
boundary to characterize — the dependency is a strict cliff, not a
gradient, so `-PARTIAL` does not apply.

## What ran

`PYTHONPATH=. .venv/bin/python
research/experiments/E2C_EXACT_VS_TRANSFORMED/attack.py`, against real,
unmodified `custody.origin.take_custody`, `custody.graph.CustodyGraph`,
`custody.action.ExportGateway`, at the frozen E0-E2B commit chain
(`cf2ac74dbe3a0963d28dc6550787905e19e84494`). `git diff --stat custody/`
empty throughout; full suite 381/381 both before and after.

## Measured outcome, all four cases

| Case | Text | `resolve_hit` | `trust` | `derived_from` | `instruction_eligible` | `action_allowed` |
|---|---|---|---|---|---|---|
| A — exact | byte-identical | `True` | `trusted` | `[root_id]` | `True` | `True` |
| B — trivial format change | period removed | `False` | `untrusted` | `[]` | `False` | `False` |
| C — semantic paraphrase | reworded | `False` | `untrusted` | `[]` | `False` | `False` |
| D — unrelated text | different proposition | `False` | `untrusted` | `[]` | `False` | `False` |

B, C, and D are not merely similarly blocked — every recorded field is
byte-for-byte identical across the three of them.

## 1. Verdict

EXACT-MATCH-DEPENDENCY-CONFIRMED.

## 2. Existing test coverage

`tests/test_graph.py:207-268`,
`RetrievalIsAttributedAsACitation.test_a_retrieval_matching_the_graph_
inherits_its_lineage`, already proves Case A's exact claim at the record
level (byte-identical cross-invocation retrieval inherits `trust` and
`derived_from` from the graph), independently re-run in isolation before
this experiment (`python -m unittest
tests.test_graph.RetrievalIsAttributedAsACitation -v` → 3/3 ok) and
reused as the positive control rather than re-derived from scratch. It
does not cover Cases B or C (a genuine but non-semantic textual change, or
a semantic paraphrase of content that was actually written), and its
closest relative to Case D (`test_an_unresolved_retrieval_stays_
untrusted`) tests content that was *never written at all*, not a changed
version of something that was — a related but distinct question. New,
minimal test code (this experiment's `attack.py`) was required for B, C,
D, per `PLAN.md`'s own branching instruction.

## 3. Case A (exact) result

Full ancestry and authority preserved: `resolve_hit=True`,
`trust=trusted`, `derived_from` names the real root record's id,
`instruction_eligible=True`, `action_allowed=True`.

## 4. Case B (minimal change) result

Total loss, identical in every measured field to Case C and Case D: a
single removed trailing period is sufficient to change the SHA-256 digest
and produce a complete `resolve()` miss.

## 5. Case C (paraphrase) result

Total loss, identical to Case B in every measured field. Reproduces
E2B's Control C finding exactly, now isolated against a controlled
comparison to a non-semantic change rather than only against a benign/
malicious contrast.

## 6. Case D (unrelated) result

Total loss, as expected for the negative control — confirms the harness
correctly refuses to inherit authority for genuinely unrelated content,
and confirms that B and C are not merely "as safe as an unrelated
proposition" by coincidence, but via the literal identical mechanism.

## 7. First code-path divergence

`custody/graph.py:187-197`, `CustodyGraph.resolve`'s `==` comparison on
two SHA-256 digests. This is the sole point where Case A's fate parts
from B/C/D's — a cryptographic hash equality check with no notion of
"close." Everything before it (the write, the graph population policy)
and everything after it (the `trust.of("load_memory")` fallback, the
`ExportGateway` refusal) is identical machinery shared by all four cases;
only the boolean result of this one comparison differs.

## 8. Is exact content identity load-bearing?

Yes, confirmed directly and without qualification for the mechanism this
experiment isolates: cross-invocation ancestry reconstruction in current
Custody has exactly one gate (`CustodyGraph.resolve`'s exact-hash match),
and that gate is binary with no partial-credit behavior. A single
character is as disqualifying as a complete rewording.

## 9. What this changes about the research problem

Sharpens `RESEARCH_QUESTION.md`'s framing with a now-precise mechanistic
fact rather than a general "exact-hash matching is fragile" statement:
the fragility is not a matter of *degree* (e.g., "small changes survive,
big ones don't") — it is a hard, all-or-nothing cliff with a single load-
bearing line of code. Any future mechanism design (explicitly not
proposed here) would need to replace or supplement exactly this one
comparison, not tune a threshold on it — there is no threshold to tune,
since the current mechanism has no notion of distance at all. This also
means E2B's `EXTERNAL-PASS-ACCIDENTAL` finding generalizes further than
"paraphrase specifically": the identical accidental-block behavior would
occur for a typo, a reformatted date, a reordered clause, or any other
byte-level change a legitimate system might introduce, not only for
adversarial or semantic transformations.

## 10. Enough characterization to begin mechanism design?

Not decided here — this experiment's scope is characterization only, per
its own non-negotiable rule, and this response does not propose or
evaluate readiness for mechanism design. What exists after E2A, E2B, and
E2C is: one clean externally-sourced authority-laundering failure (E2A,
tool-identity trust), one externally-sourced accidental-block finding with
measured collateral damage (E2B), and one precise, code-located
mechanistic root cause for both the D/E red-team gap and E2B's collateral
finding (E2C, this experiment). Whether that constitutes "enough" is a
judgment call for the next explicitly authorized step, not this one.
