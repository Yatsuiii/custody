# Concurrency and durability audit

## Current boundaries

- FirestoreAuthorityStore._run_transaction uses the installed Firestore
  transactional wrapper for the real client and the narrow fake runner for
  offline tests.
- Admission reads policies, parents, dependencies, and receipt-root state
  before create-only writes.
- Policy writes implement generation compare-and-set.
- Action decisions are linearized by request identity and request digest.
- Root revocation writes the immutable event and per-root markers in one
  transaction; repeated identical requests are idempotent and conflicting
  selectors are rejected.
- Action evaluation reads current policy/generation/revocation state through
  the transaction-local port; stale cached authority is not a grant.

## Covered locally

The production-equivalence suite covers duplicate envelopes, partial admission,
missing state, stale generation, mixed parents, selective revocation, restart
reconstruction, killed-writer behavior, and action/revocation ordering through
the local production APIs. E2H-R1E provides real persistence/process safety
evidence, with its separately recorded 90-second recovery-liveness failure.

## Not yet established

No new security semantics are needed. Real Firestore transaction conflicts,
server timestamps, restart reconstruction, and cleanup remain unproven until
the non-security contract probe completes. A probe failure must reopen a ledger
item; it must not be converted into a B7 efficacy result.

