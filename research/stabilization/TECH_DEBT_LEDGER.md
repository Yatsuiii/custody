# Canonical technical-debt ledger

Date: 2026-08-24
Branch: fix/firestore-adapter-contract

The historical repository audit reported 187 Ruff diagnostics in immutable
research/external-evaluation artifacts. That number is a diagnostic count, not
a unique-debt count. This ledger collapses one root cause into one item and
keeps historical evidence immutable.

Status values are OPEN, CLOSED, or SECURITY-MODEL-CHANGE-REQUIRED. An item is
not closed because a local fake passes; it requires the evidence named below.

| ID | severity | category | exact problem / evidence | disposition |
|---|---|---|---|---|
| TD-0001 | P1 | FIRESTORE / VERIFICATION-INFRASTRUCTURE | No attributable real-service execution had proven every required FirestoreAuthorityStore operation. | CLOSED by the hardened stab01 contract probe: 19/19 operations passed and cleanup verified. |
| TD-0002 | P1 | VERIFICATION-INFRASTRUCTURE | A previous probe could terminate without a result artifact or exception chain. | CLOSED by supervised launcher, atomic terminal artifacts, timeout, and offline failure-branch tests. |
| TD-0003 | P1 | API-CONTRACT / VERIFICATION-INFRASTRUCTURE | Previous launcher needed manual import-path correction and clean-clone startup was not evidenced. | CLOSED by clean-clone import, launcher startup, and 484-test run at 9b962c3. |
| TD-0004 | P1 | TEST-DOUBLE / API-CONTRACT | Fake Transaction.get previously returned a snapshot while installed SDK Transaction.get returns an iterator. | CLOSED by SDK-shaped fake, adapter normalization, and installed-contract tests. |
| TD-0005 | P1 | VERIFICATION-INFRASTRUCTURE | Production readiness previously relied on local/fake coverage while the real service exposed an adapter contract failure. | CLOSED by real Firestore stab01 evidence; no P7 efficacy claim is inferred. |
| TD-0006 | P1 | VERIFICATION-INFRASTRUCTURE | Probe did not record per-operation terminal evidence and could not distinguish child death from PASS. | CLOSED by operation entries, child artifact validation, and supervisor classification. |
| TD-0007 | P1 | TESTABILITY / VERIFICATION-INFRASTRUCTURE | Local production-equivalence evidence reporter called Git without an explicit safe-directory policy and failed in an isolated worktree. | CLOSED by explicit safe-directory invocation and full-suite confirmation. |
| TD-0008 | P2 | SERIALIZATION / FIRESTORE | Domain tuple-like values must not be emitted as direct nested arrays; the codec bug class must remain covered for every B7 object. | CLOSED for known B7 types by named-map codecs, safe-shape tests, round-trip tests, and the real stab01 write/read probe. |
| TD-0009 | P2 | MAINTAINABILITY | Active production/test tree had formatter drift: 73 active files would be reformatted under the configured Ruff formatter. | CLOSED by mechanical Ruff formatting; tests and security identity regression remain required. |
| TD-0010 | P3 | RESEARCH-HYGIENE | Historical research/external-evaluation files contain 187 Ruff diagnostics and are not shipping paths. | CLOSED by an explicit Ruff exclusion policy and preserved diagnostic count; historical source/result artifacts were not rewritten. |
| TD-0011 | P2 | DEPENDENCY / PACKAGING | pyproject optional ADK extra lacked the upper bound used by deployment requirements. | CLOSED by aligning metadata to >=2.6.3,<3 without changing installed major versions. |
| TD-0012 | P2 | VERIFICATION-INFRASTRUCTURE | The stored-artifact test used a skip on a fresh clone, hiding whether the absence was intentional. | CLOSED by making absence an explicit asserted clean-clone state. |
| TD-0013 | P2 | DOCUMENTATION | Stabilization artifacts must distinguish valid evidence, invalid runner attempts, unproven real-service claims, and historical limitations. | CLOSED by the completed stabilization audit artifact set and final report. |
| TD-0014 | P3 | DEAD-CODE / DUPLICATION | Old research machinery and current production B7 implementations must not be confused as one authority path. | CLOSED for the audited critical path: production imports are under custody/ and research artifacts are not imported by the local production-equivalence runner. |

## Security-model review

No item above is authorized to change B7 security identities. If a repair would
change receipt canonical bytes, binding digest, root-key digest, PolicyKey,
generation, capability meet, transform semantics, support closure, revocation
selector, or action semantics, the item must be reclassified as
SECURITY-MODEL-CHANGE-REQUIRED and stopped.

## Current count

14 unique items: 0 P0, 7 P1, 5 P2, and 2 P3. All 14 are closed under the
dispositions above. The historical 187 diagnostics remain preserved as an
audited immutable-artifact fact, not silently deleted or relabeled as active
production lint.
