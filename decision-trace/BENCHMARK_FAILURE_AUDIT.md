# Benchmark failure audit — the v0 falsifier's 9 structured failures

Branch `research/decisiontrace-plateau`, cut from `1c33d3d`. Diagnostic
only. No v0 artifact is modified by this document.

Baseline under audit (`RESULTS.md`, unchanged): structured combined 76%
(28/37), rag 57%, code_only 0%; structured `revert_pair` 94% (17/18),
structured `kep_alternatives` 58% (11/19); verdict CAUTION.

Every claim below is checked against the **live source document**, fetched
fresh from GitHub for all 37 decisions, not inferred from the card or the
quote. The nine structured prompts were reconstructed byte-exactly from
the cached point index and verified by matching the recovered retrieval
order against the `retrieved` list recorded in each run file (9 of 9
exact). So "reached the final prompt" below is measured, not assumed.

## Method

1. Fetched each decision's cited source (37/37 successful).
2. Located every `rationale_quote` in its source with a whitespace-flexible
   match (37/37 located, 1 occurrence each — no ambiguity).
3. Parsed each KEP with a **fence-aware** markdown sectioner, so `#`
   comments inside code blocks are not mistaken for headings. This
   matters: a naive parser reports a 15K-character over-capture for
   KEP-3488 that does not exist.
4. Identified each KEP's canonical `Alternatives` section (shallowest
   heading titled `Alternatives`/`Alternatives Considered`) and its named
   alternatives (child headings, or top-level bullets where the section
   uses no sub-headings).
5. Reconstructed each failing structured prompt and diffed the card points
   that reached it against the decision's full card.
6. Ran one judge-variance probe over the 9 failures (authorised as a
   diagnostic; it does **not** replace the recorded v0 score).

## Two upstream defects found in the mining pipeline

Both are mechanical, verifiable, and explain most of the failures.

### Defect 1 — `ALTERNATIVES_SECTION_RE` is unanchored

```python
ALTERNATIVES_SECTION_RE = re.compile(
    r"##\s*Alternatives(?: Considered)?\s*\n(.*?)(?:\n##\s|\Z)", ...)
```

`##\s*Alternatives` has no line-start anchor, so it matches the **trailing
two hashes** of a deeper heading. And its terminator `\n##\s` only stops at
level-2 headings, so when the match starts at level 3/4/5 the captured span
runs past the real section until the next level-2 heading.

Measured over the 19 KEPs (fence-aware ground truth):

| decision | heading level matched | captured | true section | over-capture |
|---|---|---|---|---|
| `kep-…-auth-1205-bound-service-account-tokens` | **5** (`##### Alternatives Considered`) | 7981 | 1067 | **+6914** |
| `kep-…-storage-2451-service-account-token-volumes` | **4** | 1785 | 705 | +1080 |
| `kep-…-cloud-provider-2133-out-of-tree-credential-provider` | **3** | 2991 | 2691 | +300 |
| the other 16 | 2 | — | — | 0 |

For `auth-1205` the consequence is decisive: the real `##### Alternatives
Considered` is a 1067-character list nested inside `#### File Permission`,
but the extractor swallowed 6914 further characters covering
`### ServiceAccount Admission Controller Migration`, `#### Prerequisites`,
`#### Safe Rollout of Time-bound Token`, `### Test Plan` and
`### Graduation Criteria`. `pick_quote()` then selected its ground truth
from that over-captured region.

### Defect 2 — the "stricter `pick_quote`" fix silently applied to 10 of 19 rows

`reextract_kep_quotes.py` re-extracts with `require_rejection=True`, but:

```python
picked = pick_quote(alt_section, require_rejection=True)
if picked is None:
    no_pick.append(d["decision_id"])
    continue          # <- row keeps its OLD, loose-regex quote
```

When no rejection-cue sentence exists, the row **keeps the quote selected
by the looser `RATIONALE_CUES`** — the regex the project's own code comment
describes as firing "just as often on prose explaining why the CHOSEN
design works as on prose rejecting an alternative".

Measured: **9 of 19 KEP ground truths carry no rejection cue at all**, all
9 carry a loose cue, and re-running the extractor on their sections returns
`None` for exactly those 9. So they are confirmed `no_pick` rows. The
round-3 fix covered 10 of 19 rows, not 19, and `RESULTS.md` and
`docs/PER_ALTERNATIVE_RETRIEVAL_HANDOFF.md` both describe it as uniform.

