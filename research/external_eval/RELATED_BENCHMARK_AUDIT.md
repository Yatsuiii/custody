# Related Benchmark and Attack Audit

Audit date: 2026-08-22. The audit uses primary papers and the authors' or
maintainers' repositories. A paper claim is not treated as an independently
reproduced result. A repository is not treated as an official artifact unless
the paper or repository itself establishes that relationship.

## Primary records

| Family | Pinned primary source | What it measures | Runnable/reproducibility status | Compatibility with Custody |
|---|---|---|---|---|
| **MemSecBench** | [arXiv 2607.27080](https://arxiv.org/abs/2607.27080), v1 submitted 2026-07-29 | 310 cases from 48 contexts; Write→Execute→Forget; 2 harnesses × 4 memory backends × 3 LLM backends; persistence, downstream consequence, selective repair | The paper's abstract and arXiv page expose no public repository/data URL. No code commit, license, or local run is verified; quantitative use is **blocked pending artifact release/access** | Closest lifecycle fit: it has a real execute consequence and a Forget/repair stage. It lacks bounded compromise intervals, first-class derivation graphs, and explicit authority/content separation |
| **MPBench** | [arXiv 2606.04329](https://arxiv.org/abs/2606.04329); [Apache-2.0 dataset repository](https://github.com/Digital-Trust-Lab/mp-bench) at `6886880a7c29625e0109e0ad91d0e095029f1577` | Six attack classes, benign controls, seven domains; write Attack Success Rate and later Retrieval Success Rate | Dataset is public, JSONL-shaped, Apache-2.0, and can be consumed without model calls. A target agent is still needed to score writes/retrieval; no official Forget/revocation harness is present | Good external write/retrieve coverage; not a revocation or lineage benchmark |
| **Hidden in Memory / Sleeper** | [arXiv 2605.15338](https://arxiv.org/abs/2605.15338); [public evaluation repository](https://github.com/ivaxi0s/LLM-agent-memory-poisoning) at `70de017714abd6d12bb4681e93437461ba6f9a19` | Dormant memory poisoning: Injection Rate (IR), Retrieval Rate (RR), Adversarial Usage Rate (AUR), goal-adjacent and goal-distant queries; tool-based and simulated external-manager regimes | Source datasets and smoke configs are present. Repository license is not declared by GitHub metadata. Python 3.11/`uv` and provider credentials are required for model runs; a no-cost model-free security run is not available | Strong delayed-trigger attack generator. It does not measure source compromise, revocation, lineage, or selective repair |
| **Plant, Persist, Trigger** | [arXiv 2605.28201](https://arxiv.org/abs/2605.28201); paper-linked anonymous artifact `https://anonymous.4open.science/r/skdvnfu23ihr9wdscnksf1asdffsaef` | 1,896 instances, six harmful outcomes, three attack strategies, and session/memory/skills state targets | The anonymous artifact was not accessible during this audit; license, commit, data integrity, and run instructions are therefore unknown. Exclude from quantitative comparison until independently verified | Useful attack taxonomy for sleeper activation, not a defense/revocation benchmark |
| **TMA-NM / mem-inv-bench** | [arXiv 2606.24322](https://arxiv.org/abs/2606.24322); [MIT repository](https://github.com/yedidel/mem-inv-bench) pinned at `63f1359d677efbe1a65b982b2a54cabfec97f1e1` | Summarization, paraphrase, trusted-tool echo, manufactured corroboration, direct/indirect poisoning, and delayed activation; authority laundering success; offline TLA+/monitor checks | Repository is real and MIT. Offline `test_monitor.py` and `check_invariant.py` reproduced locally with no cost. LLM benchmark scripts need `OPENROUTER_API_KEY`; published LLM numbers were not independently rerun. Six attack classes are implemented; cross-agent relay and mixed-source derived memory are absent, and the flat `MemoryItem` model cannot represent a multi-parent derivation | Best cheap source for a published attack construction and tool-echo/paraphrase laundering. It is write-time/static and has no retroactive revocation. For Gate 1, the synthetic `tool_echo` fixture materializes `true_origin` and the official helper reads it; classify B3 **B3-ORACLE-COUPLED**, not equal-observation. See `TMANM_RUNTIME_BOUNDARY.md` |
| **MemLineage** | [arXiv 2605.14421](https://arxiv.org/abs/2605.14421); no official paper artifact was found in the paper audit. Independent implementation: [amurlaniakea/memlineage](https://github.com/amurlaniakea/memlineage) at `73e770478f044323052a402795690c9d4e62f804`, AGPL-3.0 | Ed25519 origin binding, Merkle log, weighted derivation DAG, and action gating; published ASR/overhead claims | The GitHub project explicitly describes itself as an independent engineering implementation of the paper and is AGPL-3.0. It is not evidence that the paper's authors' artifact is reproducible; this project has not run it. Treat as a candidate separate baseline, not as an official paper result | Architecturally adjacent to derivation/dependency tracking; no bounded-interval revocation or post-hoc repair is described |
| **SMSR** | [arXiv 2606.12703](https://arxiv.org/abs/2606.12703) | HMAC-signed writes plus randomized retrieval ablation/majority certificate; unsigned and authenticated-adversary ASR; clean-query utility | No author repository or runnable artifact was located in the primary-source audit. Code/data/commit/license are unknown; quantitative baseline is blocked | Different defense class: write authenticity and statistical robustness, not derivation or revocation |
| **MemPoison** | [arXiv 2607.14651](https://arxiv.org/abs/2607.14651) | Triggerable memory backdoors, selective-memory bypass, and embedding-space attack success | No primary runnable implementation was located in this audit; exclude until a pinned artifact is found | Attack generator candidate for trigger/embedding laundering, not a repair benchmark |
| **MemMorph / MemoryGraft / Trojan Hippo** | [MemMorph arXiv 2605.26154](https://arxiv.org/abs/2605.26154); TMA-NM cites MemoryGraft and Trojan Hippo as attack pipelines | Tool hijacking, persistent compromise, and conversational/backdoor poisoning | TMA-NM contains references and some transcribed channels, but no independently pinned full attack artifacts were added to this evaluation set | Keep as provenance for attack families; do not claim direct reproduction without a source checkout |

## Primary-source observations

1. MemSecBench is the closest external lifecycle measurement because its
   Write→Execute→Forget protocol measures consequence and repair on the same
   case. Its missing public artifact is a reproducibility blocker, not a
   license assumption.
2. MPBench is the most accessible public dataset, but it stops before
   Forget. It can test whether a write/retrieve adapter changes attack
   success; it cannot answer the Custody interval-revocation question.
3. TMA-NM is the cheapest runnable source for a consequential authority
   attack. Its official formal checks are reproducible, while its model
   numbers remain author-reported in this workspace. Its `lineage` comparator
   is a generic stand-in, not MemLineage or Custody code. The paper explicitly
   assumes an authenticated origin-labeling monitor (Assumption A1), while the
   pinned synthetic `tool_echo` path also stores `true_origin` as ground truth
   and reads it in the official helper. Gate 1 therefore reports B3 as a
   native benchmark/oracle-coupled reference rather than an equal-information
   comparator.
4. Sleeper is a strong delayed-trigger attack source but model/API dependent.
   It reports IR/RR/AUR, so any adaptation must retain those native metrics
   rather than replacing them with a Custody-only score.
5. MemLineage and SMSR cannot be used as quantitative baselines until their
   artifacts and licenses are independently pinned. A paper-only baseline is
   reported as unavailable, never replaced by a friendly approximation.

## External benchmark gap

No audited external benchmark combines all of the following in one scored
case: a source legitimately trusted at `t0`; propagation through transformed
or cross-agent memory; discovery of compromise only in a bounded interval;
historical authority withdrawal; and selective downstream repair with benign
memory preserved. MemSecBench supplies the lifecycle/repair axis but not the
bounded interval or first-class dependency graph. TMA-NM supplies laundering
attacks but not later compromise or repair. This gap is recorded as a
limitation, not permission to replace the external benchmark with a new
self-authored suite. Any future Custody-specific extension must be a small
addition after the external mapping is run.

## Cost and access notes

- The first gate can use the pinned TMA-NM `tool_echo` fixture without an LLM
  call; expected model/API cost is `$0`. This remains a native-interface
  reference evaluation; TMA-NM origin metadata is not copied into the other
  baselines.
- TMA-NM's full model sweep needs OpenRouter credentials; no key or spend is
  assumed here.
- Sleeper and MemSecBench model-backed runs require provider credentials and
  exact model IDs; those runs remain a separately authorized phase.
- Repository access and artifact inspection do not authorize deployment,
  production data access, or changes to Custody.
