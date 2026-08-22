# External Attack Coverage Matrix

This matrix is a preregistration map, not a result table. `planned` means a
cell is eligible for a future authorized run; `measured` is an earlier result
and is not silently re-used as a matched baseline; `logical` is internal
model evidence only; `blocked` means the external artifact is unavailable;
`not-representable` means the baseline's data model cannot express the case;
`gap` means no audited external source currently supplies the case.

| External attack / lifecycle family | External source | B0 no defense | B1 current Custody | B2 naive lineage | B3 TMA-NM (native/oracle-coupled reference) | B4 MemLineage | B5 SMSR | B6 Architecture A |
|---|---|---|---|---|---|---|---|---|
| Direct poisoning | MPBench H/I; Sleeper released goals | planned | planned | planned where interface fits | planned for TMA H | candidate | blocked | planned |
| Indirect poisoning through documents/tools | MPBench six classes; Sleeper tool regime | planned | planned | planned | planned | candidate | blocked | planned |
| Trusted-tool echo | TMA-NM channel C at `63f1359` | planned | **measured fail in E2A**; matched rerun required | planned/source comparator | source attack; offline logic reproduced, LLM ASR not rerun | candidate | blocked | planned external adapter |
| Summarization laundering | TMA-NM channel A | planned | **measured accidental block in E2B**; not a defense result | planned/source comparator | source attack; no independent model run | candidate | blocked | planned |
| Paraphrase laundering | TMA-NM channel B; E2C mechanism probe | planned | measured exact-hash cliff in E2C | planned/source comparator | source attack; no independent model run | candidate | blocked | planned |
| Delayed/sleeper activation | TMA-NM I; Sleeper IR/RR/AUR | planned | not externally benchmarked | not the published comparator | TMA I source | candidate | blocked | planned |
| Multi-source derivation | No audited external attack corpus currently supplies this | gap | E1 real code pass; not external benchmark | not-representable in TMA item model | not-representable in TMA item model | candidate only | blocked | E2G logical pass; external gap |
| Cross-agent propagation | No audited benchmark supplies a scored multi-agent memory graph | gap | gap | gap | not present | candidate | blocked | E2G logical depth-3 only |
| Consequential action | MemSecBench Execute; MPBench retrieval/action goals; Sleeper AUR | planned | planned | planned where action API exists | planned for action-capable cells | candidate | blocked | planned |
| Selective repair / Forget | MemSecBench Write→Execute→Forget | blocked pending artifact | blocked pending artifact | blocked pending artifact | no repair stage | no repair stage | no repair stage | blocked pending artifact |
| Post-hoc source compromise | No external benchmark audited with this temporal sequence | gap | E2E/E2G logical only | no | no | no | no | E2D/E2G logical; E2H persistence only |
| Benign utility / collateral | MemSecBench matched Native; MPBench benign cases; Sleeper benign-save | planned | planned | planned | native utility where supported | candidate | paper-only | planned |

## Coverage decisions

Gate 1 uses two explicitly labelled views of the same external case:

* **Table A — native-interface comparison:** B0, B1, B2, B3, and B6. Each
  defense receives only its declared runtime interface. B3 is retained as the
  official native benchmark/oracle-coupled reference because the pinned
  `tool_echo` fixture materializes `true_origin` and the official helper reads
  it. This is not an equal-information claim.
* **Table B — shared-observation diagnostic:** B0, B1, B2, and B6 only, using
  the canonical event observation. B3 is `NOT_APPLICABLE` here rather than
  crippled or given a scorer field. Table B is diagnostic and does not replace
  the primary native-interface gate.

The full field provenance, allowlists, and source-line audit are frozen in
`TMANM_RUNTIME_BOUNDARY.md`.

### Keep likely Architecture A failure cases

The first protocol must not remove the following because they are inconvenient:

- trusted-tool echo, even though E2A already identified the current Custody
  failure;
- summarization and paraphrase laundering, even though exact structural
  support may be unavailable to a benchmark adapter;
- delayed/sleeper activation, because a source can be benign at write time and
  harmful later;
- multi-source and cross-agent cases, even when TMA-NM cannot represent them;
- action consequence, not only poison storage or retrieval;
- selective repair and benign collateral, not only post-revocation blocking.

An unavailable external case is recorded as a gap or blocked cell. It is not
deleted from the research question and is not replaced by a self-authored
attack that happens to favor Architecture A.

## What the matrix does not say

The matrix contains no comparative result for B6. E2D/E2G logical passes do
not fill the external cells. Likewise E2A–E2C are historical adapters against
current Custody, not a claim that B0–B5 or Architecture A have now been
benchmarked. Quantitative comparison begins only after a source commit,
fixture digest, baseline configuration, and scorer contract are frozen.

## Gap test required before any Custody-specific extension

After the first external cells run, inspect whether the external benchmark
actually contains this sequence:

```text
legitimate source at t0
  -> propagation/derivation
  -> compromise discovered later in [ta, tb]
  -> historical authority withdrawal
  -> selective downstream repair
```

Only if that sequence is absent from the strongest reproducible external
families may a small Custody-specific extension be proposed. It must be an
addition to the external rows above, not the substitute benchmark.
