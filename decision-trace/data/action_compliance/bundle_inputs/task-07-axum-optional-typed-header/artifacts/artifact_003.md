# Pinned code snapshot

Repository: `tokio-rs/axum`

Pinned SHA: `fd11d8efde4895a2159a29dcd586a7db99917057`

Relevant baseline files:

- `axum-core/src/extract/mod.rs` has a blanket `FromRequestParts` implementation
  for `Option<T>` that calls `.await.ok()`, collapsing every rejection to
  absence.
- `axum-extra/src/typed_header.rs` already distinguishes missing headers from
  malformed present values in the non-optional `TypedHeader` rejection.
- `axum/src/extract/mod.rs` re-exports the core extractor API.

The pin is the immutable base SHA of merged PR #2475. The requested slice is
small: three modified source files, one new source module, and focused tests.
