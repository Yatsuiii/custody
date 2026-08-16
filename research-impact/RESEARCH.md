# Keel, phase 1: is a research change-impact engine worth building?

Working codename **Keel**. Provisional, stands for nothing, chosen so the name
cannot smuggle in a product claim before the mechanism is proven. This is a
second, independent hackathon entry under the **Collaborative Partner** track.
It shares a repository with the other project for tooling and cloud setup only,
and shares no concepts, code, or story with it.

Investigated and written 2026-08-15. Every source below was read this session.
Where a claim rests on a search summary rather than the product or paper itself,
it says so, because "a competitor probably does not do X" is exactly the kind of
claim that gets a submission taken apart in judging.

## The one sentence

> A research program is a dependency graph of assumptions, hypotheses, and
> planned experiments. When new evidence lands against one assumption, the
> artifacts that depended on it are computed, not narrated.

## 1. Problem evidence

The claim is that research programs carry undocumented dependency structure, and
that the cost of not tracking it is paid slowly and invisibly. Three things
support that, in descending order of how much weight they can bear.

**Strong: an entire methodological field exists to do this by hand.** Clinical
medicine calls it living evidence. Guideline bodies run continuous "evidence
surveillance" and define explicit "triggers" that say when new studies force a
recommendation to be re-examined; a change in evidence is the trigger behind
75% of updates, and surveillance is tiered weekly / monthly / quarterly by how
likely a question is to be disturbed ([J Clin Epidemiol, living guidelines
methods paper 5](https://www.jclinepi.com/article/S0895-4356(22)00347-X/fulltext);
[3 years of daily evidence surveillance for Australia's living COVID-19
guidelines](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11795968/)). That is a
change-impact process, staffed by people, because no machine-readable dependency
structure exists to compute it from. The existence of the profession is the
evidence that the problem is real; its cost is the evidence that automating the
propagation is worth something.

**Moderate: the software analogue is measured.** A 2026 position paper on
tracking the epistemic status and temporal validity of architectural decisions
cites a Google SRE finding that 60% of production outages trace to stale
assumptions about system behaviour ([arXiv 2601.21116](https://arxiv.org/html/2601.21116)).
Different domain, same failure shape: a decision was correct under a premise,
the premise moved, nothing recomputed what depended on it. Treat this as an
analogy that motivates, not as evidence about research programs.

**Weak, and labelled as such: no dataset counts wasted experiments caused by
stale assumptions.** I could not find one. Any claim that "researchers waste N
months" would be invented. The honest version is: the practice of surveillance
is real and expensive, the machine-readable substrate for it is missing, and
whether the wasted-experiment cost is large is a bet this project is making, not
a fact it has.

## 2. Who already solves adjacent pieces

Five clusters. None of them is the product, and two are close enough that they
have to be named in the README rather than hidden.

### 2a. Generation-side AI scientists. They produce hypotheses; they do not maintain yours.

- **Google Co-Scientist** (Gemini, multi-agent, now shipping as Hypothesis
  Generation inside Gemini for Science, with a Nature paper). Its loop is
  generate, debate, rank via tournaments, evolve. I read the Gemini Enterprise
  documentation directly: it takes "a research goal in natural language" and
  returns "a comprehensive research roadmap". The documentation is **silent on
  persistence across sessions, on tracking one user's program over time, on
  modelling assumptions or dependencies between hypotheses and experiments, and
  on impact analysis when new evidence arrives**
  ([docs](https://docs.cloud.google.com/gemini/enterprise/docs/co-scientist-and-alphaevolve),
  [DeepMind blog](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/)).
  Silence in documentation is not proof of absence, and access is gated
  ("Access to these agents is restricted"), so this is the single most important
  open verification: **if Co-Scientist maintains a durable, dependency-aware
  program state, our gap narrows sharply.** Nothing found says it does.
- **Kosmos** (Edison Scientific, spun out of FutureHouse). A 20-cycle run reads
  ~1,500 papers, writes ~42,000 lines of code, and every conclusion is traceable
  to the code line or literature passage behind it; independent scientists rated
  79.4% of report statements accurate
  ([Edison Labs](https://labs.edisonscientific.com/research/announcing-kosmos/),
  [AIwire](https://www.hpcwire.com/aiwire/2025/11/07/futurehouse-spins-out-edison-scientific-launches-kosmos-ai-for-research/)).
  Kosmos is the strongest counter-argument on provenance: it already does
  claim-to-source traceability, better resourced than we ever will. But its unit
  is **a run and its report**. It does not hold a researcher's standing program
  between runs and tell them what a new paper broke in it. Also note the number:
  79.4% accurate statements is 1 in 5 wrong, from the best-funded system in the
  category, which is the empirical case for not letting a model own the
  propagation step.
- **AutoSci** ([arXiv 2605.31468](https://arxiv.org/abs/2605.31468)) is the
  closest published architecture: SciMem splits long-term knowledge memory from
  "active research memory" holding project-level ideas, experiments, manuscripts
  and reviews, and SciEvolve turns feedback into versioned updates. From the
  abstract and architecture section I could retrieve, it does not model
  assumption dependencies or invalidate prior plans when new evidence arrives.
  Unverified from the full paper; flagged as the paper to read line by line
  before building the real product.
- **AutoResearch negative knowledge** ([arXiv 2606.21024](https://arxiv.org/abs/2606.21024))
  keeps failures as typed, bounded records in a Research Graph with Question,
  Experiment, and Finding nodes so later agents can adopt or reject them. Same
  instinct as ours (structure beats prose, failures are assets), applied to
  agent self-improvement rather than a human's program. No downstream
  invalidation.
- Older, well known, same shape: Sakana's AI Scientist, Agent Laboratory,
  Sibyl-AutoResearch. All are pipelines that produce research output.

**What they solve:** generating and critiquing hypotheses, running analyses,
tracing a conclusion back to its source. **What none does:** hold *my* program's
assumptions across months and tell me which of *my* planned experiments a new
paper just made pointless.

### 2b. Claim-level literature evidence. They classify; they do not propagate.

- **scite** is the sharpest prior art on the semantic step. It has extracted
  1.6B+ citation statements from full text and classifies each as Supporting,
  Contrasting, or Mentioning ([scite](https://scite.ai/),
  [methodology](https://scite.ai/blog/characteristics-of-scite-citation-statements)).
  So "does this paper support or contradict that one" is a solved, productised
  problem at industrial scale. **We should not compete there, and should treat
  scite-style classification as a component we could consume rather than a moat
  we invent.** What scite has no notion of is *my* assumption A2, *my* hypothesis
  H1, or *my* experiment E4. Its graph is papers citing papers, not a research
  program.
- **Elicit, Consensus, Undermind, Atlas** are retrieval, extraction, and
  synthesis over papers, some with project workspaces that hold sources, notes
  and summaries (search summaries read 2026-08-15, not verified in-product).
  A workspace that stores papers is not a dependency graph over planned work.
- **Scientific claim verification research** (SciFact, SciFact-Open, MultiVerS,
  and the 2026 line: DeepSciVerify, SciLens, SCIVER) is the academic version of
  the same semantic step, and it is not saturated: a 2026 analysis of SciFact's
  own gold labels found errors worth 15+ F1 points
  ([BioNLP 2026](https://aclanthology.org/2026.bionlp-1.9.pdf)). Useful
  calibration: the supports/refutes judgment is genuinely hard, which is the
  argument for containing it rather than building a cascade on top of it.

### 2c. Living evidence synthesis. Same job, one domain, humans in the loop, no program graph.

**Trialstreamer** monitors PubMed daily, classifies RCT reports with a validated
model (recall 0.97, precision 0.52) and auto-extracts PICO characteristics
([medRxiv](https://www.medrxiv.org/content/10.1101/2020.05.15.20103044.full.pdf)).
**Nested Knowledge** runs updatable searches inside the same platform as
screening and extraction, with AI as a second screener under human adjudication
([Nested Knowledge](https://about.nested-knowledge.com/2026/04/15/from-rapid-review-to-living-evidence-synthesis/)).
The 2026 JMIR "Phases of Living Evidence Synthesis Using AI" paper frames the
whole pipeline ([JMIR](https://www.jmir.org/2026/1/e76130)).

**What they solve, and it is a lot:** continuous surveillance, relevance
triage, keeping one review current. **What they do not do:** they update *a
review*, a single document whose conclusions are re-derived. They do not hold a
forward-looking program of planned experiments and mark individual ones stale,
redundant, or still valid. The blast radius of new evidence is computed by a
human reading the review.

### 2d. Structured scientific knowledge. The representation exists; the propagation does not.

- **Nanopublications**: assertion + provenance + publication info, immutable,
  retract-or-supersede only. A recent extension adds a fourth graph, *knowledge
  provenance*, precisely so that "supporting and conflicting pieces of evidence
  ... need to be tracked and referred to"
  ([CEUR 3937 paper 10](https://ceur-ws.org/Vol-3937/paper10.pdf)). This is the
  closest thing to our provenance model and it is a standard we should borrow
  from rather than reinvent.
- **ORKG** structures contributions, methods, materials, results as interlinked
  machine-readable statements ([ORKG](https://www.l3s.de/research-at-l3s/all-projects/open-research-knowledge-graph/)).
  Nothing found describes contradiction handling or state propagation between
  statements.
- **W3C PROV / RO-Crate / DVC / MLflow** version artifacts and record derivation.
  Derivation recorded is not derivation acted on: none of them says "this
  recorded thing is now stale because an upstream premise changed".

### 2e. Dependency invalidation mechanisms. The machinery exists, aimed elsewhere.

This is where the actual mechanism comes from, and it is old.

- **Truth maintenance systems.** Doyle's JTMS (justifications), de Kleer's ATMS
  (assumption sets). Literally: beliefs carry the justifications that support
  them; retracting a premise deterministically retracts what rested on it. The
  2026 literature is rediscovering this for LLM agents, and one write-up states
  the reason cleanly: symbolic belief systems used to require hand-engineering
  to get structure out of text, and "what LLMs change is that structured belief
  extraction is now something you can prompt for" (search-summarised from the
  2026 TMS/belief-revision cluster).
- **LLM agent memory, 2026 cluster**: NeuSymMS (neuro-symbolic self-curating
  memory, [2605.17596](https://arxiv.org/html/2605.17596v1)), TOKI (bitemporal
  operator algebra for contradiction resolution in agent memory,
  [2606.06240](https://arxiv.org/pdf/2606.06240)), Kumiho (AGM belief revision as
  a Neo4j property graph), "When Memory Updates but Behavior Does Not"
  ([2608.01619](https://arxiv.org/html/2608.01619v1)) on repairing stale implicit
  dependencies. **Domain: an agent's own memory about a user.** Not a research
  program, no experiments, no human owner of the decision.
- **EA-Graph** ([2608.04278](https://arxiv.org/html/2608.04278v1)) is the closest
  mechanical relative and deserves the most honesty. Coding agents, verification
  claims anchored to content-addressed artifact hashes; when an upstream change
  lands, rehash the anchor, and a claim becomes *unaffected*, *affected*, or
  *unprovable*. Invalidation is deterministic; the LLM is not asked to judge it.
  Evaluated on synthetic repositories with ground truth true by construction,
  ANCHOR vs PROSE vs NONE, F1 on the affected set. **Our mechanism is the same
  shape in a different domain, and their evaluation design is the one we should
  copy.** The difference that matters: their trigger is a hash change, which is
  free and exact. Ours is "does this claim contradict this assumption", which is
  a judgment. That is the whole engineering problem.
- **Build systems and data lineage** (Make, Bazel, dbt staleness, OpenLineage)
  are the everyday proof that reverse-dependency invalidation is a solved
  pattern when the edges are explicit. Nobody has the edges for research.

## 3. The exact unresolved gap

Put the five clusters on one line each and the hole is visible:

| Who | Holds *your* program state across months | Typed dependency edges (assumption to hypothesis to experiment) | Deterministic downstream invalidation | Verbatim provenance per edge |
| --- | --- | --- | --- | --- |
| Co-Scientist / Kosmos / AutoSci | no (unverified for Co-Scientist) | no | no | Kosmos: yes, per report |
| scite / Elicit / Consensus | papers, not program | no | no | scite: yes, per citation |
| Living evidence platforms | one review | no | no (human) | partial |
| Nanopublications / ORKG | n/a | partial (representation only) | no | yes |
| TMS / EA-Graph / dbt | n/a | yes, other domains | yes | hash-anchored |

**The gap: nobody keeps a researcher's forward-looking program (assumptions,
hypotheses, and specifically *planned experiments*) as a typed graph, and turns
one new piece of literature evidence into a computed, minimal, provenance-backed
set of state changes over it.** Every ingredient exists separately. Nothing
assembles them, and the assembly is where the useful behaviour lives, because
the answer a researcher wants is not "here is what this paper says" but "E4 is
now pointless, E5 still matters, and here is the chain".

## 4. The proposed mechanism

One rule, applied without exception:

> **The model may judge one bounded pairwise relation. The graph decides
> everything downstream of it.**

Concretely, four parts.

**(1) A narrow semantic boundary.** The only thing a model is ever asked is:
given this excerpt and this single assumption statement, does it SUPPORT,
CONTRADICT, or is it UNRELATED, and at what strength. One claim, one assumption,
one answer, structured output, no free reasoning about the program. It never
sees the hypotheses or the experiment list, so it cannot decide their fate. This
is deliberately the step where the field's accuracy is worst (see 2b), which is
why it is the step that gets contained.

**(2) Excerpt-anchored provenance, checked mechanically.** Every proposed edge
must carry a verbatim excerpt from the source document. Ingestion normalises
whitespace and requires the excerpt to appear literally in the stored source
text. An edge whose excerpt is not found is refused, not down-weighted. This is
cheap, and it converts "fabricated provenance" from a trust problem into a
string-containment check. It is also the reason a human can audit any claim in
one click.

**(3) Deterministic state policy and propagation.** Node states are a pure
function of admitted edges, evaluated in a fixed order:

- an assumption's state comes only from its evidence edges (tally rules,
  strength thresholds, human confirmation flags);
- a hypothesis's state comes only from its dependency edges and direct result
  edges;
- a planned experiment's state comes only from the assumptions it requires and
  the proposition it would establish.

Propagation walks reverse dependencies in topological order and records, for
each changed node, the **minimal justification set**: the exact edge ids that
caused the change, which is a JTMS justification by another name. The report
renders those chains. Prose is generated afterwards, from the chain, and is
never the source of truth. `RETIRED` is reachable only by a human decision, so
no machine path can kill a hypothesis.

**(4) The model's generative output is validated against the graph.** The
replacement experiment is not a paragraph. Its structural slots (which
proposition is open, which hypotheses need discriminating, which assumptions are
still safe to rely on) are computed. The model writes the method. A deterministic
validator then rejects any proposal that depends on an invalidated assumption or
fails to target the open proposition. A generated experiment that does not
survive the validator is never shown.

Everything is an append-only event log; state is a fold over it; replay is
required to be byte-identical. Ingestion is keyed on a content hash so the same
evidence twice is a no-op.

## 5. Falsifiable novelty claim

> **N1.** For a research program represented as a typed graph, the set of
> artifacts affected by new evidence can be computed deterministically from the
> graph plus one bounded pairwise semantic judgment per (claim, assumption)
> pair, and that computed set matches expert ground truth on fixtures where
> ground truth is true by construction, with no false positives among unrelated
> artifacts.

Two ways to falsify it, both of which we should actively try:

- **F1, the mechanism is cosmetic.** If, on the same fixtures, an LLM handed the
  whole graph and the new paper produces the same affected set as the
  deterministic engine, then the engine buys nothing but latency and the honest
  move is to say so. **This has now been run. See section 5b: on affected-set F1
  it is a tie, so the naive form of this project's pitch is dead, and what
  survives is narrower and better evidenced.**
- **F2, the edges are not real.** If constructing the dependency edges for a real
  program requires so much interpretation that different experts produce
  different graphs, then the deterministic layer is precise about an arbitrary
  input, and precision on an arbitrary input is theatre.

## 5b. F1, run live on 2026-08-15. The result is not the one we wanted.

Fifteen controlled variants derived from one program, ground truth computed by
running the state rules on the relations each variant declares as true, three
runs each, `gemini-3.5-flash` through Vertex AI at temperature 0. **Baseline A**
gets the whole graph with current states, every edge id, the numbered document,
and the complete rule set, and is asked for the impact directly. **System B** is
asked one bounded question per assumption and the engine does the rest. Artifact:
`proof-out/f1.json`, rescored from the raw model answers by `make bench-judge`,
11/11 PASS, and rejected on each of three tampered copies.

| | A: whole-graph LLM | B: bounded judgment + engine |
| --- | --- | --- |
| affected-set precision | **0.888** | 0.829 |
| affected-set recall | 0.931 | **1.000** |
| **F1** | **0.909** | **0.907** |
| target state exact, of hits | 0.979 | 0.971 |
| unrelated artifacts preserved | 0.979 | 0.964 |
| run-to-run identical answers | 0.956 | **1.000** |
| justification contains the true cause | 1.000 | 1.000 |
| justification is exactly the minimal set | 0.817 | **1.000** * |
| impossible state transitions | 0 | 0 * |
| wrong semantic judgments | not exposed | 7 of 273 (97.4% correct) |
| input tokens / calls | 214,902 / 45 | 109,035 / 273 |

\* asymmetric by construction, and it would be dishonest to present these as
wins: System B does not author states or justifications, so it cannot emit an
impossible one or cite a wrong one. Those rows measure whether the baseline can
match what the engine gets for free.

**F1 is a tie. The claim "an LLM cannot do this" is refuted, on this benchmark,
and should never appear in a submission artifact.** What the run does show is
that the two systems fail differently, and the differences are the product
argument:

1. **The baseline invented relations twice and propagated them.** In V03 and V10
   it reported `A6 → SUPPORTED` and `E7 → REDUNDANT` from documents that never
   mention rollout coherence at all, in all three runs of each. It was not
   guessing wildly, it was pattern-matching: both documents are about position
   probing, and A6 is the nearby assumption.
2. **It missed a second relation living in one sentence, systematically.** In
   V15, one sentence bears on both A1 and A5; the baseline found A1 every time
   and A5 never, so it also missed the hypothesis downstream of A5. System B's
   per-assumption sweep asks about A5 explicitly and found it every time. That
   is a structural advantage of the bounded design, not a lucky prompt.
3. **It missed a multi-hop consequence.** In V12 it correctly found `A6 →
   SUPPORTED` and then failed, in one run of three, to notice that E7, the
   experiment that would have established A6, is now redundant.
4. **System B never missed a true impact and never changed its answer.** Recall
   1.000, run-to-run identity 1.000. The baseline changed its answer between
   runs on 4.4% of variant pairs at temperature 0.
5. **Every one of System B's errors is a single wrong judgment, faithfully
   amplified.** Seven wrong relations out of 273 became 21 wrong nodes, roughly
   3x. The amplification is real and is the honest cost of determinism. The
   number a reviewer acts on, though, is 7: each is one relation, on screen, with
   the quoted sentence, that a human confirms or rejects in one click. The
   baseline's mistakes do not localize to a decision at all.

**Where B's errors came from, exactly:** three runs of strength inflation on one
relation (V13: a suggestive single-seed result on a neighbouring benchmark called
MODERATE where the rubric says WEAK) and three runs of one over-association
(V14: reading "one-step accuracy correlates with solve rate at r=0.21" as
evidence against an assumption about decision-relevant cell changes). Two
mistakes, in two places, both at the semantic boundary, both fixable there
without touching propagation. That is the whole design thesis surviving contact:
**the errors were where the design says errors go.**

Limits, stated rather than buried: fifteen variants, one model, one temperature,
one program. Ground truth is this project's own policy applied to the correct
edge set, so the experiment asks whether unconstrained reasoning reproduces a
written rule set that both systems were handed, not whether the rule set is
right. Two variants of the benchmark were corrected mid-build after the model
was right and the declared truth was wrong, which is recorded here because a
benchmark author who never has to do that has not looked hard enough.

**Consequence for the thesis.** The claim narrows from "the graph is necessary"
to something measured: *unconstrained reasoning over a research program is
approximately as accurate, but not repeatable, not exhaustive, not auditable to
an exact cause, and not correctable in one place.* The next experiment is
already defined and cheap: recalibrate the strength rubric at the judge, rerun
the same fifteen variants, and see whether B's precision moves without touching
propagation. If it reaches ~0.95 at recall 1.0, B's F1 goes to roughly 0.97
against the baseline's 0.909, and the argument is quantitative rather than
qualitative.

## 5c. The holdout, run 2026-08-15. The fix failed and the baseline won.

The dev set above diagnosed a failure at the semantic boundary. Reporting an
improvement on those same fifteen variants would be tuning, so: the dev set was
frozen (`results/f1-dev-summary.json`, proof `279df725`), eighteen new variants
were authored over a **second program** in a different domain, their ground truth
was computed and hashed
(`80b07fc8cd242a0a74f46a617e6ae99067dfa1ee0240e2d9d89cf32e64a7995d`, in
`results/holdout-lock.json`), and only then was the boundary changed. No model
had been run against the holdout when that hash was written, and it was run
once, in four configurations, with no second pass.

**v2**, the change, is principled and was designed from the two dev failures
alone: stop asking the model for a strength label, ask two narrower factual
questions instead (`inference_distance`: DIRECT / ONE_STEP / MULTI_STEP, and
`same_setting`), and compute strength in code from a fixed table.

Eighteen variants, three runs, `gemini-3.5-flash`, 1,157s, 972 calls, zero
failures. `make bench-judge`, 20/20 PASS.

| | A:v1 | A:v2 | B:v1 | B:v2 |
| --- | --- | --- | --- | --- |
| precision | **1.000** | 0.980 | 0.884 | 0.818 |
| recall | 0.987 | 0.967 | **1.000** | **1.000** |
| **F1** | **0.993** | 0.974 | 0.939 | 0.900 |
| unrelated preserved | **1.000** | 0.997 | 0.978 | 0.963 |
| provenance exactly minimal | 0.899 | 0.905 | **0.959** | **0.959** |
| impossible states | 0 | 0 | **0** | **0** |
| run-to-run identical | 0.963 | 0.889 | 0.889 | 0.963 |
| corrections to restore truth | **5** | 8 | 17 | 25 |
| nodes repaired per correction | 1.0 | 1.0 | 1.53 | 1.60 |
| residual wrong nodes after correction | 0 | 0 | **0** | **0** |
| wrong semantic judgments | not exposed | not exposed | 17 of 432 | 25 of 432 |

Three findings, in order of how much they cost this project.

**1. The boundary fix made things worse, on unseen cases, in both systems.**
B went from 0.939 to 0.900 and its semantic errors from 17 to 25; A went from
0.993 to 0.974. The mechanism is clear in the raw answers and worth recording,
because it is a general lesson about this kind of fix: v1 let the model say
WEAK, and WEAK does not propagate. v2 removed that escape hatch and replaced it
with two questions the model answers *optimistically* — it likes DIRECT, it
likes same_setting, and that pair computes to STRONG. Decomposing a judgment is
only an improvement if the sub-questions are ones the model is conservative
about. These were not. **The dev-set diagnosis was right about where the errors
were and wrong about what would fix them, which is exactly what a holdout is
for.**

**2. The baseline beat the architecture clearly, and by more than on dev.**
0.993 against 0.939. Across two programs and 33 variants the accuracy argument
for the deterministic layer is now dead twice over, and no artifact from this
project may imply otherwise.

**3. The interesting finding: exhaustiveness cuts both ways, and the same
mechanism produced the dev win and the holdout loss.** Twenty of B's twenty-five
v2 semantic errors involve a single assumption, B7 ("context window length, not
attention degradation, is the binding constraint"). B's sweep asks about B7 for
every document, so every document about context or attention produces a
judgment, and several of those are marginal. The baseline never asks about B7 at
all, so it never gets B7 wrong. On the dev set this same property was the
architecture's clearest win: V15 hid a second relation inside one sentence and
the baseline missed it in every run while the sweep found it every time. The
property is the same one. **Asking about every assumption means never silently
skipping one, and it also means never declining to have an opinion.** That is a
real, measured trade, and it is the honest version of this project's
architectural claim.

**A caveat I am not allowed to resolve, and that is the point.** Some of B's
holdout errors are probably my ground-truth incompleteness rather than model
error: E-LOW says overflow is rare, and reading that as bearing on B7 is
defensible, but the locked truth does not declare it. On the dev set I found and
fixed exactly this kind of defect twice, before locking. Here the protocol
forbids it, so the number stands as measured and the suspicion is recorded
rather than acted on. The fix is a third set whose every (document, assumption)
pair is adjudicated for completeness before locking, not an edit to this one.

**What survives, measured on unseen cases:** recall 1.000 against 0.987, zero
impossible states, provenance exactly minimal 0.959 against 0.899, and a
verified repair property — rejecting the wrong relations restores the intended
state exactly, with zero residual wrong nodes, in every case. What does not
survive: any claim that this architecture is more accurate, and the specific fix
that was supposed to close the gap.

## 5d. F3, the longitudinal test. The pre-registered kill condition fired.

Every earlier measurement was single-document, the setting that most flatters a
model recomputing from scratch, because there is no accumulated state to get
wrong. This is the test kill condition 5 always needed: ten interacting
documents over one program, a human correction in the middle, three systems.

The baseline that matters is **A1**, not the stateless one. Denying a model
persistence and then declaring a persistent system the winner would prove
nothing, so A1 keeps a canonical structured research state, is handed all of it
back every step including every relation it has recorded and every correction
the researcher has made, and answers under a constrained schema.

Locked before any of it ran: ten documents, 80 document x assumption pairs
adjudicated exhaustively (8 RELATION, 70 NO_RELATION, 2 AMBIGUOUS), three orders
that converge, digest `409edd00...`. Thresholds for "substantial advantage" were
written into the session contract before the sequence existed.

Live: 15 trajectories, 500 model calls, 644s. `make seq-judge` 9/9 PASS.

| | A0 stateless | A1 persistent model state | B engine |
| --- | --- | --- | --- |
| end-state accuracy | 0.678 | **0.956** | **0.978** |
| mean step accuracy | 0.823 | 0.968 | 0.967 |
| steps exactly right | 2/50 | 24/50 | **33/50** |
| correction persistence | n/a | **1.000** | **1.000** |
| regressions | 37 | **5** | 6 |
| unnecessary changes | 40 | **2** | 6 |
| longest error survival | 10 | 5 | 9 |
| orders agreeing | 3/3 | 1/3 | 2/3 |
| auditable justifications | 0.589 | 0.655 | **1.000** |
| calls | 50 | 50 | 400 |

**Verdict: KILL, computed by `bench/killcondition.py` from the pre-registered
thresholds, not chosen after the fact.** Zero of four criteria met, and the hard
override fired: A1 reached end-state accuracy 0.956 and correction persistence
1.000, both above the 0.95 line that was set in advance as sufficient to end the
thesis.

**A metric defect found and corrected, disclosed because it changes how the
first number should be read.** As first run, correction persistence came out at
0.1429 for all three systems, identically. That was a bug in my implementation,
not a finding: it measured whether the corrected node's *state* stayed put,
while the pre-registered criterion says "the fraction of post-correction steps
where **the rejected relation** stays rejected". Every system's B7 state moved
at D5, the document adjudicated AMBIGUOUS for exactly that pair, so the metric
was penalising all three for a reading the adjudication says is defensible.
Corrected to measure what was registered, and to exclude ambiguous-pair shadow
from the headline as the registration also said, then recomputed from the same
recorded answers with no new calls. **The correction made the result more
favourable to every system and the verdict stronger, not weaker**: 0.1429
became 1.000 for both A1 and B, end accuracy rose for all three, and the hard
override then fired. Both artifacts are kept: `f3-sequence-asrun.json` as
produced, `f3-sequence.json` rescored.

**What actually happened, which is more useful than the table.**

- **Nobody resurrected the correction.** A1 never re-asserted the rejected D4
  relation in any run or any order. Every B7 movement came from D5, a different
  document, which is legitimate behaviour and which the adjudication had already
  marked debatable. The property this project expected to win on is a tie at
  1.000.
- **B's single semantic error survived nine steps.** It read D2, the
  deliberately weak single-seed finding from a different setting, as a
  propagating contradiction, and B3 stayed wrong for the rest of the sequence.
  Determinism preserved and amplified it exactly as faithfully as it preserves a
  correct judgment. This is the same strength-calibration failure the dev set
  diagnosed and the v2 boundary failed to fix.
- **A1's errors were the multi-hop derivations**: it missed that settling B4
  makes F6 redundant, missed F7 reactivating when B5 was contested, and twice
  marked a planned experiment COMPLETED, a transition the rules do not permit.
  B cannot make that last mistake by construction. Noted post hoc, and it was
  not among the pre-registered criteria, so it does not count.
- **B was order-sensitive (2 of 3) and A1 worse (1 of 3)**, but B's divergence
  is not the engine: propagation is a pure function of admitted relations. It is
  the judge answering the same pair differently on different days.

**The honest reading.** A persistent monolithic model, given a schema and its
own state back, maintains a research program about as well as an executable
graph does, keeps a human correction perfectly, and does it in one call per
document instead of eight. The thing this architecture uniquely provides is a
justification that always resolves to a real edge (1.000 against 0.655) and an
inability to emit a state the rules forbid. Those are real, and by the standard
set in advance they are not enough.

## 6. Kill conditions

Carried from the brief, sharpened by what phase 1 found.

1. **Co-Scientist already does this.** If access shows it maintains a durable,
   dependency-aware program state with downstream invalidation, stop. Nothing
   found says it does; this stays open until checked.
2. **F1 fails.** A plain LLM over the same graph matches the deterministic
   engine. **Partly triggered, 2026-08-15.** It matches on F1 (0.909 vs 0.907)
   and loses on recall, stability, and exact provenance. The "graph is
   necessary for accuracy" claim is dead; the "graph is necessary for repeatable,
   exhaustive, auditable, single-point-correctable impact" claim survives with
   numbers behind it. Section 5b. This is a MODIFY, not a kill, and the modified
   claim is the only one that may be used in any artifact.
3. **F2 fails.** Dependency edges cannot be elicited reliably from a real
   researcher's program.
4. **The demo needs invented claims.** If the only paper that produces a crisp
   contradiction is one we wrote, the product is a puppet show. The phase 3 gate
   is a real arXiv paper against a real program.
5. **Persistence buys nothing.** If a fresh run over the current corpus produces
   the same answer as maintained state, the state is overhead. **Triggered
   2026-08-15, by the pre-registered standard, section 5d.** A persistent
   monolithic model reached 0.956 end-state accuracy and kept a human correction
   perfectly, against 0.978 and 1.000 for the engine: a margin far below the
   0.05 registered as substantial, and above the hard-override line that was
   written down in advance as sufficient to end the thesis.

## 7. Architecture candidates

Chosen shape, and the mandatory hackathon stack is satisfied by things that
carry weight rather than by decoration:

- **Gemini 3.5+ via Vertex AI**: the pairwise claim-to-assumption judgment
  (structured output, one relation per call) and the replacement-experiment
  drafting. Two jobs, both bounded, both checked by code afterwards.
- **Google ADK**: the surveillance and impact agent. Genuine multi-turn state:
  triage a new paper, extract candidate claims, propose edges, ask the
  researcher clarifying questions where confidence is low, capture the
  confirm/override as a first-class event. That last part is exactly what the
  Collaborative Partner track asks for ("ask clarifying questions, guide the user
  step-by-step, and have a clear way to capture feedback"), and it is also the
  human-ownership rule, so the track fit is honest rather than retrofitted.
- **Firestore**: the append-only event ledger plus the materialised graph
  snapshot. Chosen over a graph database because a research program is hundreds
  of nodes, not millions: the traversal is in-process over a loaded snapshot,
  which is what makes it deterministic and unit-testable. Firestore stores
  events, not the algorithm.
- **Cloud Run**: the impact service and the ADK agent.
- **Optional, only if earned**: Pub/Sub or Cloud Scheduler for arriving
  literature; Gemma for cheap first-pass relevance triage (a real narrow role:
  most papers are irrelevant to any given program, and paying Gemini to say so is
  waste).

**Rejected: Memory Bank as the research state store.** It consolidates ingested
events into server-synthesized memories rather than storing what you gave it
one-to-one (verified live on 2026-08-13 against a real Agent Engine, during the
other project in this repo). Typed entities that must keep exact identity across
months cannot live in a store that merges them. Firestore is the right primitive.

**Rejected: a graph database.** See above. Revisit only if a program stops
fitting in memory, which it will not at demo scale.

**Rejected: agent-per-entity orchestration.** Five agents passing a graph around
is theatre. One surveillance/impact agent plus deterministic code is the design.

## 8. The smallest compelling demo

A real research program that we can defend on camera because it is ours: does
history-conditioned, coordinate-aware state improve one-step, decision-relevant
transition prediction (an ARC-style reasoning program). Two hypotheses, five
assumptions, seven experiments, some completed with results, some planned, with
prior failures visible.

A new paper arrives. The system triages it as relevant, extracts one claim,
links it to assumption A2 with a verbatim excerpt, and A2 moves to CONTESTED.
Then the graph, not the model, produces:

```
A2 SUPPORTED -> CONTESTED        because  C7 CONTRADICTS A2 (excerpt, source, confidence)
H1 ACTIVE    -> REQUIRES_REVIEW  because  H1 DEPENDS_ON A2
E4 PLANNED   -> STALE            because  E4 REQUIRES A2
E7 PLANNED   -> REDUNDANT        because  C7 decides the proposition E7 would establish
E5 PLANNED   -> unchanged        because  E5 requires A1, A4 only
E8 proposed                      targets  the open proposition, requires only A1, A4
```

Every arrow is clickable back to the paragraph. The unchanged rows are on
screen deliberately: a system that marks everything affected is useless, and
showing what did *not* move is how you prove the blast radius is real.

## 9. Biggest reason this fails

Not the engineering. The **edge acquisition problem**: a research program's
dependency edges live in a researcher's head, and asking someone to declare
"H1 depends on A2, E4 requires A2" is asking for work up front in exchange for
value later. Every system in cluster 2d (nanopublications, ORKG) has struggled
with exactly this adoption tax. The mitigation is that the agent proposes edges
from the researcher's own existing artifacts (proposals, lab notes, prior
papers) and the human confirms rather than authors, which turns the tax into a
review. Whether that is enough is unproven and is the real product risk.

## 10. Verdict

**Opened GO on 2026-08-15. Closed KILL the same day, on the evidence in 5b, 5c
and 5d.**

The sequence of findings, in the order they arrived, because the order is the
argument:

1. Phase 2 proved the mechanism works: deterministic propagation, minimal
   provenance, verified replay and repair, 22 gates.
2. F1 dev asked whether it beats a whole-context model. It ties (0.909 / 0.907).
3. F1 holdout, locked before the fix that was designed from the dev failures,
   said the fix made things worse and the baseline wins clearly (0.993 / 0.939).
4. F3 asked the only remaining question, whether persistence buys anything, with
   thresholds registered in advance. A persistent monolithic model matched the
   engine and kept a human correction perfectly. The hard override fired.

What is true at the end: Gemini 3.5 can maintain a research program's state
across ten interacting documents, keep a correction, and stay within a
constrained schema, well enough that an executable dependency graph is not
necessary for this product. What the graph still uniquely gives is a
justification that always resolves to a real edge and an inability to emit a
forbidden state. Those did not clear the bar set before the numbers existed, and
lowering the bar afterwards is the one move this project has refused at every
step.

**Recommendation: do not build the product.** The three days spent finding this
out are cheaper than two weeks building a SaaS around it and learning the same
thing after submission. The engine, the benchmarks, the locking protocol and the
judges stand as the artifact.
