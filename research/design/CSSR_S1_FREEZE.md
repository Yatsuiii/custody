# CSSR-S1 Freeze Record

**Status:** REVIEWED / FROZEN

**Frozen on:** 2026-08-29

**Specification:**
[`CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md`](CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md)

**Specification SHA-256:**
`dd18a84f08fb3330824fed01f2d144c849c6e1af24ecba081d77f224128ce007`

**Repository HEAD at review:**
`8b9086f3afdcfc54015aa16b03265bff8de8cebb`

The specification is frozen by content digest, not by the repository HEAD.
The working tree already contained unrelated modified files, including the
research sources reviewed here. The source hashes below identify the exact
bytes used; HEAD alone does not.

## Review verdict

**REVIEWED / FROZEN as a valid preregistration.** This is not evidence that
CSSR works. It means the proposed falsifier now has a safe baseline, one named
architecture switch, independent deterministic ground truth, exact fixtures
and denominators, fixed verdict gates, explicit limits, and a reproducible
artifact contract.

The strategic verdict remains **CAUTION**. The architecture is still
**architecturally unshippable** until the falsifier passes and production input
and control capture are independently demonstrated.

## Findings resolved before freeze

| Finding | Why it blocked freeze | Resolution |
|---|---|---|
| Candidate-owned receipt could self-certify | Comparing an envelope with a trace emitted by the same mechanism is tautological | Added a harness-owned recording proxy and fixture-owned control ground truth that neither arm can mutate |
| Selection-only influence was not isolated | Passing selector text to the producer tested ordinary context lineage, not an implicit control channel | `J-A-SEL` now receives `[Q-1, S-A]` as producer context and `[SEL-AP]` only as a dynamic control input |
| Metric populations were open to interpretation | A later plan could change denominators or aggregate worlds opportunistically | Froze four metric worlds, exact affected sets, mode-specific denominators `2` and `13`, and a three-instance clean-preservation population |
| Window selection lacked literal boundaries | “Selects exactly” was not independently reproducible | Froze source/operation metadata, timestamps, half-open intervals, generation, and selected roots |
| The missing-edge case contradicted the TCB contract | An untrusted caller has no authority-bearing parent field to omit | Replaced it with `C08_CONTROL_EDGE_CORRUPTION`, which drops a sealed control edge between trace capture and admission |
| Spoof cases were duplicated | Two cases exercised the same payload-forgery boundary | Merged them; the frozen suite is `C01`–`C14` |
| `SourceUnit` could imply unproved span provenance | S1 does not create sub-document identities | Froze every `SourceUnit` as one whole immutable source record and retained the mixed-record fail-closed limit |
| Job identity/digest could be circular or unstable | A digest or shared counter could drift across comparison worlds | Froze literal job ids and a canonical SHA-256 job-body encoding that excludes id, digest, time, randomness, and list position |

No unresolved preregistration blocker remains. Unresolved architecture and
external-validity risks remain explicitly listed in the specification.

## Frozen evidence inputs

Working-tree entries use SHA-256 of the exact reviewed bytes.

| Evidence | Frozen identity |
|---|---|
| `RESEARCH.md` | SHA-256 `61036f7467383eb65cb572d4b05fcc3c72b97ca26a65be8f37b3bd97b71ad60f` |
| `research/experiments/RSM_CRUX_SERIES_SUMMARY.md` | SHA-256 `8f9071d2acc5e4caaafe9b1d1f94ce6332e195b5ec47710636ba50f86e4075d9` |
| `research/design/TRANSFORMATION_MODEL.md` | SHA-256 `8f072c8c67ce8f82989f9b01d9f285f4fed4c4eef8db1e0433b4a886bb0d7b3e` |
| `research/design/REPAIR_SEMANTICS.md` | SHA-256 `c586b184ba57b5888cdd9463eb9139eedaf340adb13c3496f5665354fe4414e9` |
| `research/design/DYNAMIC_TRUST_MODEL.md` | SHA-256 `66c2a35e39cdfbb07e63d6c44abb517cada4f1bbf3a0674da816e11f6323bae6` |
| `research/design/AUTHORITY_MODEL.md` | SHA-256 `14ba2ddf5820ffdafcf26f7e2ab10f44701ad3c43911943d5e520082efaec79b` |
| `research/experiments/E2D_DESIGN_FALSIFIER/PLAN.md` | SHA-256 `2f0114d4ec972074bad61c2fd36bb399894f0f354778f450df49c00f5a5f378e` |
| `research/experiments/E2D_DESIGN_FALSIFIER/RESULT.md` | SHA-256 `c8abd393329d8569d0f3c03e10252ff053b30fa817cfb422e2e3f78c469b1ba3` |
| `research/experiments/E2D_EXT1_WINDOW_WIDENING/RESULT.md` | SHA-256 `c75a8e5ad3e8cf0f417cd3cc6a5cd73a1f819d27e240eca2b51be54f47df1148` |
| `research/experiments/E2D_EXT2_OVERLAPPING_WINDOWS/RESULT.md` | SHA-256 `505347059ee076b651398303ae66a15271737c7bbb2a4ffcc7a025b49d1c26e2` |
| `research/experiments/E2D_EXT3_LEGACY_UNKNOWN_TIMESTAMP/RESULT.md` | SHA-256 `9028439d7fa61dbf9522042eeeb2fe860cecdaddeef195bfe8c32667b6fabc4d` |
| `research/experiments/E2D_EXT4_MANIFEST_PARENTS/RESULT.md` | SHA-256 `9c1a341a430772e380dfe1accc83a07426375e477754059d56e4caa05a23bcfb` |
| Receipt collector result at commit `82c991e` | Git blob `bf4d987842cee437dd9a3930eb0d151fe3094b0c` |
| `fix/receipt-collector-id-resolution` | local and `origin` commit `28531eb173f8c97958d679986e942c1c85f5247e` |

