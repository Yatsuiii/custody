# Critical-path stabilization audit

Date: 2026-08-24

Scope is the production B7 path only. P7, MPBench, and historical research
runners are excluded from execution and are treated as immutable evidence.

| stage | authoritative implementation | finding | debt |
|---|---|---|---|
| source event / receipt | custody/authority.py (AuthorityIssuer, AuthorityReceipt) | Domain canonicalization and signature tests are green; no scorer fields are accepted by the domain API. | none found |
| verification / admission | custody/authority.py, custody/service.py, custody/firestore_store.py | All required parent and generation checks are represented; Firestore transactional reads are normalized by the transaction port. | real-service proof pending |
| durable storage | custody/firestore_store.py | Firestore codec uses maps for tuple-like fields and rejects direct array-of-array values. The installed SDK contract and 19-operation real-service probe pass. | none |
| derivation | custody/authority.py, custody/store.py | IDENTITY, REGISTERED, FREEFORM, dependency closure, and cross-agent forwarding have local production-equivalence coverage; real-store reconstruction passed. | none |
| policy / generation | custody/firestore_store.py and PolicySnapshot | Compare-and-set generation behavior is transactional in the adapter; local tests and real policy transaction paths pass. | none |
| revocation | RevocationController, FirestoreAuthorityStore.commit_root_revocation | Selector is authenticated root identity; marker and event writes are in one transaction; history is append-only; real commit/read/query passed. | none |
| action linearization | AuthorityGateway, FirestoreAuthorityStore.linearize_action | Current-state reads and decision persistence are linearized through the production store; real decision persistence/reconstruction passed. | concurrency race efficacy remains outside this non-security probe |
| recovery | FirestoreCustodyGraph, FirestoreAuthorityStore reload paths | Local restart and fail-contained partial-write cases exist; previous E2H liveness bound remains a known historical limitation. | no new semantic defect found; live contract pending |

## Priority conclusion

The unresolved critical path is evidence and adapter execution, not a missing
B7 rule. No item in this audit authorizes changing receipt identity, support
semantics, generation semantics, revocation granularity, or action behavior.
