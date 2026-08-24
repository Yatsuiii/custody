# Fresh P7 Production-Equivalence Identity

Status: **DESIGNED — NOT IMPLEMENTED OR EXECUTED**

This identity may be frozen only after its harness commit is created and
pushed. It does not authorize execution by itself.

## Identity

- Experiment: `P7_FRESH_PRODUCTION_B7_LIVE_EQUIVALENCE_CODEC01`
- Run ID: `p7-b7-20260824-codec01`
- Firestore namespace: `custody_p7_b7_20260824_codec01__*`
- Production B7 codec-repair SHA:
  `3f85af9d2f3a956ca28ea45ddb8417a9c83a5c75`
- Project/database/region: `project-988bc9fe-092c-4b32-90c` / `(default)` /
  `us-central1`
- Source producer: `TEST-OWNED`

The following identities are forbidden for reuse:

- `p7-b7-20260824-ec32e4e31d21`
- `p7-b7-20260824-obs01`

Their invalid evidence remains immutable.

## Frozen implementation boundary

A future harness commit must start from the codec-repair SHA and reuse the
already-frozen P7 treatment/scorer semantics. It may import the corrected role
error observability from runner commit
`bcb95fb181f3bd5e7eea86533217c2dca084bb28`, but it must not import either
old result artifact or reuse either old namespace.

No B7 security rule, fixture case, metric, scorer, recovery bound, cost
ceiling, or source classification may change. The only implementation delta
under evaluation is the production Firestore codec repair.

## Pre-execution gates

1. Freeze and push a harness commit containing the new run ID, namespace, and
   distinct proof filenames.
2. Verify production security-module changes from the original B7 SHA are
   limited to commit `3f85af9d2f3a956ca28ea45ddb8417a9c83a5c75`.
3. Verify local harness HEAD equals its remote branch SHA.
4. Re-run the full unit suite, unchanged production-equivalence suite, and
   changed-file Ruff checks.
5. Verify all eight new namespace collections are empty.
6. Print the existing 1,500-read, 200-write, 200-delete estimate, `$0.00065`
   estimate, and `$0.01` hard ceiling before treatment.

## Stop rules

The original P7 validity/security/utility/liveness rules remain unchanged.
Any runner failure, unauthorized ACT, utility failure, or liveness limitation
is preserved under this identity with no patch or repeat. No live execution is
performed in the codec-repair session.
