# Gate 1B-R1 — Invalid Attempt 01 Preservation

Status: `INVALID_RUNNER_IMPORT_LIFECYCLE`. This preserves the attempted R1
runner and does not contain a security result.

## Lineage and runner evidence

- R1 preregistration: `14623a83c4cde647c365a71290e7964eed4a5479`
- Branch: `research/external-gate1b-r1-provenance-falsifier`
- Attempted runner: `research/external_eval/gate1b_r1_provenance/execution/run.py`
- Attempted runner SHA-256: `0cc3b6bdb940d8aa4e6cb484ec307bcaad28445349d51866b55b6b7b9fb63321`
- Invocation:

  ```text
  GATE1B_PREREGISTRATION_SHA=14623a83c4cde647c365a71290e7964eed4a5479 \
  TMANM_SOURCE_DIR=/tmp/custody-gate1-tmanm-source \
  PYTHONDONTWRITEBYTECODE=1 \
  ./.venv/bin/python \
  research/external_eval/gate1b_r1_provenance/execution/run.py
  ```

## Boundary reached

The R1 fixture dry-run passed before treatment:

```text
authoritative IDs = 27
unique IDs = 27
expected insertions = 27
MEM-REVOKED-DESC = 1
```

The first treatment loop began. B0 completed its local in-memory store/retrieve
step for the benign case, but it was not scored. B1 setup then failed while
importing the frozen production package:

```text
from custody.action import Export, ExportGateway
ModuleNotFoundError: No module named 'custody'
```

No B0 scored result exists. No B1, B3, B6, or B6P2 result exists. No tool_echo,
receipt-control, transformation, multi-parent, generation, or revocation case
was scored. Scorer reads were `0`; no security verdict was produced; no
model/API call occurred.

## Root cause

The process current working directory was the repository root:

```text
/run/media/Yatsuiii/Windows-SSD/custody
```

The package is located at:

```text
/run/media/Yatsuiii/Windows-SSD/custody/custody/__init__.py
/run/media/Yatsuiii/Windows-SSD/custody/custody/action.py
```

The runner was invoked by nested filesystem pathname. Python therefore used the
runner's directory as the script import location and did not implicitly add the
repository root to `sys.path`. Ambient `PYTHONPATH` was empty. The production
package layout was unchanged; the failure is solely an import-launch lifecycle
failure. R2 must make the repository root an explicit import root before Python
starts.

## Integrity and interpretation

- Scorer/security result: none.
- Model/API cost: `$0`.
- Production diff under `custody/`, `tests/`, `live/`, `scripts/`, `web/`, and
  `research/design/`: empty.
- Frozen suite: `python -m unittest discover tests` — `381/381` passed.

This is not `COMPOSITION-SUPPORTED`, `COMPOSITION-FAILS`, `NO-UTILITY-GAIN`,
or `KILL`. R1 will not be patched or rerun. The attempted `run.py` remains
untracked evidence and is not an execution result.
