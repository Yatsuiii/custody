# TMA-NM Relationship

TMA-NM is treated as strong, verified prior art (`research/RELATED_WORK_AUDIT.md`,
`research/experiments/E2_TMANM_REPRO/`), not as a template to rename. This
document separates conceptual reuse from Custody-specific work and phrases the
remaining intersection as a hypothesis to test.

## Concepts reused from TMA-NM

- **Authority is distinct from mutable content and is bound at write time.**
  Architecture A keeps that separation. Text, hashes, and semantic similarity
  cannot mint authority.
- **Ordinary transformation is non-amplifying.** TMA-NM's write-time binding
  motivates `AUTHORITY_MODEL.md`'s meet rule: output authority cannot exceed
  any input or transformation cap.
- **Authority has operational tiers rather than a single confidence score.**
  `NONE/INFORM/ACT` is reused as the per-action-scope value shape.
- **Elevation, if ever allowed, must be a distinguished operation.** Ordinary
  derivation never doubles as corroboration-based elevation.

These are prior-art concepts. This packet makes no ownership claim over them.

## What is not copied

- TMA-NM's released `MemoryItem` has origin and a flat corroboration list but
  no derivation field
  (`research/experiments/E2_TMANM_REPRO/SOURCE_AUDIT.md`). It cannot represent
  the E0/E1 `A+B -> AB` graph shape in its current data model. Architecture A
  therefore computes over Custody's direct-parent DAG and logical root support,
  rather than adapting a flat item monitor.
- TMA-NM's verified core is static/write-time. The audited artifact has no
  operation for a source that was correctly authorized, later found compromised
  during a bounded interval, followed by descendant repair. Architecture A's
  compromise-window overlay and replacement-only repair come from the open
  Custody question, not from TMA-NM.
- Architecture A does **not** adopt TMA-NM's corroboration elevation in the
  core slice. No E0-E2C result forces it, and the reproduced source audit shows
  naive independence assumptions are dangerous.
- Architecture A caps free-form transformations at `INFORM`. A structural
  parent receipt proves exposure, not that a summary or paraphrase is entailed.
  This is a deliberate boundary rather than a claim that graph ancestry alone
  provides TMA-NM's stronger semantic/action guarantee.

## What current Custody contributes to the combination

- A real multi-parent derivation DAG, corrected and regression-tested in E1.
- Retroactive descendant traversal and idempotent revocation at tool/revision
  granularity.
- Cross-department propagation and an action gateway that can consume a scoped
  authority decision.
- Durable record ids and, on the Firestore path, server-assigned admission
  timestamps that can support an interval selector.

These are existing system capabilities, not evidence that the proposed
combination works.

## What remains an unproven mechanism hypothesis

The hypothesis preregistered in `DESIGN_FALSIFIER.md` is:

> A central structural admission envelope can combine origin-bound,
> non-amplifying authority with Custody's multi-parent graph and retroactive
> traversal so that byte-changing transformations remain traceable and a later
> compromise window blocks exactly the affected closure, while an outside-
> window sibling remains effective.

This hypothesis is narrower than "free-form paraphrases retain action
authority." They do not in this design: they retain support and informational
utility but are capped at `INFORM` unless a registered typed transform provides
a stronger transfer contract.

It is also narrower than a field-level contribution claim. E2 independently
reproduced TMA-NM's offline checks, but not its LLM-backed empirical numbers;
the related-work audit did not locate a system combining all of the above, but
absence from that audit is not proof. The claim remains false until the local
falsifier passes and would still require a broader literature and empirical
review before publication wording.

## Differentiating result that would matter

The useful evidence is not a new name for authority binding. It is one
deterministic artifact showing all of the following in the same system state:

1. a trusted relay cannot elevate an unknown upstream payload;
2. benign and malicious free-form transformations keep structural ancestry;
3. multi-parent synthesis keeps every parent;
4. a later bounded compromise blocks the affected closure;
5. an outside-window sibling remains usable; and
6. retry/crash replay never creates an unsafe interval.

Until that artifact exists, the relationship is a design hypothesis built from
TMA-NM concepts and Custody mechanisms, not a result.
