# E2D Design Falsifier — Result

## 1. Final verdict: PASS

Canonical `result.json` SHA-256: `e8947943d7986f25e063c017f8c5f9e7adfe130b637d8586ec00e67c9a06f08e`.
The verdict was calculated by `run.py`; this document does not choose it.

## 2. Baseline behavior

CURRENT_CUSTODY was exercised through the real frozen `take_custody`, `CustodyGraph`, and `ExportGateway`. It reproduced trusted-tool echo authority laundering, transformed exact-hash ancestry loss, and real E1 multi-parent edges. Its closest shipped revocation was whole-revision deletion, which removed the outside-window sibling; it has no interval generation, repair plan, or replacement API.

## 3. Treatment behavior

STRUCTURAL_ENVELOPE_A used only collector-observed IDs and configured policy. FREEFORM outputs retained structural support but were capped at INFORM; the parentless RELAY carried UNKNOWN_CONTEXT; active generation 1 blocked the exact affected closure; repair created a new replacement ID and never raised an unchanged record.

## 4. Metrics

| Mechanism | Metric | Numerator | Denominator | Value | Supported |
|---|---|---:|---:|---|---|
| CURRENT_CUSTODY | `direct_parent_recall` | 8 | 13 | `0.6153846153846154` | `True` |
| CURRENT_CUSTODY | `affected_recall` | 1 | 4 | `0.25` | `True` |
| CURRENT_CUSTODY | `false_act_permits` | 2 | 6 | `2` | `True` |
| CURRENT_CUSTODY | `same_record_authority_increases` | 0 | 17 | `0` | `True` |
| CURRENT_CUSTODY | `benign_inform_retained` | 0 | 1 | `False` | `True` |
| CURRENT_CUSTODY | `outside_sibling_preserved` | 0 | 1 | `False` | `True` |
| CURRENT_CUSTODY | `replay_digest_stable` | 0 | 0 | `None` | `False` |
| CURRENT_CUSTODY | `unsafe_fault_windows` | 0 | 0 | `None` | `False` |
| STRUCTURAL_ENVELOPE_A | `direct_parent_recall` | 13 | 13 | `1.0` | `True` |
| STRUCTURAL_ENVELOPE_A | `affected_recall` | 4 | 4 | `1.0` | `True` |
| STRUCTURAL_ENVELOPE_A | `false_act_permits` | 0 | 6 | `0` | `True` |
| STRUCTURAL_ENVELOPE_A | `same_record_authority_increases` | 0 | 17 | `0` | `True` |
| STRUCTURAL_ENVELOPE_A | `benign_inform_retained` | 1 | 1 | `True` | `True` |
| STRUCTURAL_ENVELOPE_A | `outside_sibling_preserved` | 1 | 1 | `True` | `True` |
| STRUCTURAL_ENVELOPE_A | `replay_digest_stable` | 1 | 1 | `True` | `True` |
| STRUCTURAL_ENVELOPE_A | `unsafe_fault_windows` | 0 | 4 | `0` | `True` |

## 5. Crash probes

| Probe | Pre-recovery affected action | Final equals no-fault | Retry count |
|---|---|---|---:|
| C1 | `DENY` | `True` | 2 |
| C2 | `DENY` | `True` | 2 |
| C3 | `DENY` | `True` | 2 |
| C4 | `DENY, DENY` | `True` | 2 |

## 6. Concurrency/high-watermark probe

The late descendant was born `BLOCKED`; its immediate action result was `DENY`. Probe result: `PASS`.

## 7. First failure

None; every PASS gate was satisfied.

## 8. Ground-truth leakage

Leakage check: `True`. Ground-truth reads before scoring: `0`. The treatment constructor rejected a ground-truth argument and the runtime fixture contained no scorer-only keys.

## 9. Limitations

- E2D does not test ORIGIN/RELAY policy misclassification.
- The SQLite state machine proves only the logical crash/replay protocol; it does not prove Firestore/Cloud Run production atomicity.
- Structural support proves exposure, not truth or semantic entailment.
- PASS does not authorize production implementation, a novelty claim, or a claim that Custody solves memory poisoning.

## 10. Next gate

Preregister an adversarial ORIGIN/RELAY policy-misclassification falsifier with configured role as its only changed variable; do not implement it in E2D.
