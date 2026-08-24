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
- real Firestore execution after hardening: NOT-RUN at the time this document
  was first created;
- P7: prohibited.

If any required operation fails, preserve the exact operation, SDK call,
expected/actual behavior, full exception chain, and cleanup status, then stop.
Do not create a P7 identity.

