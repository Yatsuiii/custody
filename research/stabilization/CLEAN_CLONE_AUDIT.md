# Clean-clone audit

Status: PASS for repository startup and offline verification on
2026-08-24, using clean clone /tmp/custody-clean-clone at commit
9b962c34011a25631ef01481b820560c286deb5b.

The clean-clone gate must use documented commands only and must verify:

- package import without a manually exported PYTHONPATH;
- the full local suite against the clean checkout;
- scripts/run_firestore_contract_probe.py --help startup;
- explicit configuration errors rather than silent process exit;
- artifact directory creation and terminal-state validation.

The current test suite has one environment-sensitive Git call in the local B7
equivalence report; it is being changed to pass an explicit safe-directory
configuration to Git. This avoids changing the security mechanism and makes
the evidence reporter work in isolated worktrees as well as normal clones.

Recorded results:

- package import resolved to `/tmp/custody-clean-clone/custody/__init__.py`;
- the full local suite completed `484 tests, 0 failures, 0 errors`;
- the Firestore probe supervisor printed its usage and resolved its own
  repository root without a manually exported PYTHONPATH;
- no stale proof artifact was required for startup.

The real networked contract probe is a separate gate and remains unproven
until its terminal artifact exists.
