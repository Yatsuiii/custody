# DecisionTrace Action-Compliance Falsification Protocol

Status: FROZEN as of this document's commit. See "Freeze enforcement"
below. This document is Phase 0 of the preregistered experiment described
in the session brief; it must exist, complete, before any benchmark task
is discovered or written (Phase 4+).

## 1. What this experiment is

Not a QA/retrieval benchmark. A test of whether a deterministic
`AuthorityProof` changes what code a capable coding agent actually
writes, when every arm already has all relevant organizational context.

Full specification of the hypothesis, metric, and GO gate lives in
`ACTION_COMPLIANCE_SPEC.md` (Phase 1), written before any task is
collected, per the same freeze discipline.

## 2. Repository / product coordinates (frozen)

| Field | Value |
|---|---|
| Repository | `Yatsuiii/custody` |
| DecisionTrace directory | `decision-trace/` |
| Production product branch | `explore/decision-trace-v0` |
| Frozen production commit (SHA) | `9bdec25e9a9e3aee157e5f73b2c78e690fc343e6` |
| Research branch (this experiment) | `research/decisiontrace-action-compliance` |
| Research branch parent | `9bdec25e9a9e3aee157e5f73b2c78e690fc343e6` (exact, verified via `git merge-base --is-ancestor`) |

Confirmed: `9bdec25` is `explore/decision-trace-v0`'s current tip and is
a merge of `integration/decisiontrace-authority-proof` (the branch that
ported the deterministic AuthorityProof architecture: Evidence Scout ->
Lifecycle Resolver -> deterministic AuthorityProof -> Provenance
Challenger -> Gemini explanation) into the frozen submission branch.

**Production is frozen.** This experiment does not modify
`explore/decision-trace-v0`, does not deploy, and does not touch
Firestore.

## 3. Frozen authority-resolver file hashes

These SHA-256 hashes were computed against `research/decisiontrace-action-compliance`
at its branch point (`9bdec25e9a9e3aee157e5f73b2c78e690fc343e6`) and
constitute the frozen implementation. Any run of
`scripts/verify_authority_freeze.py` (Section 8) that produces a
different hash for any of these files means the authority engine has
changed and the experiment is invalid from that point forward.

```
687be19116305a773f061383a5ce17b8ac8a84b3ab50dff9d8d0d485e49f49ee  app/authority.py
65b77c8f79ac652d1d656669b5de3c0688fbce1f475c46dd95e7aebcb600a22b  app/collaborate.py
9f95c3f831f187439a356cb42930b254bbe9da05fc7763314b8373e4fdac04a2  app/ui.py
e5abd66bae31320ed5308520b2066912e237ab1544e17ad0827b61ce6ab197a6  app/tests/test_authority_explanation.py
df7088ebd27072e09730a2a6c5ec3b87504759721f04de0ec5de8132ff88d38a  app/tests/test_authority_proof.py
adabde5deba2a2920bb0d47fb756abdfac0f4e6172011de94ba514e7130dae32  app/tests/test_authority.py
0b6541038b874ccf9e5e30a7bf52a339ce989bd865511681b42296369ffd3614  app/tests/test_authority_reconsideration.py
c6227df3eedc40a20ec48418070047ae3be2511436528288998bac21ddc75f02  app/tests/test_authority_regression_prospective.py
6ef8bd6f98b2ae4fd1fd4f40c96b2fdfd23eff3e004e2bf982e8e57081c521de  app/tests/test_collaborate_authority.py
```

`app/authority.py` is the deterministic resolver itself
(`resolve_authority_with_proof`, `AuthorityProof`, `CandidateAssessment`,
exclusion-reason logic). `app/collaborate.py` and `app/ui.py` are
included because they are where the proof is wired into the worker
pipeline and rendered — a change to either could alter what evidence
reaches a coding agent even if `authority.py` itself is untouched. The
six `test_authority*`/`test_collaborate_authority.py` files are included
because they pin the resolver's documented semantics; if their content
changes, the meaning of "frozen authority semantics" has silently
shifted even if `authority.py`'s bytes are unchanged elsewhere.