`kep-…-2876-crd-validation-expression-language` is the clearest casualty:
its ground truth is *"We are implementing CRD validation with CEL first
because is is a more constrained problem…"* — selected on the cue
`because`, and it is reasoning **for** the chosen design. It is precisely
the failure mode the project believed it had already fixed.

## Failure classification — all 9 structured failures

Class A is split, because the distinction decides whether the benchmark or
the miner is at fault:

- **A1 INVALID** — the quote is not a rejected-alternative rationale at
  all (chosen-design reasoning, a caveat, a meta-narrative, or a truncated
  fragment).
- **A2 MISALIGNED** — the quote *is* a genuine rejection rationale for a
  genuine alternative, but it is one arbitrary target among several the
  broad query equally invites, and the answer supplied a different valid
  one.

### 1. `elastic-elasticsearch-revert-147071` — **A2** (contributing: E)

| field | value |
|---|---|
| source type | `revert_pair` |
| query | "…planning to reintroduce… has something like this been tried and undone before, and if so why?" |
| ground-truth quote | "The two `multi_value=no on multi-field {sub,parent} rejects parent array` scenarios both failed, and the subsequent cluster instability caused a cascade of `Connection refused` failures on other unrelated tests in the same task." |
| quote's subsection | revert PR #147360 body, 3rd sentence |
| actual rejected alternative | the reverted PR #147071 itself |
| alternatives in source | 1 |
| represented in card | 1 |
| target meaning in card | **no** — card states the *cause*, quote states the *symptom* |
| retrieved | 1 own point + 4 foreign elasticsearch reverts |
| target meaning reached prompt | no |
| final answer states it | states the true cause, not the quoted symptom |
| judge | false (re-judge: still false) |

The PR body's causal sentence is *"the `cluster_features:` gate wasn't
skipping the tests on mixed clusters where older nodes lack the feature"*.
The card says *"faulty feature gating caused new tests to fail on
mixed-version clusters"* and the answer repeats it. Both are correct.
`pick_quote()` selected the **following** sentence, which lists which
scenarios failed and the `Connection refused` cascade — a downstream
symptom. A correct answer can therefore miss the target. The judge's
"false" is defensible on the text it was given; the target selection is
what is wrong.

### 2. `kep-…-storage-1979-object-storage-support` — **A2** (contributing: C)

| field | value |
|---|---|
| ground-truth quote | "Both forms are not supported in order to keep development and usage consistent." |
| quote's subsection | `Alternatives Considered > Encode BucketAccess connection information in a JSON blob` |
| actual rejected alternative | JSON-blob-encoded BucketAccess connection info |
| alternatives in source | **9** |
| represented in card | **6** (`CARD_PROMPT_MULTI` caps at "up to 6") |
| target meaning in card | yes — "JSON-encoded access secrets: Rejected because consumers needed individual secret keys…" |
| retrieved | 5 own points of 6 |
| target meaning reached prompt | **no** — the JSON-blob point is the one of six that fell outside top-5 |
| final answer states it | no; states the other 5, each correctly |
| judge | false (re-judge: still false) |

Two independent problems stack. The section's *stated* reason for dropping
the JSON blob is driver-implementer feedback; the quote is the trailing
consistency remark after it. And the card point that does carry the right
reason was evicted by the `TOP_K=5` budget — this is the exact
"correct decision retrieved, correct citation, several correct alternatives
answered, target omitted only because another point of the same decision
fell outside top-5" case hypothesised in H4.

### 3. `kep-…-auth-1205-bound-service-account-tokens` — **A1** (contributing: C)

| field | value |
|---|---|
| ground-truth quote | "After time-bound service account token being used, if in-cluster clients do not periodically reload token from projected volume, requests would be **rejected** once the initial token got expired." |
| quote's subsection | `Design Details > ServiceAccount Admission Controller Migration > Safe Rollout of Time-bound Token` |
| actual rejected alternative | **none** — this is a rollout caveat of the chosen design |
| alternatives in source | 3 (bullets in the real `##### Alternatives Considered`) |
| represented in card | 3 of 3 |
| target meaning in card | n/a — the target is not an alternative |
| retrieved | 1 own point + **4** points from `kep-…-storage-2451` |
| target meaning reached prompt | n/a |
| final answer states it | no |
| judge | false (re-judge: still false) |

Invalid by construction, via Defect 1 plus a homograph: the cue that
selected this sentence is `rejected`, meaning **HTTP requests being
rejected**, not an alternative being rejected. The quote lies outside any
Alternatives section in the document.

### 4. `kep-…-auth-5681-conditional-authorization` — **A2**

