# Gate 1B-R2 Import Contract

This contract is the sole R2 correction. It is evaluated before fixture
construction, defenses, actions, or scorer access.

## Launch invariant

The launcher must resolve the repository root from Git, change to it, and make
that exact directory an explicit import root before starting Python:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  PYTHONDONTWRITEBYTECODE=1 \
  ./.venv/bin/python \
  research/external_eval/gate1b_r2_provenance/execution/run.py
```

The exact R2 runner path is fixed by the R2 branch. The invariant is explicit
repository-root import resolution before Python starts. Do not rely on the
ambient working directory/PYTHONPATH, install globally, modify site-packages,
or append arbitrary parent directories. Do not add an experiment-specific
`sys.path.insert(...)` if this launcher contract works.

## Import-only preflight

From the same resolved root and virtual environment, before any fixture or
result path is touched, run an import-only process:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  PYTHONDONTWRITEBYTECODE=1 \
  ./.venv/bin/python - <<'PY'
import custody
from custody.action import Export, ExportGateway
from custody.graph import CustodyGraph
from custody.origin import ToolTrust, take_custody

assert custody is not None
assert Export is not None
assert ExportGateway is not None
assert CustodyGraph is not None
assert ToolTrust is not None
assert take_custody is not None
print("IMPORT_PREFLIGHT=PASS")
PY
```

The process must create no fixture, execute no defense/action, read no scorer,
and write no result. `PYTHONDONTWRITEBYTECODE=1` prevents import diagnostics
from dirtying the repository or pinned external checkout.

Required outcome is exactly `IMPORT_PREFLIGHT=PASS`. Any import error is
`INVALID` and stops R2 before treatment.

## Root-cause evidence

R1 ran `python research/.../run.py` with repository CWD but no explicit
`PYTHONPATH`. For a filesystem-path script, Python uses the script directory as
the initial script import location; CWD is not a guaranteed package import
root. The package is at `<repo>/custody/__init__.py`, while the R1 script is
under `<repo>/research/external_eval/gate1b_r1_provenance/execution/`. R2
resolves this boundary at the launcher rather than changing Custody.

## Post-import gates

After import preflight passes, R2 must still verify the pinned external source,
the scorer/runtime boundary, issuer key separation, no `true_origin` in B6 or
B6P2, no payload-semantic/case-label security branch, 27 unique fixture IDs,
27 insertions, `MEM-REVOKED-DESC == 1`, and model calls zero before treatment.
