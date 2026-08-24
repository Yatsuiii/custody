# Critical-path stabilization audit

Date: 2026-08-24

Scope is the production B7 path only. P7, MPBench, and historical research
runners are excluded from execution and are treated as immutable evidence.

| stage | authoritative implementation | finding | debt |
|---|---|---|---|
| source event / receipt | custody/authority.py (AuthorityIssuer, AuthorityReceipt) | Domain canonicalization and signature tests are green; no scorer fields are accepted by the domain API. | none found |
| verification / admission | custody/authority.py, custody/service.py, custody/firestore_store.py | All required parent and generation checks are represented; Firestore transactional reads are normalized by the transaction port. | real-service proof pending |
| durable storage | custody/firestore_store.py | Firestore codec uses maps for tuple-like fields and rejects direct array-of-array values. The installed SDK contract is now documented; the real service has not yet completed the probe. | TD-0001, TD-0003, TD-0005 |
| derivation | custody/authority.py, custody/store.py | IDENTITY, REGISTERED, FREEFORM, dependency closure, and cross-agent forwarding have local production-equivalence coverage. | real-service reconstruction pending |
| policy / generation | custody/firestore_store.py and PolicySnapshot | Compare-and-set generation behavior is transactional in the adapter; local tests cover stale generations. | real-service conflict behavior pending |
| revocation | RevocationController, FirestoreAuthorityStore.commit_root_revocation | Selector is authenticated root identity; marker and event writes are in one transaction; history is append-only. | real-service commit/read/query pending |
| action linearization | AuthorityGateway, FirestoreAuthorityStore.linearize_action | Current-state reads and decision persistence are linearized through the production store. | real-service race evidence pending |
| recovery | FirestoreCustodyGraph, FirestoreAuthorityStore reload paths | Local restart and fail-contained partial-write cases exist; previous E2H liveness bound remains a known historical limitation. | no new semantic defect found; live contract pending |

## Priority conclusion

The unresolved critical path is evidence and adapter execution, not a missing
B7 rule. No item in this audit authorizes changing receipt identity, support
semantics, generation semantics, revocation granularity, or action behavior.

