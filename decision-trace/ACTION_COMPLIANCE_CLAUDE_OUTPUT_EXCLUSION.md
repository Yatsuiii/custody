# Claude pilot output exclusion

**HARNESS/PILOT ONLY — EXCLUDED FROM FINAL DATASET**

This notice covers every prior Claude coding-agent artifact found before the
Codex migration:

- `data/runs_action_compliance_pilot/task-01-k8s-postfilter-victims/`
- `data/action_compliance/cost_pilot/`

Those directories remain available for audit and harness diagnosis. They are
not comparative data and must not enter the final run plan, condition-blind
grader inputs, grading table, bootstrap input, cost comparison, or primary
analysis. The final statistical dataset is exactly 63 fresh Codex executions
from the seven frozen tasks, three arms, and three repetitions.

The frozen Arm B summary fixtures under
`data/action_compliance/summaries_claude/` are context inputs, not coding-agent
executions. Their bytes are retained as frozen summaries; their historical
Claude summarizer metadata does not make the excluded coding-agent pilot data
eligible for analysis.
