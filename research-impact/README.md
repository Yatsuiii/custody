# Keel

**Status: killed on 2026-08-15 by its own pre-registered standard. Do not build
the product.** The engine works and the mechanism is proven; a persistent
Gemini 3.5 maintaining a JSON research state matched it closely enough that
explicit dependency machinery is not justified. The evidence is in
[`RESEARCH.md`](RESEARCH.md) sections 5b, 5c and 5d, and the reasoning is kept
in full rather than deleted, because the way this was killed is the useful part.

A research program is a dependency graph of assumptions, hypotheses, and planned
experiments. When new evidence lands against one assumption, Keel computes what
that broke, what it made redundant, and what still stands, and shows the chain
back to the sentence that caused each change. That is what the code does. What
follows is why it is not enough.

Working codename, provisional. This is a **second, independent project** that
happens to live in this repository so it can reuse the local tooling and cloud
setup. It shares no code, concepts, or product story with the other project
here; everything Keel is lives under `research-impact/`.

Phase 1 (landscape, gap, mechanism, kill conditions) is in
[`RESEARCH.md`](RESEARCH.md). This file is phase 2: the mechanism, proven
offline.

## Run it

```
make check   # ruff, then 99 offline tests, no network and no cloud
make gate    # runs the loop, writes proof-out/phase2.json
make judge   # reads that artifact back and reports PASS/FAIL per gate
```

`make judge` recomputes every state from the recorded event log instead of
believing the artifact. Editing a state, a digest, an excerpt, or dropping an
event out of the log all make it fail, which is the only reason a proof file is
worth writing.

## What `make gate` shows

Seven experiments, six assumptions, two hypotheses, and one new paper:

```
CHANGED
  A2 SUPPORTED -> CONTESTED      because it is contradicted by c-13364a12 (paper), and supported by c-7ba276db (E2 ablation report)
  A6 UNKNOWN   -> SUPPORTED      because it is supported by c-20a4b035 (paper)
  E4 PLANNED   -> STALE          because it requires A2, now CONTESTED
  E7 PLANNED   -> REDUNDANT      because it would establish A6, now SUPPORTED
  H1 ACTIVE    -> REQUIRES_REVIEW because it depends on A2, now CONTESTED
UNCHANGED
  A1, A3, A4, A5 stay put; H2 stays ACTIVE; E1, E2, E3 stay COMPLETED;
  E5 and E6 stay PLANNED
5 changed, 10 unchanged
```

The unchanged list is not padding. A system that marks everything affected is
useless, so the blast radius has to be provably narrow: `E6` tests the very
hypothesis that went under review and is still valid, because it does not rest
on the contested assumption. That distinction is computed, not judged.

Then the graph writes the replacement experiment's specification:

```
targets      A2        the question that came open
discriminates H1       the hypothesis needing separation
may rely on  A3        the premises of the superseded work that still hold
supersedes   E4, E7
```

A candidate built on `A2` is refused with `relies_on_unsafe_assumption:A2`
before anybody reads its method.

## The one rule

> The model may judge one bounded pairwise relation. The graph decides
> everything downstream of it.

- A model is asked only: does this excerpt SUPPORT or CONTRADICT this single
  assumption, and how strongly. It never sees the experiment list, so it cannot
  decide what became stale.
- Every proposed relation carries a verbatim excerpt, and ingestion refuses any
  excerpt that does not occur in the document it cites. A fabricated citation
  fails a string comparison rather than a trust judgment.
- State is a pure function of admitted edges, evaluated assumptions first, then
  hypotheses, then planned experiments. Each state records the exact edge ids
  that caused it, and the report renders those chains.
- `RETIRED` is reachable only through a human decision. No machine path can
  retire a hypothesis.

## States

| Entity | States | Set by |
| --- | --- | --- |
| Assumption | SUPPORTED, CONTESTED, INVALIDATED, UNKNOWN | its evidence edges only |
| Hypothesis | ACTIVE, REQUIRES_REVIEW, WEAKENED, RETIRED | its dependencies and direct evidence; RETIRED by human decision only |
| Experiment | PLANNED, RUNNING, COMPLETED, STALE, REDUNDANT, INVALIDATED | required assumptions, tested hypotheses, and whether its question was settled elsewhere |

Two rules that took thought rather than typing:

**Standing support turns invalidation into a contest.** An assumption believed
for a reason keeps that reason on the record, so a new strong contradiction
against existing support yields CONTESTED, not INVALIDATED. Collapsing those two
is how a system starts crying wolf.

**A completed experiment is never re-judged.** New evidence changes what is
still worth doing, not what already happened. Rewriting the past to look tidy is
the one thing a research record must not do.

## Does the deterministic layer earn its place?

