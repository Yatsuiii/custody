# Transformation Model

The mechanism tracks structural exposure, not textual similarity. A changed
string remains connected to its inputs only when an in-TCB collector can state
which stored records were exposed to the operation that produced it.

## Admission envelope

Each admitted output is written with one envelope:

```
AdmissionEnvelope(
    output_id,
    producer_id,
    operation_id,
    invocation_id,
    direct_parent_ids,
    transform_class,
    transform_revision,
    context_complete,
    input_manifest_id,
    policy_version,
    authority,
)
```

- `direct_parent_ids` are immutable record ids, never content guesses.
- `transform_class` is assigned by orchestration policy, not by the model or
  arbitrary tool.
- `context_complete` means the collector observed every stored record exposed
  to the producer. It does not mean the output is truthful.
- `input_manifest_id` is used only when the bounded inline parent list is too
  large. The manifest is immutable, count-checked, and content-digested.
- `authority` is computed by the gate from parents and policy; callers cannot
  submit it.

The envelope, direct edges, and bound authority are one atomic admission. A
record without its envelope is not published to active memory. Replaying the
same `output_id` with identical fields is a no-op; replaying it with different
fields is a conflict and fails closed.

## Who may emit the parent statement

The receipt collector is the adapter that assembles model/tool context inside
Custody's trusted boundary. It records ids as it loads records and carries that
set through the operation. The model cannot add or remove ids. An arbitrary
tool may return strings resembling ids, but those strings are payload, not
provenance.

Current Custody does not yet provide this guarantee across every path. In
particular, a `load_memory` response currently reconnects by text hash, and a
downstream Memory Bank may perform server-side summarization without exposing
the source record ids. Those paths cannot claim complete receipts until an
adapter demonstrates the mapping. This is a production blocker recorded in
`TRUSTED_COMPUTING_BASE.md`, not a detail hidden by the design.

## Transformation classes

| Class | Structural contract | Maximum authority transfer |
|---|---|---|
| `IDENTITY` | Output cites the original record directly; no new proposition is treated as authoritative | Parent caps may be preserved |
| `REGISTERED` | Deterministic typed transform with a reviewed input/output contract and explicit action-scope cap | Pointwise minimum of parent caps and registered cap |
| `FREEFORM` | Model generation, paraphrase, summarization, or other semantically open rewrite | At most `INFORM` in every scope |
| `INCOMPLETE` | Collector cannot prove full context, parent manifest is invalid, or causal validation fails | At most `INFORM`, with `UNKNOWN_CONTEXT` in support |

The distinction is structural. The system never attempts to decide whether a
free-form sentence is a "good" or "bad" paraphrase.

## Receipt validation

Admission fails closed unless all of the following hold:

1. every inline parent exists or the immutable manifest expands successfully;
2. the declared count and manifest digest match;
3. every parent causally precedes the output;
4. parent ids are de-duplicated without dropping any distinct id;
5. the collector's context set equals the receipt set when
   `context_complete=true`; and
6. an `IDENTITY` claim has the same payload digest as the cited parent; and
7. the transformation class/revision is allowed for the producer operation
   under the referenced policy version.

A failed validation does not create a fresh trusted root. The output is either
rejected (`NONE`) or admitted as `INCOMPLETE`/`INFORM` according to explicit
policy, always carrying `UNKNOWN_CONTEXT`.

## Hostile-question fallbacks

### Undeclared context

If a model or tool can read context outside the collector—hidden system memory,
an opaque retrieval plugin, ambient files, or network state—the collector sets
`context_complete=false`. The result is `INCOMPLETE`, includes
`UNKNOWN_CONTEXT`, and cannot authorize an action. A deployment that silently
marks such a path complete violates the TCB contract.

### Huge retrieval

Parent ids are never silently truncated. Inputs above the inline limit use an
immutable chunked manifest with total count and digest. If manifest expansion
is unavailable, exceeds the configured verification bound, or any chunk is
missing, the output becomes `INCOMPLETE`. The first falsifier uses bounded
inline parents; manifest scale is a later acceptance gate, not an assumed win.

### Model hallucination

A receipt proves that parents were visible, not that they entailed the output.
All free-form output is therefore capped at `INFORM`, even when every parent is
`ACT`. A hallucinated proposition may be displayed as model-generated data but
cannot independently authorize a consequential action. Content truth remains
outside this mechanism.

### Incomplete attribution

Any ambiguity adds `UNKNOWN_CONTEXT` and applies the `INCOMPLETE` cap. Missing
metadata is not interpreted as "no parents, therefore a clean root." This
preserves current Custody's fail-closed `NO_INVOCATION`/`NO_AUTHOR` direction.

### Weak contribution

The collector records exposure, not percentage contribution. If a record was
visible to the transform, it is a full direct parent. This may quarantine a
mostly benign output when one weak parent is later compromised. The collateral
is measured; weights are not fabricated.

### Memory plus a fresh tool result

The retrieved memory record and the fresh tool-output record are both direct
parents. The fresh tool's identity never overwrites the memory's support. If
the tool operation is a relay with an unobservable external upstream, the
output also carries `UNKNOWN_CONTEXT` and is capped accordingly.

## Cross-invocation behavior

The record id travels with retrieval metadata inside the adapter; content may
change freely after that point without losing the edge. Exact content hash may
remain as an integrity check for an `IDENTITY` read, but it is no longer an
ancestry reconstruction mechanism. A hash mismatch changes the transform class
or rejects an identity claim; it never asks a similarity model to invent a
parent.

## Write path and downstream publication

The durable envelope is committed before active-memory publication. Publication
uses an idempotent outbox keyed by `output_id`; a crash can leave a durable,
not-yet-published record, but cannot leave published memory with no authority
record. Retry resumes publication. This reverses the unsafe failure shape where
downstream memory exists while its graph edge does not.

Server-side downstream transformations that cannot emit a new envelope are not
allowed to create action-authorizing memories. They may remain an informational
surface outside the mechanism's action claim.

## What the model guarantees

- byte changes no longer erase known structural ancestry;
- ordinary derivation cannot amplify action authority;
- incomplete observation is explicit and fail-closed; and
- every action-authorizing record has an explainable parent/policy path.

It does not guarantee that free-form content is faithful, detect malicious
meaning, or recover unobserved inputs after the fact.
