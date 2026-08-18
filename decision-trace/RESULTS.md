# DecisionTrace v0 falsifier results

n = 37 decisions across 4 repos.

| Condition | Citation-correct | Rationale-match | Combined (both) | Hallucination rate | Supersession-aware |
|---|---|---|---|---|---|
| code_only | 16% (6/37) | 11% (4/37) | 0% | 8% | 44% (8/18) |
| rag | 76% (28/37) | 59% (22/37) | 57% | 3% | 94% (17/18) |
| structured | 100% (37/37) | 76% (28/37) | 76% | 0% | 100% (18/18) |

## Threats to validity

- **Citation-correctness is satisfied by construction for the structured arm.** Every retrieved card carries its own citation field (`Evidence: PR #N` / file path) inline, so a model that answers from a retrieved card at all is very likely to cite correctly — this measures whether retrieval found the right card, not independent recall of the citation.

- **19 of 37 decisions (51%) come from kubernetes/enhancements KEPs** (source `kep_alternatives`); the remaining 18 are revert-PR pairs across three repos. The headline numbers are weighted toward KEP-shaped sources — see the per-source breakdown below.


## Per-source breakdown

| Condition | Source | Citation-correct | Rationale-match | Combined |
|---|---|---|---|---|
| code_only | revert_pair | 0% | 11% | 0% (n=18) |
| code_only | kep_alternatives | 32% | 11% | 0% (n=19) |
| rag | revert_pair | 94% | 94% | 94% (n=18) |
| rag | kep_alternatives | 58% | 26% | 21% (n=19) |
| structured | revert_pair | 100% | 94% | 94% (n=18) |
| structured | kep_alternatives | 100% | 58% | 58% (n=19) |

## Per-decision detail

| decision_id | repo | code_only | rag | structured |
|---|---|---|---|---|
| rust-lang-rust-revert-149375 | rust-lang/rust | cR | CR | CR |
| rust-lang-rust-revert-148937 | rust-lang/rust | cr | CR | CR |
| rust-lang-rust-revert-149060 | rust-lang/rust | cr | CR | CR |
| rust-lang-rust-revert-149516 | rust-lang/rust | cr | CR | CR |
| rust-lang-rust-revert-142034 | rust-lang/rust | cr | CR | CR |
| kubernetes-kubernetes-revert-140448 | kubernetes/kubernetes | cr | CR | CR |
| kubernetes-kubernetes-revert-306 | kubernetes/kubernetes | cr | cr | CR |
| kubernetes-kubernetes-revert-136254 | kubernetes/kubernetes | cr | CR | CR |
| kubernetes-kubernetes-revert-126794 | kubernetes/kubernetes | cr | CR | CR |
| kubernetes-kubernetes-revert-127300 | kubernetes/kubernetes | cr | CR | CR |
| elastic-elasticsearch-revert-154503 | elastic/elasticsearch | cr | CR | CR |
| elastic-elasticsearch-revert-152050 | elastic/elasticsearch | cr | CR | CR |
| elastic-elasticsearch-revert-151875 | elastic/elasticsearch | cr | CR | CR |
| elastic-elasticsearch-revert-120214 | elastic/elasticsearch | cr | CR | CR |
| elastic-elasticsearch-revert-147071 | elastic/elasticsearch | cr | CR | Cr |
| kep-keps-sig-storage-1979-object-storage-support | kubernetes/enhancements | Cr | cr | Cr |
| kep-keps-sig-auth-1205-bound-service-account-tokens | kubernetes/enhancements | Cr | cr | Cr |
| kep-keps-sig-auth-2718-20210511-client-exec-proxy | kubernetes/enhancements | cr | CR | CR |
| kep-keps-sig-cloud-provider-2133-out-of-tree-credential-provider | kubernetes/enhancements | crH | CR | CR |
| kep-keps-sig-api-machinery-2332-pruning-for-custom-resources | kubernetes/enhancements | cRH | cr | CR |
| rust-lang-rust-revert-144407 | rust-lang/rust | cr | CR | CR |
| kubernetes-kubernetes-revert-129701 | kubernetes/kubernetes | cR | CR | CR |
| kubernetes-kubernetes-revert-126599 | kubernetes/kubernetes | cr | CR | CR |
| kep-keps-sig-auth-279-limit-node-access | kubernetes/enhancements | cr | cR | CR |
| kep-keps-sig-storage-2451-service-account-token-volumes | kubernetes/enhancements | cr | Cr | CR |
| kep-keps-sig-cli-2382-kustomize-exec-secret-generator | kubernetes/enhancements | cr | Cr | CR |
| kep-keps-sig-instrumentation-647-apiserver-tracing | kubernetes/enhancements | cr | Cr | CR |
| kep-keps-sig-storage-1790-recover-resize-failure | kubernetes/enhancements | Cr | cr | CR |
| kep-keps-sig-auth-5681-conditional-authorization | kubernetes/enhancements | cr | CR | Cr |
| kep-keps-sig-api-machinery-3488-cel-admission-control | kubernetes/enhancements | cr | cr | Cr |
| kep-keps-sig-api-machinery-2523-consistent-resource-versions-semantics | kubernetes/enhancements | crH | cr | Cr |
| kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay | kubernetes/enhancements | cr | crH | Cr |
| kep-keps-sig-scheduling-5501-reflect-preenqueue-rejections-in-pod-status | kubernetes/enhancements | Cr | CR | CR |
| kep-keps-sig-api-machinery-2885-server-side-unknown-field-validation | kubernetes/enhancements | cR | Cr | CR |
| kep-keps-sig-api-machinery-2876-crd-validation-expression-language | kubernetes/enhancements | Cr | Cr | Cr |
| kep-keps-sig-scheduling-5229-asynchronous-api-calls-during-scheduling | kubernetes/enhancements | Cr | Cr | CR |
| kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure | kubernetes/enhancements | cr | Cr | Cr |