Measured, not asserted, and the answer is not the one this project wanted.
Controlled variants over two research programs, ground truth computed by running
the rules on declared-true relations, three runs each, live `gemini-3.5-flash`.
One system is this architecture; the other is the same model handed the whole
graph, the whole document, and the complete rule set, asked for the impact
directly.

```
make bench-stub     # the harness, offline, free, produces no result
make lock-holdout   # recompute and hash the holdout ground truth
make bench-dev      # the frozen dev suite, live
make bench-holdout  # 18 unseen variants x 3 runs x 4 configurations, live
make bench-judge    # rescores both from the raw model answers, 12/12 and 20/20
```

Two suites. The **dev** set diagnosed a failure; it is frozen and may never
produce a headline number again. The **holdout** was authored over a second
program and hashed before the resulting fix was written, then run once.

| | whole-graph LLM | bounded judgment + engine |
| --- | --- | --- |
| affected-set F1, dev (15 variants) | **0.909** | 0.907 |
| affected-set F1, holdout (18 variants) | **0.993** | 0.939 |
| recall, holdout | 0.987 | **1.000** |
| provenance exactly minimal, holdout | 0.899 | **0.959** |
| impossible states | 0 | **0** |
| residual wrong nodes after correction | 0 | **0** |

**The baseline is more accurate, on both suites, and the fix we designed for the
gap made things worse on unseen cases.** Those are the first two sentences on
purpose. A capable model holding the rules is good at this, so "an LLM cannot do
this" is not a claim this project gets to make.

What the runs do show is that the two systems fail differently, and that the
difference is the same property with opposite signs. This architecture asks
about every assumption, so it never silently skipped one: on the dev set it
found a second relation hidden in a single sentence that the baseline missed in
every run, and on the holdout that same exhaustiveness produced marginal
opinions about an assumption the baseline simply never considered. It also
never emitted an impossible state, cited a justification that was not an edge in
its own graph, or left anything wrong after the bad relations were rejected.
Full breakdown, and the ground-truth caveat the protocol would not let us fix,
in [`RESEARCH.md`](RESEARCH.md) sections 5b and 5c.

## The longitudinal test that ended it

Ten interacting documents, one program, a human correction in the middle, three
systems, thresholds registered in the session contract before the sequence
existed. The baseline that mattered was not the stateless one: A1 keeps a
canonical structured research state and is handed all of it back every step.

| | A0 stateless | A1 persistent model | B this engine |
| --- | --- | --- | --- |
| end-state accuracy | 0.678 | 0.956 | **0.978** |
| correction persistence | n/a | **1.000** | **1.000** |
| regressions | 37 | **5** | 6 |
| auditable justifications | 0.589 | 0.655 | **1.000** |
| calls | 50 | 50 | 400 |

`bench/killcondition.py` computes the verdict from the registered thresholds.
Zero of four criteria were met and the hard override fired: A1 cleared 0.95 on
both end-state accuracy and correction persistence, which was written down in
advance as sufficient to end the thesis. **KILL.**

Neither system ever resurrected the rejected relation. The engine's one wrong
judgment at document two survived all nine remaining steps, faithfully
propagated. The persistent model missed multi-hop consequences and twice marked
a planned experiment COMPLETED, which the engine cannot do. None of that clears
a bar set in advance, and lowering it afterwards is the one thing this project
refused to do at every step.

## What is proven here, and what is not

Proven, offline, and re-checked by an independent judge: propagation, blast
radius, provenance chains, admission refusals, idempotent re-ingestion,
deterministic replay, human override reversal, and the replacement-experiment
check. 21 gates, all passing, on `proof-out/phase2.json`.

Not proven, and not claimed:

- **That this beats a capable model given the same rules.** It does not, on
  affected-set F1. See above.
- **How accurately the pairwise judgment generalises.** 97.4% over 273 dev
  judgments, 96.1% over 432 holdout judgments, on two programs, one model, one
  temperature. On the holdout most of the errors concentrate on a single
  assumption, and some of them are probably incomplete ground truth rather than
  model error, which the locking protocol deliberately forbids us from
  adjudicating after the fact.
- **That the fixture's papers are real.** The internal results are this
  program's own and synthetic by nature; the external paper is written for the
  fixture and labelled as such in `fixtures/arc_program.json`. Phase 3 ingests a
  real arXiv document.
- **That a researcher will declare their dependency edges.** That is the real
  product risk and `RESEARCH.md` says so.

## Phase 3

Gemini 3.5 via Vertex AI for the pairwise judgment and the method prose; ADK for
the surveillance agent that triages arriving papers and asks the researcher
where confidence is low; Firestore for the event log; Cloud Run for both. The
engine in `keel/` does not change when they arrive, because none of them is
allowed inside the propagation.
