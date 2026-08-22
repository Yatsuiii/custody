# Baseline Reproducibility

This is the baseline ladder for the external evaluation, not the older
internal `BASELINES.md` numbering. The IDs are frozen here so a future run
cannot silently swap a baseline after seeing results.

## Frozen ladder

| ID | Baseline | Pinned source | Reproducibility status | Allowed quantitative use |
|---|---|---|---|---|
| **B0** | No memory-security defense | The selected benchmark's native no-defense cell; for the first gate, the external TMA-NM fixture | Trivial only when the benchmark supplies the attack and task; no model call for the first fixed tool-echo cell | Control for raw harmful-action success and native attack metrics |
| **B1** | Current frozen Custody | Production subtree at `31bd1b03c544a3fd2626491c5596694586cf3416` (the E1 multi-parent fix; no production files are changed by this package) | Reproducible locally; E2A already measured the tool-echo failure at this code lineage | Primary current-system comparator; historical E2D baseline `040c28c36d10a6c89144a19e01b0eae77a88ec64` is not substituted for B1 |
| **B2** | Provenance/naive-lineage comparator | TMA-NM `mem-inv-bench` `63f1359d677efbe1a65b982b2a54cabfec97f1e1`, its `lineage` branch | Reproducible as the authors' generic comparator; it is not MemLineage and does not run Custody | Include only where the external benchmark defines the same item/action interface; label as a stand-in |
| **B3** | TMA-NM | `yedidel/mem-inv-bench` `63f1359d677efbe1a65b982b2a54cabfec97f1e1`, MIT | Offline formal checks reproduced; model-backed benchmark requires OpenRouter and remains unrerun. The pinned synthetic `tool_echo` helper materializes and reads `true_origin`; classify this Gate 1 reference **B3-ORACLE-COUPLED** | Run the official model-free decision path exactly as published and label it a native benchmark/oracle-coupled reference; do not present it as an equal-observation comparator or author-reported LLM replication |
| **B4** | MemLineage | Published design arXiv 2605.14421; independent implementation `amurlaniakea/memlineage` `73e770478f044323052a402795690c9d4e62f804`, AGPL-3.0 | Not yet reproduced; independent implementation is not the official paper artifact | Feasibility candidate only; exclude from primary comparison until build/run and license scope are independently verified |
| **B5** | SMSR | arXiv 2606.12703; no pinned public implementation found | Blocked for quantitative reproduction | Paper context only until an official artifact is available; never use a hand-built HMAC/voting approximation |
| **B6** | Architecture A | E2G execution lineage at `bd0fcd3af38b105f326dbe0e4f73149b6da67449`, selected G3; logical prototype only | Deterministic logical harness reproduced; no external benchmark adapter or production implementation exists | Future adapter target. A logical PASS is not an external benchmark result |

## Reproduction rules

1. Pin every source to a commit or immutable release before execution. A
   moving `main` branch is not a reproducible baseline.
2. Record license, Python/runtime requirements, model/API requirements, and
   the exact command. A missing key, inaccessible dataset, or incompatible
   license is `blocked`, not a substitute baseline.
3. Run the benchmark's own no-defense and benign controls before inserting
   B1 or B6. If the external fixture cannot execute without changing its
   published security question, mark that cell `not comparable`.
4. Do not copy TMA-NM's synthetic `true_origin` or any expected answer into
   B0, B1, B2, or B6. The official B3 reference may consume its own native
   origin metadata only through the pinned TMA-NM path and must be labelled
   oracle-coupled for this fixture; the field is not a shared scorer input.
5. Treat every baseline's runtime interface as an explicit allowlist. A
   native field is permitted only when the baseline's published/frozen
   mechanism declares its producer and trust assumption. A field populated
   solely from scorer truth is forbidden to that baseline.
6. Do not score B3's author-reported LLM tables as an independent replication;
   the locally reproduced TLA+/monitor checks are separate evidence.
7. Do not build B4 or B5 approximations to fill a missing repository. Their
   absence is a result of the reproducibility audit.

## Model and cost feasibility

| Baseline/family | Model calls in first gate | Later model requirement | Cost status |
|---|---:|---|---|
| B0/B1/B2/B6 on TMA tool-echo fixture | 0 | None for the fixed deterministic action adapter | Expected `$0` |
| B3 TMA-NM full empirical suite | 0 in offline subset | OpenRouter models and API key for benchmark scripts | Not authorized; cap must be set in a future run plan |
| MPBench target-agent evaluation | 0 for dataset inspection | Depends on the chosen fixed victim/model harness | Not yet scored |
| Sleeper repository | 0 for dataset/smoke inspection | Provider credentials for tool-based/external-manager regimes; Python 3.11+ and `uv` | Not yet scored |
| MemSecBench | 0 until a public artifact is pinned | Three LLM backends in the paper's matrix, exact IDs not yet available | Blocked pending artifact |
| B4 MemLineage | 0 for source inspection | Repository-specific local/model requirements must be audited before use | Not yet scored |
| B5 SMSR | 0 | Unknown until official artifact | Blocked |

The first external gate has a hard model/API ceiling of `$0`. No provider
credits are purchased or assumed. A model-backed benchmark phase requires a
new authorization or an explicitly pinned extension of this preregistration;
it may not silently follow the model-free gate.

## Native-interface and shared-observation eligibility

The primary Gate 1 table is a **NATIVE-INTERFACE COMPARATIVE SECURITY
EVALUATION**. It may include B0, B1, B2, B3's official offline decision logic,
and B6, provided the same externally authored `tool_echo` fixture is
executable for each native interface. B3 is retained as a faithful
native-benchmark/oracle-coupled reference because the official fixture's
`true_origin` is benchmark-materialized; this is disclosed rather than treated
as equal information.

An optional secondary shared-observation table may include B0, B1, B2, and B6
using only the canonical event projection. B3 is `NOT_APPLICABLE` in that
table, not reimplemented without its native monitor and not given scorer
labels. The complete field-level allowlists and provenance are in
`TMANM_RUNTIME_BOUNDARY.md`.

B4 and B5 are reported as
`UNAVAILABLE_REPRODUCTION`, not as zeros. This keeps a missing defense from
being mistaken for a weak defense and prevents a strawman comparison.

## Result artifact lineage

A future authorized run must retain, for every cell:

- source URL, commit, license, and source digest;
- fixture/data digest and unchanged external case identifier;
- baseline source digest and configuration digest;
- model/provider/temperature/seed, or `model_calls = 0`;
- native benchmark metrics plus the common action endpoint where available;
- exact raw numerator/denominator, failures, and exclusion reason;
- a canonical result digest and a separate scorer-only ground-truth digest.

The current package creates none of those run artifacts and performs no
benchmark execution.
