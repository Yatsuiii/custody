# Firestore contract probe protocol

This is a storage/API integration check, not P7 and not a security efficacy
experiment. It uses no attack labels, scorer, true-origin field, model call,
or harmful-action case.

The child fixture exercises missing reads, transaction-aware reads, issuer-key
create/read/idempotency, policy write/read/idempotency, legitimate admission
and dependency reconstruction, action-decision persistence, root-revocation
persistence, reverse dependency lookup, and cleanup. Each operation is an
explicit record with SDK call, result, and exception chain when it fails.

The supervisor requires a new namespace and a terminal artifact. It is the only
permitted route to a future contract probe. It must be launched from the
repository scripts path with an explicit unique prefix and output artifact.

## Current status

- previous adapter probe: NOT-RUN / INCONCLUSIVE;
- hardened supervisor: implemented and offline-tested;
- real Firestore execution after hardening: PASS;
- run prefix: custody_firestore_contract_20260824_stab01;
- project/database/region: project-988bc9fe-092c-4b32-90c, (default),
  us-central1;
- terminal artifact digest: `ce16030e207c796fc7fe9c1f05dded1345fe9bc472f9584cafa9ebbceb24c34c`;
- raw child result digest: `b112a6c56654bfb7b38d023014c08a4e72dfd06de2b8a5e031205e1a74ae87e0`;
- operations: 19/19 passed, including fresh-process reconstruction;
- cleanup: 8 collections empty after deleting 8 authoritative test documents;
- model calls: 0; scorer reads: 0;
- P7: prohibited.

The PASS operations were: fresh namespace counts; missing outside-transaction
read; missing transaction-aware read; issuer-key create/read/idempotent path;
policy create/read/idempotent path; legitimate admission/replay/read;
dependency reconstruction; action-decision create/read; root-revocation
create/read; reverse dependency query; and a separately started process that
reconstructed issuer key, policy, envelope, dependencies, receipt-root,
decision, revocation, marker, and reverse-dependency state.

If any required operation fails, preserve the exact operation, SDK call,
expected/actual behavior, full exception chain, and cleanup status, then stop.
Do not create a P7 identity.
