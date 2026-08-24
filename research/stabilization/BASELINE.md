# Stabilization Baseline

Date: 2026-08-24

## Repository identity

| Field | Value |
|---|---|
| Branch | `fix/firestore-adapter-contract` |
| HEAD | `aae9d4097a230b40bbea3b42a37043cf2dcc7acf` |
| Origin branch | `origin/fix/firestore-adapter-contract` |
| Local == origin | YES |
| Tracked worktree | CLEAN |

The baseline includes the bounded Firestore adapter-contract repair, its
contract tests, the probe launcher, and the explicit prior-probe status. No
P7 harness or P7 execution identity is part of this stabilization branch.

## Verification state

- Full unit suite: `479 passed, 1 skipped`.
- Firestore adapter/codec/local equivalence checks: passed; local result
  remains `LOCAL-EQUIVALENCE-SUPPORTED`.
- Ruff check over the repository: **187 diagnostics**.
- Ruff formatter check: **88 files would be reformatted; 30 already formatted**.
- APOSD: the last committed changes passed the repository APOSD hook; no
  standalone APOSD command is configured in the repository.
- Real Firestore contract probe: `NOT-RUN / INCONCLUSIVE`; all eight prior
  scratch collections were empty after the silent attempt.

The 187 Ruff diagnostics are a tool baseline, not assumed to be 187 unique
technical-debt causes. The ledger must consolidate root causes and audit
non-Ruff debt separately.

## Frozen B7 security-file hashes

| File | SHA-256 |
|---|---|
| `custody/action.py` | `92bccb5586d45e2c267253b3256d84377362d43029a6400195eaa43423b3fec7` |
| `custody/authority.py` | `e05254a00a7a4ad9e7cf54e2488a40478798a1d11238b3ab8acfdfe5cf7b5b6f` |
| `custody/firestore_store.py` | `0d9c37087bc194c009daf157031344940daa29c84c7822efb8c68db8717bf643` |
| `custody/store.py` | `01e7980166a80b2862930cd167df064dfecfcc11b5ac1f407c95aff693c93e63` |
| `custody/nonce_ledger.py` | `e21792fe3599ba416bab8198ca97f1d12b3c5e803f048e6c9069ae0e78de7f58` |
| `custody/service.py` | `0b0036d0795099486e67d05bbf635b43e18bf8a877a44042bb2dd5002f8d6c14` |

## Existing documented state

No `research/stabilization/` debt ledger existed at baseline. Existing B7
documents record the Firestore codec audit and the adapter contract audit;
the latter explicitly leaves real-service usability unproven. Historical
invalid P7 evidence remains immutable and is outside this cleanup scope.

## Baseline decision

Production edits are now permitted only through bounded stabilization commits,
with the B7 security identities listed in the task frozen unless an item is
explicitly classified `SECURITY-MODEL-CHANGE-REQUIRED`.
