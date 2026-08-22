# DecisionTrace falsifier v2 results

n = 83 cases across 33 decisions and 4 repos. Evidence tiers: {'v0_carryover': 18, 'body': 46, 'labelled': 19}.

v2 asks one targeted question per named alternative instead of one broad question per KEP. It is **not** the same benchmark as v0 and its numbers are not directly comparable — see `BENCHMARK_V2_SPEC.md` and the methodology section below.

| Condition | Citation-correct | Rationale-match | Combined (both) | 95% CI | Hallucination | Per-decision mean |
|---|---|---|---|---|---|---|
| code_only | 17% (14/83) | 45% (37/83) | **10%** (8/83) | 5%–18% | 2% | 5% (k=33) |
| rag | 59% (49/83) | 89% (74/83) | **55%** (46/83) | 45%–66% | 7% | 73% (k=33) |
| structured | 100% (83/83) | 99% (82/83) | **99%** (82/83) | 93%–100% | 0% | 97% (k=33) |
| structured_ingested | 92% (76/83) | 87% (72/83) | **87%** (72/83) | 78%–92% | 0% | 92% (k=33) |
| rag_labelled | 94% (78/83) | 89% (74/83) | **89%** (74/83) | 81%–94% | 0% | 90% (k=33) |

## Per-source breakdown

| Condition | Source | Citation | Rationale | Combined |
|---|---|---|---|---|
| code_only | revert_pair | 0% | 28% | 0% (n=18) |
| code_only | kep_alternative | 22% | 49% | 12% (n=65) |
| rag | revert_pair | 94% | 94% | 94% (n=18) |
| rag | kep_alternative | 49% | 88% | 45% (n=65) |
| structured | revert_pair | 100% | 94% | 94% (n=18) |
| structured | kep_alternative | 100% | 100% | 100% (n=65) |
| structured_ingested | revert_pair | 100% | 94% | 94% (n=18) |
| structured_ingested | kep_alternative | 89% | 85% | 85% (n=65) |
| rag_labelled | revert_pair | 89% | 89% | 89% (n=18) |
| rag_labelled | kep_alternative | 95% | 89% | 89% (n=65) |

## What changed from v0, and why

| | v0 | v2 |
|---|---|---|
| KEP unit | one KEP | one **named alternative** |
| KEP question | "what alternatives were considered here, and why weren't they used?" | "was *X* considered, and if so why wasn't it adopted?" |
| KEP target | one sentence picked by a cue regex | the alternative's own contiguous disposition span |
| Section boundary | next `##`, from an unanchored match | next heading of the same or shallower level, fence-aware |
| Structured record | one free-form card, "up to 6" points | one first-class object per alternative, uncapped |
| `revert_pair` arm | 18 cases | **identical** 18 cases, same query, same target, judged by v0's `judge_one` |
| Retrieval | `TOP_K=5` over 91 points | `TOP_K=5` over the alternative-card pool |
| Thresholds | structured >= 85%, RAG <= 70% | **unchanged**, imported from `grade.py` |

v2 is a different task from v0. It is not a corrected score for the same
question, and the two headline numbers should not be differenced. What is
comparable is the mechanism: v0 asked a set question and graded one
element, v2 asks about the element it grades.

## The three confounds, and what actually survives them

Read this before quoting any number in the table. Two of the three inflate
the structured arm and one deflates the RAG arm, and once all three are
removed the headline claim does not survive.

**Confound 3 — RAG was never told which document it had retrieved.**
`run_rag` indexed the answer-bearing document as `{"id": "TARGET"}` while
every decoy kept its real identifier (`keps/sig-.../README.md`,
`elastic/elasticsearch#111968`). The prompt renders each chunk as
`[<doc_id>]`, so the one document that could answer the question was the
one document whose identity was hidden, and every distractor announced
its own. The structured card, meanwhile, has always rendered
`Evidence: <path>` inline. The two arms were not being asked the same
thing.

