# golang/go#61626 — "proposal: maps: add maps.KeysSlice and maps.ValuesSlice"

Fetched via `gh issue view 61626 --repo golang/go --json title,url,body,comments`.
State: CLOSED. Final proposal-review ruling: **declined**.
https://github.com/golang/go/issues/61626

## Original request (body, verbatim)

> Since we need to reserve Keys and Values for iterators.
> I think we might need to change the old maps.Keys/Values to
> maps.KeysSlice/ValuesSlice as mention in
> [513715](https://go-review.googlesource.com/c/go/+/513715)

(i.e., add exported functions to package `maps` that return a map's keys,
or values, directly as a `[]K` / `[]V` slice — the same shape as the old
`golang.org/x/exp/maps.Keys` / `.Values`.)

## rsc, 2023-08-09T20:24:21Z (proposal-review comment, verbatim)

> #61900 adds Keys and Values back as iterators.
> #61899 adds slices.Collect and slices.Sorted.
>
> With these, the old maps.Keys(m) would become
> slices.Collect(maps.Keys(m)) and similarly Values.
> Better, this idiom:
>
> ```
> keys := maps.Keys(m)
> slices.Sort(keys)
> use(keys)
> ```
>
> becomes
>
> ```
> use(slices.Sorted(maps.Keys(m))
> ```
>
> Are there other pattern uses for maps.Keys (other than sorting them) that
> we should be sure to cover?

## rsc, 2024-01-23T19:52:05Z (verbatim)

> The key issue seems to be
> https://github.com/golang/go/issues/61626#issuecomment-1672096753.
> It sounds like if we add maps.Keys, maps.Values, and slices.Collect, then
> we can use
>
> KeySlices(m) => slices.Collect(maps.Keys(m))  (or slices.Sorted(maps.Keys(m)))
> ValuesSlice(m) => slices.Collect(maps.Values(m))
>
> and do not need to add these explicitly.

## rsc, 2024-02-01T20:24:03Z (verbatim)

> Based on the discussion above, this proposal seems like a likely decline.
> — rsc for the proposal review group

## rsc, 2024-02-08T23:59:34Z — final ruling (verbatim)

> No change in consensus, so declined.
> — rsc for the proposal review group

## Governing rule established

The stdlib `maps` package deliberately does **not** export a
slice-returning `Keys`/`Values`-family function (e.g. `KeysSlice`,
`ValuesSlice`, or any signature `func(m Map) []K`). The accepted,
authoritative pattern for "I need a map's keys as a slice" is
**composition**: `slices.Collect(maps.Keys(m))` or, for a sorted slice,
`slices.Sorted(maps.Keys(m))` — using the iterator-returning `maps.Keys`
(added by #61900, see companion doc) together with `slices.Collect` /
`slices.Sorted` (added by #61899). This was an explicit, considered
decision, not an oversight: the proposal was actively discussed for six
months and closed with an explicit "declined" ruling from the proposal
review group, precisely because the composition already covers the need.