## Freeze rule

Before drafting or reviewing any execution plan, recompute:

```text
sha256sum research/design/CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md
```

The result must equal the specification digest above. Any byte change voids
this freeze and requires a new review record. Any material change to the
hypothesis, architecture switch, threat model, fixtures, oracle, metric
population, threshold, or kill condition requires `CSSR-S2`; it cannot be
introduced as a CSSR-S1 plan detail.

An execution plan may add only mechanical serialization details that preserve
the frozen values. If a detail can change an expected edge, state, visibility
decision, denominator, or verdict, it is not mechanical and the plan must stop.

## Authorization boundary

Review and freeze are complete. Creation of
`research/experiments/CSSR_S1_SELECTION_CHANNEL/PLAN.md` is now eligible for a
separate explicit authorization, but is **not authorized or created by this
review**.

Still unauthorized:

- `fixture.json`, `run.py`, `result.json`, or `RESULT.md`;
- any experiment execution;
- any `custody/*.py` change;
- any production integration, branch merge, commit, or push; and
- any claim that CSSR has passed, works, or provides retrospective repair.

## Review checks

- Baseline, hypothesis, one changed variable, metrics, thresholds, kill
  conditions, result tables, and artifact lineage are present.
- Four metric worlds, fourteen cases, literal windows, exact graph parents, and
  metric denominators are frozen.
- Safety is checked by graph/set/digest operations only; no LLM, embedding,
  human semantic judgment, or self-declared provenance participates.
- The exposure oracle is independent of both mechanism arms.
- Integrity and availability are separate; no utility score can compensate for
  an integrity failure.
- Atomic admission, generation freshness, duplicate delivery, conflict,
  crash/replay, schema evolution, and synthetic-data retention are covered.
- The safe coarse baseline is expected to remain safe; CSSR must additionally
  preserve the exact clean treatment population.
- Legacy fused records and mixed-content source records remain explicitly
  fail-closed.
- No experiment directory or implementation was created during review.

## DDIA Review

**Verdict:** architecturally unshippable, but valid to falsify.

The spec now fixes ownership, atomic visibility, fresh-generation reads,
idempotency, conflict behavior, recovery probes, artifact schema, and synthetic
data retention. The dominant unresolved risk is whether a production collector
can completely observe dynamic data and control influence. A deterministic
harness PASS cannot establish that external-validity premise.

## Experiment Review

**Verdict:** valid and frozen; result not run.

**Baseline:** safe fused-record revocation.

**Hypothesis:** isolated derivation shards improve clean preservation without
creating an unsafe survivor.

**Changed variable:** `materialization_mode` only.

**Metric:** fixed structural counts, sets, generations, and digests.

**Kill/continue decision:** an integrity failure kills CSSR; safe failure to
preserve the frozen clean population shelves it. Only a full PASS permits a
bounded prototype discussion.

**Missing evidence:** all execution results and production external validity.

## Outcome Ledger

### Decision 1

**Decision:** freeze CSSR-S1 as the only admissible specification for a future
selection-channel/composite-view falsifier.

**Lane:** causality/debugging systems.

**Artifact:** this freeze record and the content-addressed specification.

**Acceptance gate:** specification SHA-256 matches; an authorized plan copies
all frozen values and introduces no semantic provenance judgment.

**Result:** REVIEWED / FROZEN; execution not authorized.

**Next action:** obtain explicit authorization for the isolated `PLAN.md`, then
verify its recorded spec digest before any harness file exists.

**Kill condition:** digest mismatch, changed verdict gate, candidate-owned
oracle ground truth, or any need for semantic independence judgment.

**Status:** shipped.