## 4. What the AuthorityProof schema provides to Arm C

From `app/authority.py`, an `AuthorityProof` (frozen shape, do not
extend during the experiment) carries:

- `requested_scope`
- the governing decision (if any) — `AuthorityResolution`
- `candidates` — `list[CandidateAssessment]`, each with a decision id,
  its status, and (if excluded) an `exclusion_reason`
- lifecycle witnesses — the specific edge (e.g. `REVERTS`, `SUPERSEDES`)
  that establishes the winner, replayed from `_replay_authority_records`
- ambiguity signaling when no single governing decision resolves

Exclusion reasons are produced deterministically by
`_status_exclusion_reason` and the lifecycle-edge replay logic in
`_governing_proof`/`resolve_authority_with_proof` — not by an LLM call.

## 5. Frozen experimental settings

These must not change after this document is committed, for the
duration of the experiment (Phases 2 onward, when they are eventually
run under a separate, explicitly authorized compute session):

| Setting | Frozen value | Notes |
|---|---|---|
| Authority resolver | `app/authority.py` @ hash above | No new heuristic, no fix, no threshold tune after task collection begins |
| Coding-agent model | TBD at experiment-launch authorization | Must be identical across Arms A/B/C; recorded here once chosen, then frozen |
| Coding-agent prompt | TBD, drafted in Phase 4 before any comparative run | Same prompt text/template across arms except for the arm-specific context block |
| Tool permissions | TBD, drafted with the harness design | Identical across arms: same shell/file-edit access, same repo checkout mechanism |
| Context formatting | Raw context identical across Arms A/B/C; Arm C adds only the `AuthorityProof` block | No extra documents given to Arm C beyond what the frozen resolver derives from the same corpus given to A/B |
| Token budget | TBD, set once and frozen at launch | Same across all arms |
| Generation temperature | TBD, set once and frozen at launch | Same across all arms |
| Maximum steps | TBD, set once and frozen at launch | Same across all arms |
| Patch submission format | TBD, drafted in Phase 4 | A unified diff or full-file patch, deterministic to grade mechanically |

The "TBD, set once and frozen at launch" rows are intentionally not
filled in by this document, because filling them in requires choosing
and authorizing an actual execution harness (which coding-agent runtime
executes 30-50 tasks x 3 arms x 2-3 runs against pinned OSS commits,
what it costs, and where it runs) — a decision outside this session's
scope. This document exists so that whichever session makes that choice
inherits an already-frozen authority engine and cannot retroactively
change it to make an arm look better.

## 6. Freeze enforcement

`scripts/verify_authority_freeze.py` (Section 8) recomputes the hashes
in Section 3 and exits nonzero on any mismatch. It must be run as a
precondition before Phase 4 task construction begins, before Phase 13's
full run, and as part of Phase 14 reporting (to prove no drift occurred
during the run).

No prompt edits, heuristic fixes, or case exclusions to the authority
resolver are permitted after this document is committed, per Phase 13's
"no changes after outputs begin" rule in the external protocol. Any
change requires: (1) explicitly declaring the freeze broken, (2) a new
session-contract entry, (3) a fresh hash freeze, (4) discarding any
comparative results already gathered under the old freeze.

## 7. Explicitly out of scope for this document

This document does NOT preregister the hypothesis, metric, or GO gate —
that is `ACTION_COMPLIANCE_SPEC.md` (Phase 1), a separate file, written
next but only after this freeze is committed, matching the external
protocol's phase ordering.

This document does NOT select or construct benchmark tasks (Phase 4+),
does NOT choose the coding-agent execution harness, and does NOT
authorize any compute spend. Those are separate, explicit decisions.

## 8. Guard script

`decision-trace/scripts/verify_authority_freeze.py` — recomputes SHA-256
over the file list in Section 3 and diffs against the frozen table
embedded in the script. Run: `python decision-trace/scripts/verify_authority_freeze.py`.
