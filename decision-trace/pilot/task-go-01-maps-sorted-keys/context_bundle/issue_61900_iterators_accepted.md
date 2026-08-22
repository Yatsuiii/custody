# golang/go#61900 — "maps: add iterator-related functions"

Fetched via `gh issue view 61900 --repo golang/go --json title,url,body,comments`.
State: CLOSED. Final proposal-review ruling: **accepted**.
https://github.com/golang/go/issues/61900

## Proposal body (excerpt, verbatim)

> We propose to add the following functions to package maps, to provide
> good support for code using iterators.
>
> ```go
> // All returns an iterator over key-value pairs from m.
> func All[Map ~map[K]V, K comparable, V any](m Map) iter.Seq2[K, V]
>
> // Keys returns an iterator over keys in m.
> func Keys[Map ~map[K]V, K comparable, V any](m Map) iter.Seq[K]
>
> // Values returns an iterator over values in m.
> func Values[Map ~map[K]V, K comparable, V any](m Map) iter.Seq[V]
>
> // Insert adds the key-value pairs from seq to m.
> func Insert[Map ~map[K]V, K comparable, V any](m Map, seq iter.Seq2[K, V])
>
> // Collect collects key-value pairs from seq into a new map and returns it.
> func Collect[K comparable, V any](seq iter.Seq2[K, V]) map[K]V
> ```

## rsc, 2024-01-31T18:28:07Z (verbatim)

> It's true that slices.Sorted(maps.Keys(m)) will not pre-size the slice,
> but that's not necessarily a strike against the iterator forms. We could
> have a separate discussion about maps.KeysSorted and maps.KeysSortedFunc
> as optimizations, if that became a concern.

(No such follow-on `maps.KeysSorted` proposal was ever separately accepted;
the companion decline of `maps.KeysSlice`/`ValuesSlice`, see
`issue_61626_keysslice_declined.md`, is the closest thing to it, and it
was declined.)

## rsc, 2024-02-14T23:50:36Z — final ruling (verbatim)

> No change in consensus, so accepted. 🎉
> This issue now tracks the work of implementing the proposal.
> — rsc for the proposal review group

The full accepted godoc, as quoted in the ruling comment:

```
func All[Map ~map[K]V, K comparable, V any](m Map) iter.Seq2[K, V]
func Collect[K comparable, V any](seq iter.Seq2[K, V]) map[K]V
func Insert[Map ~map[K]V, K comparable, V any](m Map, seq iter.Seq2[K, V])
func Keys[Map ~map[K]V, K comparable, V any](m Map) iter.Seq[K]
func Values[Map ~map[K]V, K comparable, V any](m Map) iter.Seq[V]
```

This is exactly the API present in the pinned snapshot's
`src/maps/iter.go` (see `current_maps_package.md`).

## Net effect of #61900 + #61626 together

Package `maps` intentionally exposes `Keys`/`Values` only as
**iterators** (`iter.Seq[K]` / `iter.Seq[V]`), never as slice-returning
functions. Getting a `[]K`/`[]V` out of a map is meant to be done by
composing `maps.Keys`/`maps.Values` with `slices.Collect` (unsorted) or
`slices.Sorted` (sorted), not by adding a new package-level function that
does the loop-and-append-and-return-a-slice itself. A later, repeated
attempt to add that convenience function back (#61626, and its duplicates
#72909, #73291, #65919) was declined each time on this same rationale.