Measured: on the KEP arm RAG retrieved the target in **65/65** cases and
stated a correct reason in **88%** of them, but cited correctly in **49%**.
Relabelling the target with its real identity — nothing else changed, same
chunks, same vectors, same questions — moves RAG's KEP citation from 49%
to **95%** and its combined score from 55% to **89%**.

**What survives.** With the structured store built without ever seeing the
question list (`structured_ingested`) and RAG told what it retrieved
(`rag_labelled`), the comparison is **RAG 89% (74/83) versus structured
87% (72/83)**. The difference is two cases, far inside both Wilson
intervals. On rationale alone the two are 89% and 87%. The verdict under
the unchanged thresholds is CAUTION, one point below the KILL line.

**So the structured-versus-RAG advantage this benchmark was built to
demonstrate is not demonstrated.** v0's apparent gap (76% vs 57%) was two
artifacts pointing in opposite directions: structured was held down by
ground truth it could not have matched, and RAG was held down by a
labelling bug on the only document that mattered. Correct both and the two
arms are tied.

One asymmetry now runs the *other* way and is worth stating: RAG sees the
verbatim graded span whenever it retrieves the right chunk, while the
structured arm only ever sees a paraphrase and never the graded text. That
structured reaches parity from a distillation is a real qualitative point
in its favour. It is not what the preregistered threshold asks, and the
threshold governs.

## The two confounds that make 99% indefensible

Read this before quoting the headline number. The structured arm's 99% is
close to a tautology of how v2 was constructed, and it is reported here
only because the result is the result.

**Confound 1 — the card index is bijective with the test set.** v2 built
exactly one card per case, 83 for 83, and each card's `reason` was
distilled from precisely the span the judge grades against. The developer
question contains that card's `alternative_name` verbatim, so retrieval is
an exact-key lookup: measured, the case's own card is in the top 5 for
**83 of 83** cases and at **rank 1 for 82 of 83**. The only step between
the graded span and the answer is one paraphrase whose explicit purpose is
to preserve meaning. This is structurally the same family of defect as the
confound `docs/FALSIFIER_CONFOUND_HANDOFF.md` fixed in v0 — not identical,
since a paraphrase and a retrieval barrier sit in between, but it is
supervision leaking from the test-set decomposition into the memory being
tested. A real ingestion pipeline is not handed the list of questions.

**Confound 2 — half the KEP questions are answerable without any memory.**
`code_only` has no retrieval, no history and no cards, and still gets
`rationale_match` on **32 of 65** KEP cases. Naming an alternative often
implies its own weakness to any competent model ("why not Rego?" invites
"no static typing"). So in v2 `rationale_match` is a weak discriminator
and `citation_correct` carries most of the signal, which is the metric the
threats section below already flags as satisfied by construction for the
structured arm.

Together these mean the 99/55 gap overstates what structured memory
contributes. The honest reading of v2 is narrower: **given a correctly
extracted per-alternative record, answering "why wasn't X used?" is close
to solved, and the difficulty lives in the extraction, which v2 did not
test.** `BENCHMARK_V2_SPEC.md` Amendment 2 specifies the corrected run
that does test it.

## Threats to validity

- **Citation-correctness is satisfied by construction for the structured
  arm**, exactly as in v0: each retrieved card carries its own
  `Evidence:` line, so answering from a card at all tends to cite
  correctly. This measures whether retrieval found the right card, not
  independent recall of the citation.
- **Cases are clustered, not independent.** 65 of 83 cases come from 15
  KEPs, so several cases share one document and one card-building pass.
  The per-decision mean in the headline table is the conservative
  statistic; the per-case number and its Wilson interval assume more
  independence than the design has.
- **The benchmark is more KEP-weighted than v0** (78% vs 51%). Since the
  KEP arm is the harder one, this makes the pooled number harder to clear,
  not easier.
- **6 of 65 KEP cases have evidence text that also appears in a decoy**
  (KEP-5593 inherits its Alternatives section from KEP-4603, a legitimate
  member of the decoy pool). This can only help the RAG arm.
