# Gate 1B — Invalid Attempt 01 Preservation

Status: `INVALID_PRETREATMENT_RUNNER_FAILURE`. This record preserves the
pre-treatment runner failure and is not a security result.

## Lineage

- Parent Gate 1B design freeze: `cd75a059052229916980f1b992d48bd1e8c6eb9c`
- Execution branch: `research/external-gate1b-provenance-falsifier`
- Attempted runner: `research/external_eval/gate1b_provenance/execution/run.py`
- Runner SHA-256: `7e2bda867dc49fca99dce463cfd255d42c95b71444af05ccf3d8356a7ee72e81`

## Failure boundary

The runner failed while constructing the revocation fixture, before any
treatment or scorer execution. The exact exception was:

```text
ValueError: duplicate authoritative record: MEM-REVOKED-DESC
```

The duplicate record ID was `MEM-REVOKED-DESC`.

The first insertion is the explicit `state.add(revoked_descendant)` in the
revocation fixture block (`run.py:1257`). The second insertion is the
`state.add(record)` performed by the local `finish()` helper
(`run.py:1018`) when `finish("revoked_descendant", revoked_descendant, ...)`
is called (`run.py:1264–1268`). The intended canonical owner is one fixture
registration path; the existing attempt has both the revocation block and
`finish()` acting as owners.

## What did not happen

The failure occurred before treatment execution. No B1, B6, B3, or B6P2
result was produced; no benign, tool-echo, forgery/replay, transform,
multi-parent, generation, or revocation action was scored; and the scorer
never produced a result. No model/API call occurred. No Gate 1B security
verdict exists and no security conclusion is inferred here.

The execution directory contained only the attempted `run.py`; no
`result.json`, `RESULT.md`, or adapter audit was generated.

## Repository checks

- Production diff under `custody/`, `tests/`, `live/`, `scripts/`, `web/`, and
  `research/design/`: empty.
- Frozen test suite: `python -m unittest discover tests` — `381/381` passed.

## Preservation rule

This pre-treatment runner failure is preserved as immutable evidence. The
same Gate 1B experiment identity will not be patched and rerun. A separately
preregistered R1 may correct only fixture construction ownership and add a
pre-treatment uniqueness check; it must retain the attack, controls, security
semantics, metrics, denominators, and verdict/KILL gates unchanged. The
correction was selected without observing any treatment result.
