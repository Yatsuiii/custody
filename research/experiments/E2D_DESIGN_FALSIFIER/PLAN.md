# E2D Plan — Structural Envelope Falsifier Execution

This fixes the record ids and input manifests that
`research/design/DESIGN_FALSIFIER.md` requires as literals. It changes
nothing about the frozen scenario, metrics, or gates — it only names the
concrete fixture that satisfies them.

## Fixture: departments, sources, operations

- Department: `sales`.
- Source `vendor_portal`, operation `vendor_portal.lookup`, role `ORIGIN`,
  policy cap `ACT` for scope `export.send`.
- Source `relay_proxy`, operation `relay_proxy.fetch`, role `RELAY`, no
  observable upstream record for the frozen scenario's relay case.
- Transform `summarize_v1`, class `FREEFORM`.
- Transform `merge_v1`, class `REGISTERED`, contract cap `ACT` for
  `export.send` when every parent already permits it.

## Six required elements, with fixed ids and times

All timestamps UTC RFC 3339. Admission clock is deterministic and
monotonic within the fixture (each record's `admitted_at` is fixed, not
wall-clock).

1. **Trusted-tool echo (`E-RELAY-1`).** `relay_proxy.fetch` returns
   attacker-controlled payload with no observable upstream record.
   `admitted_at = 2026-08-10T09:00:00Z`. Root, `direct_parent_ids = []`,
   `context_complete = false`.

2. **Benign paraphrase (`E-BENIGN-1` -> `E-BENIGN-PARA-1`).**
   `E-BENIGN-1` is an `ACT`-capped `vendor_portal.lookup` root,
   `admitted_at = 2026-08-05T09:00:00Z` (outside the later compromise
   window — this doubles as the required outside-window sibling root).
   `E-BENIGN-PARA-1` is `summarize_v1` (`FREEFORM`) over `E-BENIGN-1`,
   `admitted_at = 2026-08-05T09:05:00Z`.

3. **Malicious paraphrase (`E-MAL-1` -> `E-MAL-PARA-1`).** `E-MAL-1` is a
   `NONE`-capped root (unvouched operation), `admitted_at =
   2026-08-15T09:00:00Z`. `E-MAL-PARA-1` is `summarize_v1` (`FREEFORM`)
   over `E-MAL-1`, `admitted_at = 2026-08-15T09:05:00Z`.

4. **Multi-parent synthesis.**
   - `E-SYN-ACT-ACT` = `merge_v1` (`REGISTERED`) over two `ACT` roots:
     `E-BENIGN-1` (2026-08-05, outside window) and `E-VENDOR-2`, a second
     `ACT` `vendor_portal.lookup` root inside the window,
     `admitted_at = 2026-08-15T10:00:00Z`. Synthesis `admitted_at =
     2026-08-15T10:05:00Z`.
   - `E-SYN-ACT-NONE` = `merge_v1` (`REGISTERED`) over one `ACT` root
     (`E-BENIGN-1`) and one `NONE` root (`E-MAL-1`).
     `admitted_at = 2026-08-15T10:10:00Z`.

5. **Later compromise.** Window `W1`:
   `source_id = vendor_portal`, `operation_id = vendor_portal.lookup`,
   `start = 2026-08-12T00:00:00Z`, `end = 2026-08-19T00:00:00Z`,
   `reported_at = 2026-08-20T00:00:00Z`. `E-VENDOR-2`
   (2026-08-15, in-window) is the affected root. `E-BENIGN-1`
   (2026-08-05, outside window) is not.

6. **Unaffected sibling.** `E-BENIGN-1` and its identity descendant
   `E-BENIGN-IDENTITY-1` (`IDENTITY` transform citing `E-BENIGN-1`
   directly, `admitted_at = 2026-08-06T09:00:00Z`) must both remain `LIVE`
   and `export.send`-eligible after `W1` activates, since neither is
   supported by `E-VENDOR-2`.

## Derived-record support closure (ground truth, for `direct_parent_recall`/`affected_recall`)

| Record | Direct parents | Support (root closure) | Affected by W1? |
|---|---|---|---|
| `E-RELAY-1` | `[]` | `{self, UNKNOWN_CONTEXT}` | no |
| `E-BENIGN-1` | `[]` (root) | `{self}` | no |
| `E-BENIGN-PARA-1` | `[E-BENIGN-1]` | `{E-BENIGN-1}` | no |
| `E-BENIGN-IDENTITY-1` | `[E-BENIGN-1]` | `{E-BENIGN-1}` | no |
| `E-MAL-1` | `[]` (root) | `{self}` | no (not in W1's source/operation scope — different root, NONE-capped, not selected by W1) |
| `E-MAL-PARA-1` | `[E-MAL-1]` | `{E-MAL-1}` | no |
| `E-VENDOR-2` | `[]` (root) | `{self}` | **yes** (direct root in window) |
| `E-SYN-ACT-ACT` | `[E-BENIGN-1, E-VENDOR-2]` | `{E-BENIGN-1, E-VENDOR-2}` | **yes** (support intersects `{E-VENDOR-2}`) |
| `E-SYN-ACT-NONE` | `[E-BENIGN-1, E-MAL-1]` | `{E-BENIGN-1, E-MAL-1}` | no |

## Expected `Caps` before W1 activates

| Record | `export.send` cap | Rationale |
|---|---|---|
| `E-RELAY-1` | `INFORM` | `RELAY`, no observable upstream, `UNKNOWN_CONTEXT` |
| `E-BENIGN-1` | `ACT` | `ORIGIN` root, policy cap `ACT` |
| `E-BENIGN-PARA-1` | `INFORM` | `FREEFORM` caps at `INFORM` regardless of parent |
| `E-BENIGN-IDENTITY-1` | `ACT` | `IDENTITY` may preserve parent cap |
| `E-MAL-1` | `NONE` | unvouched root |
| `E-MAL-PARA-1` | `NONE` | `min(INFORM, NONE) = NONE` |
| `E-VENDOR-2` | `ACT` | `ORIGIN` root, policy cap `ACT` |
| `E-SYN-ACT-ACT` | `ACT` | `min(REGISTERED_cap=ACT, ACT, ACT) = ACT` |
| `E-SYN-ACT-NONE` | `NONE` | `min(ACT_cap, ACT, NONE) = NONE` |

## Expected `EffectiveCaps` after W1 activates

Every record whose `Support` intersects `{E-VENDOR-2}` becomes `NONE` in
every scope regardless of its bound `Caps`. That is exactly `E-VENDOR-2`
and `E-SYN-ACT-ACT`. Everything else is unchanged from the table above.

## Crash/replay probe points

Simulated by taking a durable-state snapshot after each named step below,
then resuming from that snapshot and re-running the remainder, comparing
the final artifact to a no-fault run:

1. after window intent (W1 marked `ACTIVE`), before the repair plan is
   built;
2. after the plan is persisted, before the first per-record outcome is
   applied;
3. midway through per-record repair (after `E-VENDOR-2`'s outcome, before
   `E-SYN-ACT-ACT`'s);
4. after all outcomes are applied, before `phase` is marked `COMPLETE`.

## What this plan does not do

It does not touch `custody/*.py`. It does not run the "CURRENT_CUSTODY"
comparison arm — that baseline is already characterized by E1/E2A/E2B/E2C
per `DESIGN_FALSIFIER.md`'s result table, and re-deriving it is outside
this plan's scope. This plan runs Architecture A only, against the gates
already fixed in `DESIGN_FALSIFIER.md`.