- **2 of 65 alternative names are topic headings rather than option names**
  (`Scopes`, `On Success and the 10 minute recovery threshold`). Disclosed
  rather than removed, since removing them after the fact would be
  case-level selection.
- **46 of 65 KEP targets are whole-body evidence**, not a labelled
  Why-Rejected part, so for those the judge is matching against everything
  the document says about the alternative, including description.
- **One revert case is knowingly mis-targeted.** `elastic-…-147071`'s
  target sentence is a symptom rather than the cause. It was left exactly
  as v0 had it, because repairing the single revert row that failed would
  be rewriting a failed ground truth.
- **The judge is an LLM.** A v0 variance probe over 9 failures flipped 1,
  so expect roughly ten percent of borderline rows to be unstable.


API failures recorded separately (never scored as correct): 0


## Per-case detail

| case_id | source | code_only | rag | structured | structured_ingested | rag_labelled |
|---|---|---|---|---|---|---|
| `rust-lang-rust-revert-149375` | revert_pair | cR | CR | CR | CR | CR |
| `rust-lang-rust-revert-148937` | revert_pair | cR | CR | CR | CR | CR |
| `rust-lang-rust-revert-149060` | revert_pair | cr | CR | CR | CR | CR |
| `rust-lang-rust-revert-149516` | revert_pair | cr | CR | CR | CR | cr |
| `rust-lang-rust-revert-142034` | revert_pair | cR | CR | CR | CR | CR |
| `kubernetes-kubernetes-revert-140448` | revert_pair | cr | CR | CR | CR | CR |
| `kubernetes-kubernetes-revert-306` | revert_pair | cr | cr | CR | CR | cr |
| `kubernetes-kubernetes-revert-136254` | revert_pair | cr | CR | CR | CR | CR |
| `kubernetes-kubernetes-revert-126794` | revert_pair | cr | CR | CR | CR | CR |
| `kubernetes-kubernetes-revert-127300` | revert_pair | cr | CR | CR | CR | CR |
| `elastic-elasticsearch-revert-154503` | revert_pair | cr | CR | CR | CR | CR |
| `elastic-elasticsearch-revert-152050` | revert_pair | cR | CR | CR | CR | CR |
| `elastic-elasticsearch-revert-151875` | revert_pair | cr | CR | CR | CR | CR |
| `elastic-elasticsearch-revert-120214` | revert_pair | cr | CR | CR | CR | CR |
| `elastic-elasticsearch-revert-147071` | revert_pair | cr | CR | Cr | Cr | CR |
| `kep-keps-sig-storage-1979-object-storage-support::automatically-mount-buckets-` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-storage-1979-object-storage-support::encode-bucketaccess-connecti` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-storage-1979-object-storage-support::cross-resource-protection-fi` | kep_alternative | cr | cR | CR | CR | CR |
| `kep-keps-sig-storage-1979-object-storage-support::bucket-creation-annotation` | kep_alternative | cr | cR | CR | CR | CR |
| `kep-keps-sig-storage-1979-object-storage-support::bucketclass-field-on-bucket-` | kep_alternative | CR | cR | CR | CR | CR |
| `kep-keps-sig-storage-1979-object-storage-support::updating-bucketaccess-secret` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-storage-1979-object-storage-support::bucketaccess-static-provisio` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-storage-1979-object-storage-support::bucketaccess-read-write-acce` | kep_alternative | cR | CR | CR | CR | CR |
| `kep-keps-sig-storage-1979-object-storage-support::handling-systems-that-cannot` | kep_alternative | Cr | CR | CR | cr | CR |
| `kep-keps-sig-auth-2718-20210511-client-exec-proxy::alternative-proposal-reques` | kep_alternative | cR | CR | CR | CR | CR |
| `kep-keps-sig-cloud-provider-2133-out-of-tree-credential-provider::api-server-p` | kep_alternative | Cr | cR | CR | CR | CR |
| `kep-keps-sig-cloud-provider-2133-out-of-tree-credential-provider::sidecar-cred` | kep_alternative | CR | cR | CR | CR | CR |
| `kep-keps-sig-cloud-provider-2133-out-of-tree-credential-provider::bound-servic` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-cloud-provider-2133-out-of-tree-credential-provider::pushing-cred` | kep_alternative | Cr | cR | CR | CR | CR |
| `rust-lang-rust-revert-144407` | revert_pair | cr | CR | CR | CR | CR |
| `kubernetes-kubernetes-revert-129701` | revert_pair | cR | CR | CR | CR | CR |
| `kubernetes-kubernetes-revert-126599` | revert_pair | cr | CR | CR | CR | CR |
| `kep-keps-sig-auth-279-limit-node-access::file-or-flag-based-configuration-of-t` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-auth-279-limit-node-access::api-based-configuration-of-the-apiser` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-auth-279-limit-node-access::allow-kubelets-to-add-any-labels-they` | kep_alternative | cr | cR | CR | CR | CR |
| `kep-keps-sig-auth-279-limit-node-access::forbid-all-labels-regardless-of-names` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-cli-2382-kustomize-exec-secret-generator::enable-plugins-with-env` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-instrumentation-647-apiserver-tracing::introducing-a-new-egressse` | kep_alternative | Cr | CR | CR | CR | CR |
| `kep-keps-sig-instrumentation-647-apiserver-tracing::other-opentelemetry-export` | kep_alternative | cR | CR | CR | CR | CR |
| `kep-keps-sig-storage-1790-recover-resize-failure::allow-admins-to-manually-fix` | kep_alternative | Cr | cR | CR | CR | CR |
| `kep-keps-sig-storage-1790-recover-resize-failure::solving-limitation-of-allowi` | kep_alternative | CR | cR | CR | CR | CR |
| `kep-keps-sig-auth-5681-conditional-authorization::expose-all-conditions-in-adm` | kep_alternative | cr | CR | CR | Cr | CR |
| `kep-keps-sig-auth-5681-conditional-authorization::propagate-an-api-server-gene` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-auth-5681-conditional-authorization::only-one-conditionset-expose` | kep_alternative | Cr | CR | CR | CR | CR |
| `kep-keps-sig-auth-5681-conditional-authorization::require-the-client-to-annota` | kep_alternative | CR | CR | CR | CR | CR |
| `kep-keps-sig-auth-5681-conditional-authorization::extract-label-and-field-sele` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-auth-5681-conditional-authorization::do-nothing-force-implementer` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-api-machinery-3488-cel-admission-control::duck-typed-crds` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-api-machinery-3488-cel-admission-control::openapiv3-ref-in-crds` | kep_alternative | CR | cR | CR | CR | CR |
| `kep-keps-sig-api-machinery-3488-cel-admission-control::matchrules-subresource` | kep_alternative | cR | cR | CR | Cr | CR |
| `kep-keps-sig-api-machinery-3488-cel-admission-control::policyconfiguration-kin` | kep_alternative | cr | cr | CR | cr | cr |
| `kep-keps-sig-api-machinery-3488-cel-admission-control::generate-crds` | kep_alternative | cr | cr | CR | cr | cr |
| `kep-keps-sig-api-machinery-3488-cel-admission-control::scopes` | kep_alternative | cr | Cr | CR | Cr | Cr |
| `kep-keps-sig-api-machinery-2523-consistent-resource-versions-semantics::introd` | kep_alternative | cRH | CR | CR | CR | CR |
| `kep-keps-sig-api-machinery-2523-consistent-resource-versions-semantics::use-sy` | kep_alternative | cr | cR | CR | CR | CR |
| `kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay::global-overri` | kep_alternative | cr | cRH | CR | CR | CR |
| `kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay::per-exit-code` | kep_alternative | cr | crH | CR | CR | CR |
| `kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay::restartpolicy` | kep_alternative | cr | cRH | CR | CR | CR |
| `kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay::on-success-an` | kep_alternative | cr | crH | CR | cr | Cr |
| `kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay::exposing-per-` | kep_alternative | cR | cR | CR | cr | CR |
| `kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay::late-recovery` | kep_alternative | cr | cRH | CR | cr | CR |
| `kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay::more-complex-` | kep_alternative | cR | cRH | CR | cr | CR |
| `kep-keps-sig-api-machinery-2885-server-side-unknown-field-validation::http-hea` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-api-machinery-2876-crd-validation-expression-language::introduce-` | kep_alternative | cR | CR | CR | CR | CR |
| `kep-keps-sig-api-machinery-2876-crd-validation-expression-language::rego` | kep_alternative | CR | CR | CR | CR | CR |
| `kep-keps-sig-api-machinery-2876-crd-validation-expression-language::expr` | kep_alternative | cr | cr | CR | CR | cr |
| `kep-keps-sig-api-machinery-2876-crd-validation-expression-language::webassembl` | kep_alternative | CR | CR | CR | CR | CR |
| `kep-keps-sig-api-machinery-2876-crd-validation-expression-language::starlark-f` | kep_alternative | cR | CR | CR | CR | CR |
| `kep-keps-sig-api-machinery-2876-crd-validation-expression-language::build-our-` | kep_alternative | cR | cR | CR | CR | CR |
| `kep-keps-sig-api-machinery-2876-crd-validation-expression-language::make-it-ea` | kep_alternative | CR | cR | CR | CR | CR |
| `kep-keps-sig-scheduling-5229-asynchronous-api-calls-during-scheduling::1-handl` | kep_alternative | cr | Cr | CR | CR | Cr |
| `kep-keps-sig-scheduling-5229-asynchronous-api-calls-during-scheduling::2-handl` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-scheduling-5229-asynchronous-api-calls-during-scheduling::1-just-` | kep_alternative | cR | CR | CR | CR | CR |
| `kep-keps-sig-scheduling-5229-asynchronous-api-calls-during-scheduling::proposa` | kep_alternative | cR | CR | CR | CR | CR |
| `kep-keps-sig-scheduling-5229-asynchronous-api-calls-during-scheduling::proposa` | kep_alternative | cR | Cr | CR | CR | Cr |
| `kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure::` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure::` | kep_alternative | cR | CR | CR | CR | CR |
| `kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure::` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure::` | kep_alternative | cRH | CR | CR | CR | CR |
| `kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure::` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure::` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure::` | kep_alternative | cr | CR | CR | CR | CR |
| `kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure::` | kep_alternative | cr | CR | CR | CR | CR |

(Capital = correct, lowercase = incorrect, H = hallucinated a wrong citation.)


## Structured failure diagnostics

- own card **not** retrieved into the prompt: **0** (retrieval)
- own card retrieved but the answer still missed the reason: **1** (representation or generation)
- rationale right, citation wrong: **0**

  - _retrieved but missed_: `elastic-elasticsearch-revert-147071`

## v2.1 extraction recall (preregistered metric)

- ingested records: **108** for 83 cases (1.30 per case), vs v2's exact 1.00
- a record from the right decision reached the prompt: **65/65** (100%)
- a record actually *naming* the asked-about alternative reached the prompt: **45/65** (69%)


## Verdict (v2, leaked store): GO

RAG reached only 55% (<=70%) while structured memory reached 99% (>=85%). Structured decision memory materially beats naive RAG. Build DecisionTrace.


## Verdict (v2.1, unsupervised store, unlabelled RAG): GO

RAG reached only 55% (<=70%) while structured memory reached 87% (>=85%). Structured decision memory materially beats naive RAG. Build DecisionTrace.


## Verdict (v2.2 — the headline: unsupervised store, labelled RAG): **CAUTION**

RAG=89%, structured=87% — doesn't cleanly clear either threshold at n=83. Inconclusive; widen the sample or inspect per-decision detail above before deciding.

This is the comparison with no thumb on either scale: the structured store was built without ever seeing the question list, and RAG is told the identity of every chunk it retrieved, including the one that answers the question.