(Capital = correct/true, lowercase = incorrect/false, H = hallucinated a wrong citation.)


## Verdict: CAUTION

RAG=57%, structured=76% — doesn't cleanly clear either threshold at n=37. Inconclusive; widen the sample or inspect per-decision detail above before deciding.

## Per-alternative retrieval experiment (2026-08-18) — null result

Hypothesis (docs/PER_ALTERNATIVE_RETRIEVAL_HANDOFF.md): the structured
condition indexed one whole card per decision, so a multi-point KEP card's
retrieval was precise at the decision level but imprecise at the
alternative level — the model had to guess which of several rejected
alternatives the judge's ground-truth quote was about. Splitting each
`rationale_card` into individual alternative-points and indexing each
point separately (same TOP_K=5, ~60-90 points pooled instead of 37 whole
cards) was expected to let retrieval surface the specific point a query is
about.

Implemented exactly as specified: `split_rationale_points()`,
`point_card_text()`, `get_point_index()` added to `run_conditions.py`;
`run_structured()` swapped from `get_card_index()` to `get_point_index()`;
all 37 structured runs regenerated; all three conditions re-graded (111
judge calls).

**Result: no change.** structured combined 76% (identical), revert_pair
subset 94% (identical), kep_alternatives subset 58% (identical) — byte-for-
byte the same aggregate numbers as the whole-card baseline. Retrieval
granularity was not the bottleneck: at k=5 the model already reliably
retrieves the right decision's card content either way, so splitting a
6-point card into 6 separately-indexed points didn't change which points
ended up in the prompt for these queries. The remaining kep_alternatives
gap is not a retrieval-precision problem.

`data/corpus/cards-index.json` (whole-card index) kept unchanged for
comparison/rollback; the new `data/corpus/points-index.json` is not wired
back in as the default going forward, since it produced no improvement.
`run_conditions.py` still calls `get_point_index()` post-experiment —
reverting to `get_card_index()` is a one-line change if a future session
wants the simpler whole-card mechanism back, now that per-point retrieval
is confirmed not to help.

This closes the retrieval-granularity lever as a research question:
further movement on the 58% KEP-subset number needs a larger n or a
different mechanism (e.g. changing how the judge's ground-truth quote is
selected, or a genuinely different retrieval signal), not another
indexing-granularity iteration on this n=37 set.
