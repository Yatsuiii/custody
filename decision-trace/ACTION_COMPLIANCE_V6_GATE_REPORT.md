# Action-Compliance V6 Gate Report

## Result

V6 model-free gates pass. No V6 coding-model or comparative statistical call
has been made in the managed Codex session.

## Verified gates

- shared interpreter/grader classifier regression: 13/13 cases pass;
- task contracts: 7/7, contract version `test-command-v2`;
- sanity replay: 14/14 cases, zero model calls, parseable graders, real tests
  executed, expected compliant/violating authority outcomes, clean resets;
- crash/recovery: pass, including stale-slot recovery and live-slot
  protection;
- storage stress: 63/63 cycles pass at two workers, zero model calls, zero
  residual worktrees, approximately 99 KiB net residual growth;
- contract-strengthened orchestration dry run at
  `data/action_compliance/v6_dry_run_host_contract_v2/`: 63/63 rows, three arms, three
  21-row rounds, fresh opaque IDs, exact contract commands, zero model calls;
- authority freeze: 9/9;
- raw A/B/C parity: 7/7 equal raw prefixes;
- neutral bundle verification: 7/7 task bundles, three artifacts each;
- V6 manifest: all listed files self-verify.

## Boundary condition

The managed parent session has a restricted network namespace and reports DNS
failure for the Codex provider. Therefore the V6 excluded-fixture Codex
preflight has not been run here. The V6 host runner rejects this environment
for `--preflight` and `--execute` before launching a child. Run those modes
from a normal host shell so the child inherits host provider access.

The host runner must recheck the installed CLI version, provider reachability,
disk guards, and `CODEX_HOME` immediately before the excluded preflight. The
statistical V6 dataset remains empty until that preflight passes.

## Exclusions

All Claude, V1, V2, V3, V4, and V5 outputs remain excluded. V5 was model-free
only; V6 uses fresh run IDs and does not read prior result rows or condition
maps.
