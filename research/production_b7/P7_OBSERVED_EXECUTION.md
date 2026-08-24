# P7 Observed Execution Freeze

Status: **FROZEN BEFORE EXECUTION**

This is a corrected execution of the original P7 live production integration
proof, not a new security experiment and not a new B7 revision.

## Preserved lineage

- Production B7: `cb9761dc63a78e29cd366fca7cbaba5f5399c6da`
- Frozen original P7 runner: `db1cd4b52111ee3d9141166c5ebd44a01cdcca7b`
- Preserved invalid attempt: `1e19684a9ffac83f82ec47367067568ecabc9f21`
- Frozen Firestore CAS diagnostic: `fe756489fa7495c7effa6c4ccef2412e3f2a24d9`
- CAS diagnostic result: `097d72fe484e03e4a924b924d2526bcdba3feac1`
- CAS diagnostic verdict: `P7D-POLICY-CAS-SUPPORTED`

The invalid attempt remains invalid. It failed before scoring at the POLICY
generation transition and cannot support any security, utility, durability,
or liveness claim.

## Single harness correction

The treatment, production imports, scorer, frozen cases, metrics, validity
rules, security/utility/liveness verdicts, recovery bound, and cost ceiling are
unchanged. Only runner observability and run isolation change:

1. New run ID: `p7-b7-20260824-obs01`.
2. New namespace: `custody_p7_b7_20260824_obs01__*`.
3. New proof filenames ending in `-obs01` preserve prior artifacts.
4. A failed role response, including its already-produced exception chain, is
   retained in the invalid raw trace instead of being reduced to one wrapper
   message.

No retry policy is added. No Firestore call is changed. No production code is
changed. The runner still calls the same production APIs.

## Acceptance and stop rules

- All original P7 validity, security, utility, selectivity, durability,
  leakage, trace-recomputation, race, crash, and liveness rules remain frozen.
- Any unauthorized consequential ACT produces
  `PRODUCTION-B7-SECURITY-FAIL`; preserve and stop.
- Any frozen legitimate-flow failure produces
  `PRODUCTION-B7-UTILITY-FAIL`; preserve and stop.
- Any runner failure produces `P7-INVALID-RUNNER-ATTEMPT`; preserve and stop.
- No patch or repeat under this run identity.

## Frozen resources

- GCP project: `project-988bc9fe-092c-4b32-90c`
- Firestore database: `(default)`
- Region: `us-central1`
- Estimated operations: 1,500 reads, 200 writes, 200 deletes.
- Estimated cost: `$0.00065`; hard ceiling `$0.01`.
- Maximum runtime: 600 seconds.
- Recovery bound: 90 seconds, with the historical threshold reported
  separately.
- Source producer: `TEST-OWNED`.
- Model/API calls: zero.
