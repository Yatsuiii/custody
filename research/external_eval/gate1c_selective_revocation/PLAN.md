# Gate 1C — Selective Receipt Revocation

Status: design and preregistration only. No runner, prototype, or production
change is authorized by this document.

## Identity and lineage

- Experiment family: `GATE1C_SELECTIVE_RECEIPT_REVOCATION`
- Proposed experiment identity: `EXT_GATE1C_SELECTIVE_RECEIPT_REVOCATION`
- Parent R3 preregistration: `8822dae5fda2566d24e0d4115173d360df722eec`
- Frozen R3 execution: `f3eb51cbdd52eca0f30f9989311f944b5ee50c35`
- R3 result: `COMPOSITION-FAILS`
- First failed gate: `REVOCATION_COLLATERAL`

Gate 1B-R3 remains valid evidence and is immutable. Gate 1C is a new design
question created by failure localization, not a rerun or repair of R3.

## Baseline and hypothesis

**Baseline:** R3's issuer-wide selector R0, which stores
`revoked_issuers = {issuer_id}` and checks that set before root-specific
receipt fields.

**Hypothesis:** the R3 collateral failure is caused by selector granularity,
not by missing receipt fields or missing support closure. Replacing only the
revocation selector with an authenticated root-bound selector can deny every
descendant that requires a compromised root while retaining unrelated,
pre-compromise, and post-remediation authority.

**Single changed variable:** revocation selector granularity. Receipt schema,
issuer, signature, attack, transformations, generation rules, parentage,
scorer, action, and authority meet remain frozen.

## Candidate semantics

The selected minimum is R3 receipt-root-bound revocation. A root selector is
formed from existing authenticated and durable fields:

```text
RootKey = (
    issuer_id,
    receipt_id,
    upstream_record_id,
    upstream_object_commitment,
    PolicyKey,
    granting_generation,
    root_record_id,
)
```

No new receipt field is proposed. The verifier first authenticates the receipt
and resolves its immutable root record; the dependency closure retains the
`receipt_id` and `root_record_id` needed to match a revocation selector. A
bounded compromise interval is a frozen set of authenticated RootKeys (R4),
not a broad issuer or PolicyKey deny-list.

The action rule is:

```text
ALLOW only if every required authority-bearing support path resolves to a
currently valid authenticated root and every required transform/policy
dependency is current.
```

If one required parent is revoked or unresolved, a clean sibling cannot wash it.
If an action is explicitly defined to depend only on a clean parent, that
dependency must be represented structurally rather than inferred at evaluation
time.

## Bounded-compromise fixture

The future falsifier must include one issuer/source with authenticated roots:

```text
R_PRE   legitimate before compromise
R_BAD_1 compromised during the bounded interval
R_BAD_2 compromised during the bounded interval
R_POST  legitimate after remediation
```

Derived records are:

```text
D_PRE   <- R_PRE
D_BAD1  <- R_BAD_1
D_BAD2  <- R_BAD_2
D_POST  <- R_POST
D_MIX   <- R_BAD_1 + unrelated clean root
```

The selector covers exactly `R_BAD_1` and `R_BAD_2`. Required results are
`D_BAD1 DENY`, `D_BAD2 DENY`, and `D_MIX DENY` when both supports are required;
`D_PRE ALLOW`, `D_POST ALLOW`, and unrelated-root `ALLOW`. Historical evidence
must not change.

## Data-system invariants (DDIA review)

1. Receipts, records, parentage, support roots, and dependencies are immutable
   evidence; revocation state is a separate current control-plane fact.
2. The action read must use authoritative selector state and the complete
   support closure; a stale cache cannot restore ACT.
3. Selector activation is append-only/idempotent and keyed by authenticated
   roots, not self-declared labels or payload text.
4. Derived records retain every required root dependency across REGISTERED,
   cross-agent, and multi-parent paths; dropping a dependency is an escape.
5. Duplicate selector activation and replay are harmless; historical records
   are never rewritten to achieve collateral metrics.
6. A future implementation must specify reverse-closure indexing, freshness,
   and concurrent revocation/action ordering before it is architecturally
   shippable.

The smallest proof artifact is a deterministic two-run trace containing root
keys, closure decisions, selector matches, action outcomes, and immutable
snapshot hashes.

## Prior-art and design verdict

The root-bound selector is known-style scoped revocation; it is not claimed as
novel. The R3 trace demonstrates that the existing selector is too coarse and
that P2 already carries enough identity to attempt a selective test.

**Design verdict: `SELECTOR-TOO-COARSE`.**

This verdict is a diagnosis, not evidence that a selective implementation will
pass.

## Cheapest Gate 1C falsifier (not authorized to run)

Reuse the frozen Gate 1B/R3 receipt graph, benign/tool-echo world, action path,
and model-free boundary. Compare:

- R0 current issuer-wide revocation (negative control); and
- R3 root-bound selector with the same immutable records and dependencies.

Add only the bounded-compromise roots and the required clean sibling,
pre-compromise, post-remediation, cross-agent, and escape controls above.
Run two clean deterministic executions. No content inspection, scorer truth,
model calls, or production writes are permitted.

## Acceptance gates and kill rule

The future candidate passes only when all are true:

- affected revoked descendants false ACT = `0/N` and affected recall = `100%`;
- unrelated receipt-backed utility = `100%`;
- pre-compromise and post-remediation utility = `100%`;
- mixed revoked/clean dependencies cannot wash revocation;
- cross-agent forwarding cannot escape revocation;
- historical rewrites = `0`;
- normalized traces reproduce.

KILL the selective-revocation thesis if a valid run either permits ACT for an
affected descendant or shows that preserving unrelated legitimate authority
necessarily preserves ACT for a compromised descendant under the same trust
boundary. Any failed utility/selectivity gate is `SELECTIVE-REVOCATION-FAIL`,
not a partial pass.

No MPBench authorization follows from this design phase.
