Objective: Write one handoff document that lets a brand-new session resume
the P7 line of work with zero prior context: what was independently verified
this session, what was built, what real bug was found, and the exact next
task. Documentation only -- no code, no further Firestore execution, no
change to any frozen artifact.

Branch: docs/p7-handoff-20260825-01
Parent: probe/p7-barrier-contract-20260824-02 @ 5fa161c16b9a498cc1635c095a00d2e4f802dfba
        (corrected O-barrier probe evidence; frozen P7 harness and both
        barrier probes MUST NOT be modified or moved by this work)

Allowed files:
- research/production_b7/P7_NEXT_SESSION_HANDOFF.md
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to scripts/p7_run.py, scripts/p7_barrier_contract_probe.py,
  scripts/p7_barrier_contract_probe_o2.py, custody/*, or
  tests/test_b7_production_equivalence.py.
- No further real-Firestore execution of any kind in this session.
- No new probe, no P7 execution, no branch other than this docs branch.
- Every SHA, branch name, and namespace prefix quoted in the handoff must be
  copied from this session's actual verified output, not retyped from memory.

Baseline: N/A -- documentation only; `git diff --stat custody/ tests/
scripts/` empty is the only relevant no-drift check.

Acceptance gates:
1. The handoff document lets a reader with zero prior context reconstruct,
   without re-deriving: the reconciliation-audit finding (stabilization
   lineage was a superset, now pushed as origin/stabilization/custody-final-16d3459),
   the frozen P7 harness identity and branch, both barrier-probe results
   (probe 01 FAIL/probe-body-bug, probe 02 FAIL/real HARNESS-BARRIER-BUG),
   and the exact root cause (DocumentReference.get(transaction=t) bypasses
   Transaction.get(), confirmed from installed SDK source).
2. States explicitly, in one place, everything still NOT authorized: P7 run01
   itself, and any further probe/harness execution until the fix below is
   made and re-verified.
3. Gives one concrete, scoped next task: fix _P7Client's read-interception
   strategy in a NEW harness revision (new branch/new P7 identity, since the
   current frozen identity p7-b7-20260824-run01 cannot be reused per this
   session's own standing rule), re-run both O and P barrier probes as a
   fresh pair under a fresh probe identity, and only then reconsider
   authorizing a live P7 run.
4. Lists every relevant branch/SHA table so the next session does not need
   to re-run `git ls-remote`/`git log` archaeology to find them.

Verification: read-through against this session's actual tool output (SHAs,
digests, branch names) for exact-copy accuracy; `git diff --stat custody/
tests/ scripts/` empty.

Status: active
