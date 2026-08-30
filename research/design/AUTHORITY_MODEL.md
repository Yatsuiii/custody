# Authority Model

This is the canonical authority algebra for Architecture A. Other design
documents reference it rather than redefining authority locally.

## Values and ordering

For each configured `ActionScope` (for example `export.send`), a record has one
of three tiers:

```
NONE < INFORM < ACT
```

- `NONE`: retained only in the provenance/quarantine ledger; never placed in
  active memory context and never authorizes an action.
- `INFORM`: may be surfaced as data with provenance, but never authorizes a
  consequential action.
- `ACT`: may authorize the named action scope, subject to the action gateway.

An absent scope is `NONE`. Adding a new action type therefore cannot inherit
authority accidentally.

Authority is not a scalar:

```
Authority(M) = (Caps(M), Support(M))
Caps(M)      : ActionScope -> Tier
Support(M)   : set[RootRef]
```

`RootRef` identifies an immutable root contributor by record id, department or
principal boundary, source tool/operation, optional revision, and authoritative
admission time. `Support` is a logical transitive closure over direct
`derived_from` edges. The direct edges are the source of truth; an expanded
support set may be cached, but is not a second independently mutable lineage
store.

The distinguished `UNKNOWN_CONTEXT` root represents input that the receipt
collector could not account for. Its cap is at most `INFORM` in every scope.
It can never disappear merely because later code learns about the other inputs.

## Root binding

A root has no declared stored-record parents. Its cap is bound once by the
admission policy; text does not participate.

| Root kind | Cap rule | Support |
|---|---|---|
| Attributable user/principal | Explicit per-principal, per-scope policy; unspecified scopes are `INFORM` | `{self}` |
| Clean model output with no inputs | `INFORM` in every scope; a model is not an authority oracle | `{self}` |
| Vouched `ORIGIN` tool operation | Pointwise policy cap for that source and operation | `{self}` |
| Unvouched tool or invalid metadata | `NONE` | `{self}` |
| `RELAY` output with no observable upstream record | At most `INFORM` and includes `UNKNOWN_CONTEXT` | `{self, UNKNOWN_CONTEXT}` |

`ORIGIN` versus `RELAY` is operation-level, not just a tool-name flag; the
rules and mixed-operation fallback are in `TOOL_RELAY_MODEL.md`.

## Ordinary derivation

For an output `M` with a complete structural receipt naming declared parents
`P1, ..., Pn` and transformation class `K`:

```
Caps(M)[s] = min(TransformCap(K)[s], Caps(P1)[s], ..., Caps(Pn)[s])
Support(M) = union(Support(P1), ..., Support(Pn))
```

The minimum is the lattice meet under `NONE < INFORM < ACT`. Duplicate parents
are removed by record id. Parent order is irrelevant.

`TransformCap` is policy owned by the admission gate:

- `IDENTITY`: may preserve `ACT` because the referenced record itself remains
  the action citation.
- `REGISTERED`: a deterministic typed transform receives an explicit per-scope
  cap no higher than its contract permits.
- `FREEFORM`: capped at `INFORM`; structural ancestry does not prove that a
  paraphrase, summary, or model generation is semantically faithful.
- `INCOMPLETE`: capped at `INFORM` and adds `UNKNOWN_CONTEXT` to support.

If any parent is `NONE` in a scope, the output is `NONE` in that scope. If a
receipt is missing, malformed, names a missing parent, silently truncates a
manifest, or claims impossible causal order, the output uses `INCOMPLETE`; it
does not fall back to a fresh trusted root.

This rule is deterministic and proves I1 pointwise: a meet cannot exceed any
operand. It also preserves ancestry across byte changes without claiming that
the changed bytes are entailed by their parents.

## Effective authority after revocation

Bound authority is immutable. An active compromise window changes effective
authority, not the historical record:

```
Affected(M, W) = Support(M) intersects Roots(W)

EffectiveCaps(M, W)[s] =
    NONE       if Affected(M, W)
    Caps(M)[s] otherwise
```

For several active windows, `Affected` is the union. A record that intersects
an active window is ineffective in every action scope until it is deleted or
superseded by a new record. The implementation must not remove a compromised
root from `Support(M)` and meet the survivors: that could raise unchanged
content. `REPAIR_SEMANTICS.md` specifies replacement-only restoration.

## Required worked cases

### One `NONE` parent and one `ACT` parent

For any scope `s`, `min(NONE, ACT, TransformCap) = NONE`. The output retains
both parents in support and cannot authorize `s`.

### Two trusted parents

For a registered transform whose cap is `ACT`, two parents that are both `ACT`
for `s` yield `ACT` for `s`; support is the union of both root closures. For a
free-form synthesis, the same parents yield `INFORM`, because provenance alone
does not verify the generated proposition.

### Independent corroboration of a low-tier claim

Ordinary derivation performs no elevation. If the claim itself or any declared
parent is `NONE`/`INFORM`, combining two independent witnesses does not raise
it. A future `elevate` operator would be a separate mechanism with its own
falsifier; it is not part of this design.

### Correlated corroboration

The result is identical to independent corroboration in the core design: no
elevation occurs. This deliberately avoids treating two principals on one
compromise domain as independent merely because their ids differ.

### Action-type-dependent authority

Suppose a payroll source has:

```
payroll.read -> ACT
export.send  -> INFORM
```

An identity retrieval preserves those two entries. A registered synthesis with
another source meets each entry independently. It can remain `ACT` for
`payroll.read` while remaining unable to authorize `export.send`. A new scope,
such as `funds.transfer`, is `NONE` until policy explicitly defines it.

### Memory plus a fresh tool result

Both record ids are direct parents. Caps meet pointwise and support unions.
Treating the fresh tool as the output's origin and discarding the memory parent
would recreate E2A's relay-elevation failure.

### Weak contribution

There are no weights. If the orchestration layer exposed a parent to the
transform, that parent is included in full. This is conservative and may cause
collateral quarantine; silently omitting it would violate I3.

## Action decision

For an action in scope `s`, the gateway requires every cited record to have
`EffectiveCaps(record)[s] == ACT` under the latest revocation generation. A
record at `INFORM` may help a model formulate a response but cannot satisfy the
gateway. An uncited action remains denied.

This keeps the enforcement interface small: callers ask one scoped question;
the authority module owns lattice policy, receipt validation, support closure,
and revocation overlay evaluation.

## Explicit limits

- Structural support proves exposure/dependency, not truth or entailment.
- Free-form paraphrases do not retain `ACT`; distinguishing benign from
  malicious free-form rewriting would require a semantic or trusted typed
  mechanism not present here.
- No corroboration elevation, weighted attribution, or cryptographic receipt
  authentication is included.
- Records with unauthenticated or missing admission time cannot participate in
  precise interval selection; `DYNAMIC_TRUST_MODEL.md` defines the fallback.
