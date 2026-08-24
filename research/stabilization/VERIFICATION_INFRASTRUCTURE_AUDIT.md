# Verification-infrastructure audit

## Historical failures preserved

The previous real Firestore probe had two non-results:

1. a launcher import failure: ModuleNotFoundError: No module named custody;
2. a later invocation with no stdout, no result artifact, and no captured
   exception chain; read-only inspection found the eight scratch collections
   empty.

Neither is a PASS, a security result, or a P7 result.

## Hardened path

scripts/run_firestore_contract_probe.py now supervises
scripts/firestore_contract_probe.py and:

- writes a start artifact before spawning the networked child;
- records Python executable/version, sys.path, package path, repository SHA,
  branch, remote SHA, and installed SDK versions;
- uses the repository root rather than a caller-provided PYTHONPATH;
- imposes a finite timeout;
- captures stdout, stderr, exit status, timeout, and child result path;
- requires a child artifact with exactly PASS, FAIL, or BLOCKED;
- converts missing, malformed, silent, nonterminal, or zero-exit-without-PASS
  outcomes to PROBE-HARNESS-FAIL;
- writes terminal results atomically and preserves cleanup separately.

Offline harness tests cover the artifact and process-failure branches. The
clean-clone launch passed, and the stab01 real non-security probe passed 19/19
operations with cleanup verified. The earlier silent and import-failure
attempts remain immutable invalid evidence.
