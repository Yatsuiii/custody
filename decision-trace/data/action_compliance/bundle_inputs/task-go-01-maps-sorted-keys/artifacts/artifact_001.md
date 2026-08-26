# Current `maps` package source at pinned commit 56ebf80e57db9f61981fc0636fc6419dc6f68eda (tag go1.25.1)

## src/maps/iter.go (full file, verbatim)

```go
// Copyright 2024 The Go Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package maps

import "iter"

// All returns an iterator over key-value pairs from m.
// The iteration order is not specified and is not guaranteed
// to be the same from one call to the next.
func All[Map ~map[K]V, K comparable, V any](m Map) iter.Seq2[K, V] {
	return func(yield func(K, V) bool) {
		for k, v := range m {
			if !yield(k, v) {
				return
			}
		}
	}
}

// Keys returns an iterator over keys in m.
// The iteration order is not specified and is not guaranteed
// to be the same from one call to the next.
func Keys[Map ~map[K]V, K comparable, V any](m Map) iter.Seq[K] {
	return func(yield func(K) bool) {
		for k := range m {
			if !yield(k) {
				return
			}
		}
	}
}

// Values returns an iterator over values in m.
// The iteration order is not specified and is not guaranteed
// to be the same from one call to the next.
func Values[Map ~map[K]V, K comparable, V any](m Map) iter.Seq[V] {
	return func(yield func(V) bool) {
		for _, v := range m {
			if !yield(v) {
				return
			}
		}
	}
}

// Insert adds the key-value pairs from seq to m.
// If a key in seq already exists in m, its value will be overwritten.
func Insert[Map ~map[K]V, K comparable, V any](m Map, seq iter.Seq2[K, V]) {
	for k, v := range seq {
		m[k] = v
	}
}

// Collect collects key-value pairs from seq into a new map
// and returns it.
func Collect[K comparable, V any](seq iter.Seq2[K, V]) map[K]V {
	m := make(map[K]V)
	Insert(m, seq)
	return m
}
```

## src/maps/maps.go (signatures only — Equal, EqualFunc, Clone, Copy, DeleteFunc)

No `Keys`/`Values`/`KeysSlice`/`ValuesSlice` slice-returning functions
exist anywhere in this file or `iter.go`. This is the full current
exported surface of package `maps`: `Equal`, `EqualFunc`, `Clone`, `Copy`,
`DeleteFunc`, `All`, `Keys`, `Values`, `Insert`, `Collect`.

## Relevant `slices` package functions (src/slices/iter.go), for composition

```go
func Collect[E any](seq iter.Seq[E]) []E
func Sorted[E cmp.Ordered](seq iter.Seq[E]) []E
func SortedFunc[E any](seq iter.Seq[E], cmp func(E, E) int) []E
func SortedStableFunc[E any](seq iter.Seq[E], cmp func(E, E) int) []E
```

`slices.Collect(maps.Keys(m))` yields an unsorted `[]K`.
`slices.Sorted(maps.Keys(m))` yields a sorted `[]K` (requires `K: cmp.Ordered`).
Both are already implemented, tested, and part of accepted stdlib policy
(#61899, companion proposal to #61900, also accepted).

## src/maps/maps_test.go (full file, verbatim — this is the file the task modifies)

Tests present: `TestEqual`, `TestEqualFunc`, `TestClone`, `TestCloneNil`,
`TestCopy`, `TestDeleteFunc`, `BenchmarkMapClone`, `TestCloneWithDelete`,
`TestCloneWithMapAssign`, `TestCloneLarge`. No test in this file exercises
`Keys`/`Values`/`All`/`Insert`/`Collect` (those live in `iter_test.go`) and
no test builds a sorted slice of a map's keys for a deterministic-output
comparison — see `TASK.md` for the requested addition.

Shared test fixtures already in the file:
```go
var m1 = map[int]int{1: 2, 2: 4, 4: 8, 8: 16}
var m2 = map[int]string{1: "2", 2: "4", 4: "8", 8: "16"}
```