| field | value |
|---|---|
| ground-truth quote | "- Only one conditional authorizer could effectively be supported, instead of many in this framework." |
| quote's subsection | `Alternatives Considered > Do nothing, force implementers to implement all of this out of tree` |
| actual rejected alternative | do nothing / force out-of-tree implementation |
| alternatives in source | 6 |
| represented in card | 6 |
| target meaning in card | partially — the card gives that alternative a *different* one of its stated disadvantages |
| retrieved | 5 own points of 6 (target's point present) |
| target meaning reached prompt | the alternative yes, this specific disadvantage no |
| final answer states it | names the right alternative, gives the card's reason |
| judge | false (re-judge: still false) |

H1 in pure form. The quote is one disadvantage bullet among several for
one alternative among six; the query asks about all six.

### 5. `kep-…-api-machinery-3488-cel-admission-control` — **B CARD_COVERAGE_MISS**

| field | value |
|---|---|
| ground-truth quote | "- If the `spec.match` schema is incorrectly defined, CRD author might not realize it since they need to check the status of the corresponding `ValidatingAdmissionPolicy` for any errors." |
| quote's subsection | `Alternatives > Policy definition and configuration separation alternatives > Alternative: Duck Typed CRDs` |
| actual rejected alternative | Duck Typed CRDs |
| alternatives in source | 4 top-level groups (19 740 chars), each with its own sub-alternatives |
| represented in card | 4 points — **all four from the first group only** (`Type checking alternatives`) |
| target meaning in card | **no** |
| retrieved | 4 own points of 4 + 1 foreign |
| target meaning reached prompt | **no** |
| final answer states it | no; states all 4 type-checking alternatives correctly |
| judge | false (re-judge: still false) |

The genuine representation failure. Three of four alternative groups
(`Policy definition and configuration separation`, `CEL variables`,
`Message formatting`) never entered the card, so no retrieval or prompting
change could have recovered them. No over-capture here — the fence-aware
check confirms the 19 740-character span is genuinely all one
`## Alternatives` section.

### 6. `kep-…-api-machinery-2523-consistent-resource-versions-semantics` — **B** (contributing: E, A2)

| field | value |
|---|---|
| ground-truth quote | "**Disadvantages** - Since the field will deprecated but never removed, in practice we have 3 options to understand instead of 2." |
| quote's subsection | `Alternatives Considered > Alternative: Introduce ExactResourceVersion and MinResourceVersion parameters` |
| actual rejected alternative | `ExactResourceVersion`/`MinResourceVersion` parameters |
| alternatives in source | 2 |
| represented in card | 2 of 2 |
| target meaning in card | **no** — the alternative has two Disadvantages bullets; the card kept the second, the quote is the first |
| retrieved | 2 own points of 2 + 3 foreign |
| target meaning reached prompt | the alternative yes, this disadvantage no |
| final answer states it | "increases API complexity" — a generic form of the target |
| judge | false — **flipped to true on the variance probe** |

The only genuinely borderline row. Reason-level card lossiness inside a
correctly-identified alternative.

### 7. `kep-…-node-5593-configure-the-max-crashloopbackoff-delay` — **A1**

| field | value |
|---|---|
| ground-truth quote | "On further discussion, this was determined to be both too risky and a non-goal for Kubernetes architecturally, and moved into the Alternatives section." |
| quote's subsection | `Alternatives > Flat-rate restarts for Succeeded Pods > On Success and the 10 minute recovery threshold` |
| actual rejected alternative | unresolvable from the sentence — "this" refers to a prior draft of the proposal |
| alternatives in source | 7 |
| represented in card | 4 |
| target meaning in card | no |
| retrieved | 4 own points of 4 + 1 foreign |
| target meaning reached prompt | no |
| final answer states it | no; states 4 alternatives, 2 with correct rejection reasons |
| judge | false (re-judge: still false) |

Meta-narrative about the KEP's own editing history ("the original version
of this proposal included… and moved into the Alternatives section"), not a
rationale attributable to a named alternative. The document's actual
"**Why not?**" for flat-rate restarts is the preceding paragraph — which
the card and the answer both capture correctly.

### 8. `kep-…-api-machinery-2876-crd-validation-expression-language` — **A1**

| field | value |
|---|---|
| ground-truth quote | "We are implementing CRD validation with CEL first because is is a more constrained problem and is complementary to CEL for general admission…" |
| quote's subsection | `Alternatives > Introduce CEL for General Admission Control` |
| actual rejected alternative | **none** — the document says this option "is valuable and should be implemented"; only the *ordering* is being justified |
| alternatives in source | 7 |
| represented in card | 5 |
| target meaning in card | no — correctly so |
| retrieved | 5 own points of 5 |
| target meaning reached prompt | no |
| final answer states it | no; states Rego, Starlark, WebAssembly, custom language and webhooks, each with the source's real reason |
| judge | false (re-judge: still false) |

A stale loose-cue row (Defect 2), selected on `because`. The card is
*more* faithful to the document than the ground truth is: it lists the
alternatives that were actually rejected and omits the one that was not.

### 9. `kep-…-node-6122-configurable-scaling-delay-with-pod-resource-exposure` — **A1** (contributing: C)

| field | value |
|---|---|
| ground-truth quote | "* **Why Rejected**: This approach was discussed as a potential implementation detail for determining which CPUs to remove." |
| quote's subsection | `Alternatives > 1. LIFO (Last-In, First-Out) CPU Release` |
| actual rejected alternative | LIFO CPU release |
| alternatives in source | 8 |
| represented in card | 6 (cap) |
| target meaning in card | the alternative yes, this sentence no |
| retrieved | 5 own points of 6 — **the LIFO point is the one evicted** |
| target meaning reached prompt | no |
| final answer states it | no; states the other 5 correctly |
| judge | false (re-judge: still false) |

Malformed target. The quote is the **first sentence** of the `Why
Rejected` bullet, which is a framing clause. The actual reason is the
sentences immediately after it: *"However, KEP-5554 established the
principle of preserving the Original CPUSet… LIFO would add tracking
complexity without providing additional guarantees. This was rejected
during SIG Node meetings as an unnecessary complication."* The card says
exactly that. `sentences()` split at the first period and stopped.

## Totals

```
9 failures:
  7  benchmark-label / task mismatch  (A)
       4  A1 INVALID   — quote is not a rejected-alternative rationale
       3  A2 MISALIGNED — valid rationale, but one arbitrary target of several
  2  card coverage      (B)
  0  retrieval coverage (C)  — primary; 3 as a contributing cause
  0  generation         (D)  — primary; 1 as a minor contributing cause
  0  judge ambiguity    (E)  — primary; 2 as a contributing cause
  0  genuine unknown    (F)
```

**Generation is not a bottleneck anywhere.** In all 9 failures the model
rendered every card point it was given, with the source's reasoning intact:
prompt slots from the target decision vs alternatives named in the answer
were 1/1, 5/5, 1/1, 5/5, 4/4, 2/2, 4/4, 5/5, 5/5. Across the 8 KEP
failures the system named a mean of **4.4 real rejected alternatives with
correct reasons per answer** and scored zero for every one of them.

**Judge noise is real but small.** 1 of 9 flipped on the variance probe
(`2523`, the row this audit independently classifies as borderline). At
that rate judge ambiguity accounts for roughly one case, not four.

**H3 is confirmed and quantified.** The card holds fewer points than the
source names alternatives on **4 of 19** KEPs by the forensic count
(9→6, 8→6, 7→5, 7→4) and **6 of 19** by the stricter leaf-based count that
`audit_v0_failures.py` reports (see the note under the 19-KEP table). The
"up to 6" ceiling in `CARD_PROMPT_MULTI` binds literally on two of them,
`storage-1979` (9 alternatives) and `node-6122` (8); on the rest the model
simply stopped early. Either way 3 of the 4, and 4 of the 6, are failures.

**H4 is confirmed.** Three failures lost the target alternative's card
point to the `TOP_K=5` budget *within the correct decision* — `1979` (6
points, target evicted), `6122` (6 points, target evicted), `auth-1205`
(4 of 5 slots taken by a different KEP). This is not the closed
retrieval-granularity lever; splitting cards into points was already done
and is what makes this visible. It is a budget-vs-cardinality problem
created by asking one question about N alternatives.

## The diagnostic number, stated carefully

Two of the nine failures (`3488`, `2523`) are genuine system-side
representation failures. The other seven trace to ground truth that is
invalid or arbitrarily selected.

> If every A-class target were well-formed and uniquely determined, and the
> system performed on those rows as well as it demonstrably performs on the
> alternatives it already surfaces, structured would score **35/37 = 95%**.

That figure is an **upper bound and a diagnostic, not a prediction and not
a benchmark result**. It assumes away the A2 rows' real difficulty: under a
well-posed target the system must answer about *that* alternative, and
`1979` shows a case where the right card point exists but never reaches the
prompt. The honest way to find out is to re-pose the task and re-measure,
not to subtract rows. That is what `BENCHMARK_V2_SPEC.md` does.

## Full 19-KEP table

`v0` = structured result. `nAlt` = named alternatives in the canonical
Alternatives section. `card` = points in `rationale_card`. `stale` = ground
truth still selected by the loose `RATIONALE_CUES` (Defect 2).

| decision_id | v0 | nAlt | card | stale | quote's alternative |
|---|---|---|---|---|---|
| `…storage-1979-object-storage-support` | FAIL | 9 | 6 | – | Encode BucketAccess conn. info in a JSON blob |
| `…auth-1205-bound-service-account-tokens` | FAIL | 3 | 3 | – | **outside canonical section** |
| `…auth-2718-client-exec-proxy` | ok | 1 | 1 | – | Alternative Proposal: Request Replacement |
| `…cloud-provider-2133-out-of-tree-credential-provider` | ok | 4 | 4 | – | API Server Proxy |
| `…api-machinery-2332-pruning-for-custom-resources` | ok | 5 | 5 | – | (GDoc bullet — degenerate name) |
| `…auth-279-limit-node-access` | ok | 4 | 4 | **YES** | Allow kubelets to add any labels they wish |
| `…storage-2451-service-account-token-volumes` | ok | 0 | 5 | **YES** | outside canonical section (nested dup.) |
| `…cli-2382-kustomize-exec-secret-generator` | ok | 1 | 2 | **YES** | Git Style Plugins |
| `…instrumentation-647-apiserver-tracing` | ok | 2 | 3 | **YES** | (section prose, no named alt) |
| `…storage-1790-recover-resize-failure` | ok | 3 | 2 | **YES** | Why not use pvc.Status.Capacity…? |
| `…auth-5681-conditional-authorization` | FAIL | 6 | 6 | **YES** | Do nothing / force out-of-tree |
| `…api-machinery-3488-cel-admission-control` | FAIL | 4 | 4 | **YES** | Policy definition separation → Duck Typed CRDs |
| `…api-machinery-2523-consistent-resource-versions` | FAIL | 2 | 2 | – | Introduce Exact/MinResourceVersion params |
| `…node-5593-configure-max-crashloopbackoff-delay` | FAIL | 7 | 4 | – | Flat-rate restarts for `Succeeded` Pods |
| `…scheduling-5501-reflect-preenqueue-rejections` | ok | 2 | 4 | – | Detailed comparison for five design alternatives |
| `…api-machinery-2885-server-side-unknown-field-validation` | ok | 2 | 4 | **YES** | (section prose, no named alt) |
| `…api-machinery-2876-crd-validation-expression-language` | FAIL | 7 | 5 | **YES** | Introduce CEL for General Admission Control |
| `…scheduling-5229-async-api-calls-during-scheduling` | ok | 1 | 3 | – | (section prose, no named alt) |
| `…node-6122-configurable-scaling-delay` | FAIL | 8 | 6 | – | 1. LIFO CPU Release |

71 named alternatives across the 19 KEPs. 9 of 19 ground truths are stale
loose-cue picks; 5 of 19 quotes sit in section prose or outside the
canonical section rather than inside a named alternative.

**Which extractor the `nAlt` column uses.** The counts above come from the
forensic extractor: immediate child headings, or top-level bullets where a
section uses no headings. `audit_v0_failures.py` recomputes the same column
with the final v2 rule (leaf-most headings, name-shape filtered) and gets
different numbers for three shapes of document — where a KEP groups its
options (`3488`: 6 leaves beneath 4 group headings), writes them as prose
bullets (`auth-1205`, `2332`: 0 headings), or uses a design-FAQ layout
(`5501`: 0). Both counts are reported rather than reconciled into one,
because the disagreement between them *is* the finding: how many
alternatives a KEP "has" depends on the extractor, which is exactly why v0's
single regex produced targets it could not justify. The script is the
reproducible source; this table is the reading that drove the diagnosis.

Note the passes are not clean either: `auth-279`, `cli-2382`,
`instrumentation-647`, `storage-1790`, `2885` and `storage-2451` all pass
**with stale loose-cue ground truth**. The v0 KEP number is not
"58% correct" so much as "58% agreement with a target selected by a regex
that is wrong about half the time in both directions".

## Verdict on the v0 KEP benchmark

Not valid as written, for the `kep_alternatives` half. See
`BENCHMARK_V2_SPEC.md` for what replaces it and why. The `revert_pair`
half is sound in structure — one decision, one supersession, one stated
reason — with one row (`147071`) whose target sentence is a symptom rather
than the cause.
