# P7 Firestore Policy CAS Diagnostic

Status: **FROZEN BEFORE EXECUTION**

This diagnostic is not a P7 rerun and produces no B7 security or utility
result. It exists solely because the frozen P7 attempt ended before scoring
with `AuthorityUnavailable: B7 Firestore transaction failed` while advancing
one policy generation. The runner discarded the wrapped Google API exception.

## Experiment review

- Baseline: P0-P6's fake-Firestore production-store tests support
  `put_policy` generation compare-and-set. The first P7 live attempt persisted
  its initial policies and admissions, then became an invalid runner attempt at
  the fresh POLICY process's generation transition.
- Hypothesis: the frozen production `FirestoreAuthorityStore.put_policy` can
  create generation 1 and compare-and-set it to generation 2 against real
  Firestore from independently started processes.
- Single changed variable: fake/local persistence is replaced by the existing
  real Firestore database. Production code and policy bytes remain frozen.
- Metrics: initial create result, generation CAS result, independent reread,
  exact exception chain, and post-cleanup namespace count.
- Acceptance threshold: create succeeds; CAS succeeds with
  `expected_generation=1`; a fresh process reads exactly generation 2/version
  `p7d-v2`; cleanup leaves every diagnostic collection empty.
- Kill condition: any CAS exception or reread mismatch stops the investigation.
  Do not change production B7 and do not rerun full P7.
- Result classes:
  - `P7D-POLICY-CAS-SUPPORTED`
  - `P7D-PRODUCTION-FIRESTORE-POLICY-CAS-FAIL`
  - `P7D-INVALID-DIAGNOSTIC`

## Frozen environment

- Production B7: `cb9761dc63a78e29cd366fca7cbaba5f5399c6da`
- Invalid P7 evidence: `1e19684a9ffac83f82ec47367067568ecabc9f21`
- GCP project: `project-988bc9fe-092c-4b32-90c`
- Firestore database: `(default)`
- Region: `us-central1`
- Namespace: `custody_p7d_policy_cas_20260824_01__*`
- Processes: CREATE, CAS, and READ are independently started Python processes.
- Maximum runtime: 180 seconds.
- Estimated operations: at most 25 reads, 2 writes, and 2 deletes.
- Estimated cost: less than `$0.00002`; hard ceiling `$0.001`.
- Model/API calls: zero.

## Exclusions

No source receipt, payload, scorer field, benchmark label, action decision,
revocation, private key, or production customer data enters this diagnostic.
It may classify only the production Firestore policy persistence boundary.
