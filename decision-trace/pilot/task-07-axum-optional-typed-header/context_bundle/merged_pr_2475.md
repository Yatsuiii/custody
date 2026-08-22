# Merged PR #2475 — governing implementation and release contract

Source: https://github.com/tokio-rs/axum/pull/2475

PR #2475, “Add a separate trait for optional extractors,” merged on 2024-12-10
as `ec75ee38274ed5423ece5f3ae0b6e947a7e6ec43`. Its checklist adds the two
optional-extractor traits, implements them only for relevant types, deprecates
the old optional wrappers, documents the behavior, and updates changelogs. A
review approved the final PR.

The merged axum and axum-extra changelogs state that `Option<Path<T>>` and
`Option<Query<T>>` no longer swallow all error conditions. The documentation
uses `TypedHeader` as the general example: a missing header produces `None`,
whereas a present header that fails to parse rejects the request.

The merged `TypedHeader` implementation records whether the header is missing,
returns `Ok(None)` only for that case, and returns `TypedHeaderRejection` for a
decode failure when a value was present. This code is policy-conforming
implementation evidence; it is not inferred from the pre-merge blanket code.
