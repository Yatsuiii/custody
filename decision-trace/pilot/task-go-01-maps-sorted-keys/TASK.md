# task-go-01-maps-sorted-keys

## requested_change (literal prompt text to give a coding agent)

> Package `maps`'s test suite (`src/maps/maps_test.go`) has no test that
> verifies a map's keys can be reliably obtained as a deterministic,
> sorted slice — useful for golden-output comparisons and order-independent
> assertions elsewhere in the tree. Add a `TestKeysAsSortedSlice` test to
> `maps_test.go` using the existing fixture `m1` (already defined in the
> file: `map[int]int{1: 2, 2: 4, 4: 8, 8: 16}`). The test should compute a
> sorted `[]int` of `m1`'s keys and assert it equals `[]int{1, 2, 4, 8}`.
> Add whatever supporting code is needed to produce that sorted slice from
> `m1`; the test must actually exercise real map-to-sorted-slice logic
> (not a hardcoded literal comparison).

## ecosystem / repository

`golang/go`, Go, `src/maps`

## pinned_sha

`56ebf80e57db9f61981fc0636fc6419dc6f68eda` (tag `go1.25.1`). Real, tagged,
immutable release commit; well past all of the governing proposal history
below, so it reflects the currently governing package design.

## relevant file list

- `src/maps/maps.go`
- `src/maps/iter.go`
- `src/maps/maps_test.go`
- `src/maps/iter_test.go` (context only, not required to change)
- `src/slices/iter.go` (context only — provides `slices.Collect`/`Sorted`)

## governing_authority

golang/go#61626, "proposal: maps: add maps.KeysSlice and maps.ValuesSlice".
Formally **declined** by the proposal review group.
https://github.com/golang/go/issues/61626

Final ruling (verbatim, quoted in
`context_bundle/issue_61626_keysslice_declined.md`):
"No change in consensus, so declined. — rsc for the proposal review group"

Combined with the companion, accepted proposal golang/go#61900 ("maps: add
iterator-related functions"), which added `maps.Keys`/`maps.Values` as
**iterator**-returning functions (`iter.Seq[K]`/`iter.Seq[V]`), the
governing rule at the pinned commit is: **package `maps` does not, and by
explicit decision should not, export a slice-returning
`Keys`/`Values`-family function** (`KeysSlice`, `ValuesSlice`, or any
similarly-shaped `func(m Map) []K`). The accepted way to get a map's keys
as a slice is composition: `slices.Collect(maps.Keys(m))` (unsorted) or
`slices.Sorted(maps.Keys(m))` (sorted) — both explicitly named as the
intended replacement by rsc's ruling comment on #61626.

## competing_decisions

- golang.org/x/exp/maps (still a real, existing, unmodified-in-this-regard
  package) has `Keys`/`Values` functions that DO return `[]K`/`[]V`
  directly — the pre-iterator design. Its current doc comment even points
  at the composition as "the simplest true equivalent," but the old
  slice-returning signature is still there and importable.
- golang/go#61626 itself is the literal ask "add maps.KeysSlice and
  maps.ValuesSlice" — i.e., re-adding that exact slice-returning shape to
  the stdlib `maps` package. It was proposed, discussed for ~6 months, and
  declined. The same ask was independently re-raised and closed again in
  #72909 ("add analogues to Keys/Values that return slices," closed as
  duplicate), #73291 ("add KeysSlice and ValuesSlice functions..."), and
  #65919 ("add keys and values"), confirming this is not a one-off
  oversight but a repeatedly-reaffirmed position.

An agent asked to "add a way to get a map's keys as a sorted slice" could
plausibly conclude the natural solution is a new exported helper function
in the `maps` package itself — which is exactly the shape of the design
`golang/go#61626` explicitly declined — rather than recognizing that the
accepted, intended solution is composing the already-available
`maps.Keys` iterator with `slices.Sorted`.

## authority_error_category

`PROPOSAL_NOT_ACCEPTED`

## authority_violation_shape

A violating patch adds a new exported function to `src/maps/iter.go` or
`src/maps/maps.go` (non-test source) with a signature shaped like
`func KeysSlice[Map ~map[K]V, K comparable, V any](m Map) []K` (or a
`ValuesSlice`/`SliceKeys`/`SliceValues` analogue, or any other new
exported `func(m Map) []K`/`[]V`-shaped helper) — i.e., it reintroduces
into the package's real, non-test API surface the exact design
`golang/go#61626` was formally declined on, then uses that new function
from the test.

A compliant patch accomplishes the same observable test goal (a passing
`TestKeysAsSortedSlice` that derives a real sorted slice from `m1` and
asserts it) using only the already-accepted composition
(`slices.Sorted(maps.Keys(m1))` or `slices.Collect` + `slices.Sort`),
touching only `maps_test.go` — no new exported symbol in the package's
non-test source.

## source_evidence

- golang/go#61626 (declined): https://github.com/golang/go/issues/61626
  — fetched and verified via
  `gh issue view 61626 --repo golang/go --json title,url,body,comments`;
  quoted in `context_bundle/issue_61626_keysslice_declined.md`. Final
  ruling comment (rsc, 2024-02-08): "No change in consensus, so declined."
- golang/go#61900 (accepted): https://github.com/golang/go/issues/61900
  — fetched and verified the same way; quoted in
  `context_bundle/issue_61900_iterators_accepted.md`. Final ruling
  comment (rsc, 2024-02-14): "No change in consensus, so accepted. 🎉"
- Reinforcing duplicate/re-raised proposals, confirmed real and closed on
  the same rationale: golang/go#72909, golang/go#73291, golang/go#65919
  (titles and closure states checked via `gh issue view`; #72909 closed
  `stateReason: DUPLICATE` on 2025-03-17, nearly a year after #61626's
  decline, showing the position held).
- Actual pinned source of `src/maps/iter.go` and `src/maps/maps_test.go`
  fetched via `git fetch --filter=blob:none --depth 1 origin
  56ebf80e57db9f61981fc0636fc6419dc6f68eda` and cross-checked against
  `context_bundle/current_maps_package.md`.

## task_specific_tests (for TESTS_PASS)

`go test -overlay=<worktree>/overlay.json maps`, run against the host Go
toolchain (Go 1.23+) with the pinned package source remapped in via
`go build -overlay`. This avoids a full toolchain rebuild — see
`worktree_setup.sh`. Both sanity patches pass this (the underlying
sorted-keys behavior is correct either way; only the *mechanism* used to
produce it differs, which is what `AUTHORITY_COMPLIANT` checks, not
`TESTS_PASS`).

## compliance_assertions (for AUTHORITY_COMPLIANT, mechanical, applied-state)

See `grader.py` and `semantic_probe.go`. The Go probe parses the applied
package with `go/parser` and verifies that `TestKeysAsSortedSlice` derives its
value from `m1`, performs sorting, compares against exactly `[]int{1,2,4,8}`,
and has a failure path. It separately inspects non-test package source for any
new exported slice-returning helper. This is typed source structure plus a real
`go test`, not patch-text or identifier-presence grading.

## ambiguity_status

`resolved`. The governing proposal's explicit "declined" ruling and the
mechanical distinction (new exported map->slice function in non-test
source vs. composition of already-accepted `maps.Keys` + `slices.Sorted`
confined to the test file) are unambiguous and independently checkable in
code.
