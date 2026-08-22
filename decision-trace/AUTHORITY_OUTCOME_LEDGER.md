# Authority benchmark outcome ledger

| Decision | Evidence | Acceptance gate | Result | Next action / kill condition |
|---|---|---|---|---|
| Close rationale recall | `RESULTS_V2.md`: 72/83 structured vs 74/83 RAG | Do not tune or restore old claim | Closed negative result | Never reuse 76% vs 57% |
| Test current organizational authority | `AUTHORITY_BENCHMARK_SPEC.md`, 15 timelines / 61 checkpoints | DT baseline >= RAG +10 points plus error/CI gates | Failed: 47/61 vs 52/61 | Do not claim baseline advantage |
| Preserve negative baseline | Commit `0db0305`, prompt hashes, 122-call manifest | No selective reruns | Passed | Baseline remains headline |
| Try one authority resolver | `AUTHORITY_INTERVENTION.md`, `app/authority.py` | Rescue >=8/14, gain >=8 points, zero regression/gate failure | Passed engineering gate: 61/61, 14/14 rescued | Prospectively replicate; kill claim if unseen set fails preregistered gate |
| Keep product frozen | Branch and Git evidence | No merge/push/deploy | Passed | Explicit authorization required for any integration |
| Ship intervention | APOSD hook + full real integration suite | Both must pass | Blocked/unshippable: reviewer session limit; suite not completed | Rerun after reviewer quota resets, then full Vertex/Firestore suite |
