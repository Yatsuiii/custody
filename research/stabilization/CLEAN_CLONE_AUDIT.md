# Clean-clone audit

Status at baseline: pending.

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

No clean-clone PASS is claimed until the commands and outputs are recorded.

