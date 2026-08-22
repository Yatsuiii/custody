# Gate 1B-R2 — Authority Receipt Runner-Lifecycle Correction

Status: preregistration/design only. R2 is not executed in this session.

## Identity and lineage

- Experiment ID: `EXT_GATE1B_R2_AUTHORITY_RECEIPT`
- Branch: `research/external-gate1b-r2-provenance-falsifier`
- Parent R1 preregistration: `14623a83c4cde647c365a71290e7964eed4a5479`
- Preserved R1 invalid attempt: `d339f10bb705191f50e9f9759b5d7f5341f34893`
- Parent Gate 1B design: `cd75a059052229916980f1b992d48bd1e8c6eb9c`
- Reason: `INVALID_RUNNER_IMPORT_LIFECYCLE` before any scored security result.

R1's 27-record fixture correction passed. R1 then began its first treatment
loop, performed only an unscored B0 local store/retrieve step, and failed when
B1 imported `custody` from a nested script invocation. R1 is preserved and
will not be patched or rerun.

## Single authorized R2 change

R2 changes only the Python launch/import lifecycle:

- determine the repository root explicitly;
- change to that root;
- put exactly that root on `PYTHONPATH` before Python starts;
- run the R2 runner with the frozen virtual environment and bytecode disabled;
- perform an import-only preflight before fixture construction or treatment.

No `custody/` package change, global installation, site-package modification,
ambient-PYTHONPATH dependency, or arbitrary parent-directory insertion is
permitted. A launcher-level correction is an execution-environment property,
not a treatment semantic.

## Frozen security experiment

All R1 security semantics remain identical:

- `yedidel/mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1`;
- `code/laundering.py::tool_echo` and the exact benign control;
- source-issued P2 receipt, issuer/relay separation, Ed25519 verification, and
  object binding;
- B1 Current Custody, B6 Architecture A, B6P2 Architecture A plus P2, and B3
  official oracle-coupled contextual reference;
- cases A–O, transformations, generation, multi-parent, revocation, scorer
  boundary, metrics, denominators, verdict/KILL gates, and model cost `0/$0`.

The R2 runner must still pass the R1 fixture gate before treatment:

```text
authoritative IDs = 27
unique IDs = 27
expected insertions = 27
MEM-REVOKED-DESC = 1
```

R2 begins fresh deterministic runtime state and never imports or resumes R1
state. B0's partial R1 local operation is not evidence.

## Required pre-treatment order

1. verify the dynamically discovered R2 preregistration commit, branch, and
   remote SHA;
2. verify production diff is empty and the external source is pinned;
3. execute the import-only preflight specified in `IMPORT_CONTRACT.md`;
4. verify scorer isolation, issuer/relay key separation, no `true_origin` in
   B6/B6P2, no payload-semantic/case-label branch, and model calls zero;
5. run the 27/27 fixture dry-run and require `MEM-REVOKED-DESC == 1`;
6. only then execute cases A–O.

Any failed pre-treatment gate is `INVALID` and stops before treatment.

## No execution in this session

R2 creates no runner, result, RESULT.md, or adapter audit here. A future
authorization must not patch R1 or change P2/Architecture A after any result.
