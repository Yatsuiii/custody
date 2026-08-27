# Research

Two research bodies were produced in this repository, and most of both lives on
frozen experiment branches rather than on this one, which is why this index
exists. The Custody `research/` directory is not on this branch at all.
DecisionTrace's action-compliance pilot is, under `decision-trace/pilot/`, but
its v2 benchmark results are not. Every link below is pinned to a commit SHA
rather than a branch name, so each one resolves regardless and cannot rot if a
branch is advanced or deleted.

Each ran as a falsification programme against its own thesis, with thresholds
fixed before any result was seen and every step scoped as a test rather than as
authorization to build. Both reached conclusions specific enough to act on. The
DecisionTrace benchmark is complete. **The Custody programme is active**, and
its central question is still open.

## Custody: bounded-interval revocation for agent memory

What the programme established, in order: the gap it targets is real and is
independently named as unexplored by a field survey rather than asserted here; a
multi-parent lineage bug in its own foundation, found and fixed; three
external-validity experiments run against a competing system's released code,
plus a mechanistic falsifier that isolated the root cause of one whole failure
class to a single line; and a
complete mechanism design with preregistered falsification gates.

**Current verdict: RESEARCH-ONLY**, which is not BUILD and explicitly not KILL.
The programme is ongoing and this verdict is where the evidence stands today,
not a closing position.
The thesis survives in narrowed form. The programme declined to authorize an
implementation until its own preregistered gate is met. That is the result, not
a shortfall against it. The research also says plainly that calling this
paper-grade today would overclaim.

The adopted question, after the flattering version was rejected for being
"re-marketing an existing hackathon result":

> When a source that was legitimately, correctly trusted at write time is
> later discovered to have been compromised only during a bounded sub-interval
> of its trust lifetime, can a fleet's memory system revoke influence scoped to
> that interval, including influence reached through paraphrase, relay,
> trusted-tool echo, or manufactured corroboration, with materially less
> collateral damage than today's whole-tool revocation?

- [RESEARCH_QUESTION.md](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/RESEARCH_QUESTION.md)
- [RESEARCH_VERDICT.md](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/RESEARCH_VERDICT.md)
- [NOVELTY_MATRIX.md](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/NOVELTY_MATRIX.md)
- [RELATED_WORK_AUDIT.md](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/RELATED_WORK_AUDIT.md)
- [HYPOTHESES.md](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/HYPOTHESES.md)
- [EXPERIMENT_REGISTRY.md](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/EXPERIMENT_REGISTRY.md)
- [THREAT_MODEL.md](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/THREAT_MODEL.md)
- [design/](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/design/DESIGN_FALSIFIER.md)

The `NOVELTY_MATRIX.md` scores this system against four real prior systems and
marks it the weaker one on two rows: authority tracked separately from content,
and laundering-resistant matching.

### Falsification chain

Each experiment was scoped as a falsification test, not as authorization to
build further. Verdict strings are quoted from the source.

| Step | Verdict | What it established |
|---|---|---|
| E0/E1 | `FOUNDATION-SURVIVES` | Reproduced a real multi-parent lineage bug against production code, then fixed it minimally. 10/10 attack variants pass; 381 tests, up from 377, zero regressions. |
| E2 | `EXTERNAL-HARNESS-PARTIAL` | TMA-NM's released code is real and its formal reproduction passed clean. Its headline numbers are measured against the author's own generic stand-in, so no head-to-head number against this system exists anywhere. |
| E2A | `EXTERNAL-FAIL` | Tool-identity trust with no payload inspection, reproduced from an external attack class. |
| E2B | `EXTERNAL-PASS-ACCIDENTAL` | Exact-hash matching cannot distinguish malicious from benign transformation. |
| E2C | `EXACT-MATCH-DEPENDENCY-CONFIRMED` | One line is the entire load-bearing mechanism. A trusted fact retrieved byte-identical is fully preserved; the same fact with a single trailing period removed produces a total loss, byte-for-byte identical in every measured field to a full paraphrase and to an unrelated proposition. A hard cliff, not graded fragility. |
| Design | `DESIGN-CAUTION` | Six primitives derived, three architectures compared, PASS/CAUTION/KILL gates preregistered for E2D. Carry into one isolated falsifier; do not authorize production. |

On the E2 comparison specifically: TMA-NM's data model carries no
derivation field at all, so it cannot represent a multi-parent synthesized
memory even in principle. Post-E1 this system is ahead of it on derivation-graph
expressiveness, while TMA-NM remains ahead on laundering-resistant authority.
Different, only partially overlapping capabilities.

A separate production-equivalence harness, run against real Firestore rather
than local fakes, returned `LOCAL-EQUIVALENCE-SUPPORTED` with two honestly
reported ceiling misses:
[P7 handoff](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/production_b7/P7_CODEX_HANDOFF.md).

### Open problem, currently unsolved

The question the programme exists to answer is still open: how to remove exactly
the poisoned artifacts and nothing else. Two halves, each established by its own
experiment rather than assumed.

**Identification.** `CustodyGraph.resolve` matches on SHA-256 equality, so a
laundered descendant is invisible to revocation. E2C established this is a hard
cliff rather than graded fragility: a trusted fact retrieved byte-identical is
fully preserved, and the same fact with a single trailing period removed is
indistinguishable in every measured field from a full paraphrase and from an
unrelated proposition. Loosening the match is not an available fix, because E2B
established that exact-hash matching cannot separate malicious transformation
from benign transformation. Strict matching misses laundered copies; looser
matching destroys legitimate derived work.

**Repair.** The design packet rules out the obvious shortcut. Pruning a
compromised parent and re-meeting the survivors on unchanged content can raise
the old record, so affected descendants stay `BLOCKED` with no transition back
to `LIVE`. Useful restoration requires a freshly executed transform under a new
record id. Deleting only the poisoned artifact therefore still costs every
downstream record that touched it, until each one is re-derived.

The candidate answer is the structural-envelope architecture in
[research/design/](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/research/design/REPAIR_SEMANTICS.md),
sitting at `DESIGN-CAUTION` with preregistered PASS/CAUTION/KILL gates. It has
not been run. That experiment, E2D, is the next step.

### Known limitations

- The E1 multi-parent fix (`31bd1b0`) is **not yet on this default branch**.
  The bug is fixed in the research and still present in the code on the branch
  a visitor reads first.
- No direct measured comparison against TMA-NM exists. The structural argument
  that this system falls inside the malleable category its theorem covers is
  reasoning, not a measurement.
- E2D has not run. Production is described in the design packet as
  architecturally unshippable until five named conditions are proved.

## DecisionTrace: does structured decision memory beat RAG?

**Result: the advantage the benchmark was built to demonstrate is not
demonstrated.**

The v0 run appeared to show a large gap. The v2 run, which asks one targeted
question per named alternative instead of one broad question per document,
found that gap was "two artifacts pointing in opposite directions": the
structured arm was held down by ground truth it could not have matched, and
RAG was held down by a labelling asymmetry.

Under fair comparison, with the structured store built without ever seeing the
question list and RAG told what it retrieved:

| Condition | Combined | 95% CI | Hallucination |
|---|---|---|---|
| `code_only` | 10% (8/83) | 5%–18% | 2% |
| `rag` | 55% (46/83) | 45%–66% | 7% |
| `structured` | 99% (82/83) | 93%–100% | 0% |
| `structured_ingested` | **87% (72/83)** | 78%–92% | 0% |
| `rag_labelled` | **89% (74/83)** | 81%–94% | 0% |

n = 83 cases across 33 decisions and 4 repositories. The two arms that matter
are the bottom two, and RAG is ahead by two cases, far inside both Wilson
intervals. The verdict under unchanged thresholds is CAUTION, one point below
the KILL line, and the source records the comparison as inconclusive at this
sample size rather than as a win for either arm.

The `structured` row at 99% is included for completeness and should not be
read as the result: that store was built with sight of the question list. The
v0 source names the related threat to validity directly, that
citation-correctness is satisfied by construction for the structured arm, since
every retrieved card carries its own citation inline.
v0 and v2 are different tasks and their headline numbers must not be
differenced, per the source document.

- [RESULTS.md, v0](https://github.com/Yatsuiii/custody/blob/ca53fce3ef8f6212e417238f976f2623d8a5fb9e/decision-trace/RESULTS.md)
- [RESULTS_V2.md](https://github.com/Yatsuiii/custody/blob/ca53fce3ef8f6212e417238f976f2623d8a5fb9e/decision-trace/RESULTS_V2.md)
- [RESULTS_AUTHORITY_PROSPECTIVE.md](https://github.com/Yatsuiii/custody/blob/1b5bf510360dc8338a90c4027848b2a93bcfe90a/decision-trace/RESULTS_AUTHORITY_PROSPECTIVE.md)
- [Action-compliance pilot](https://github.com/Yatsuiii/custody/blob/0983bdcfe5db4e16df05b70691bc6530779efe61/decision-trace/pilot/task-02-django-index-together-superseded/SANITY_RESULTS.md),
  ten hand-built tasks drawn from Kubernetes, Django, pip, CPython, packaging,
  OpenTofu, axum and Go, each with its own per-task sanity results. Linked at
  one task; browse the sibling directories for the rest.

## Method

Both bodies ran under the same discipline, recorded in
[.claude/SESSION_CONTRACT.md](https://github.com/Yatsuiii/custody/blob/ca54d84e077d0a5584f79edec6ef54c4629ce61b/.claude/SESSION_CONTRACT.md):
a written contract naming objective, branch, allowed files, non-goals and
acceptance gates before any edit; thresholds fixed before results were seen and
not relaxed afterwards; failures classified before being fixed; and results
reported against the preregistered gate rather than against what would have
looked better.
