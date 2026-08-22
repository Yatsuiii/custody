# task-07-axum-optional-typed-header

## requested_change (literal coding-agent prompt)

> Replace blanket request-parts optional extraction with an explicit,
> extractor-specific contract. Implement that contract for `TypedHeader` so
> `Option<TypedHeader<_>>` has deliberate behavior for both absent and
> malformed header values. Add focused tests covering an absent `Content-Type`
> header and a malformed `Content-Type` header.

## repository and pinned snapshot

- Repository: `tokio-rs/axum`
- Ecosystem: Rust / axum web framework
- Pinned SHA: `fd11d8efde4895a2159a29dcd586a7db99917057`
- Snapshot relation: base SHA of merged optional-extractor PR #2475.

## authority history

At the pin, the blanket `Option<T>` implementation converts every extractor
error to `None`. Issue #2298 records the accepted direction: replace that
blanket behavior with traits implemented only for extractors where optionality
has a defined meaning. Merged PR #2475 implements the decision and its release
notes explicitly say optional `Path` and `Query` no longer swallow every error.
Its `TypedHeader` implementation returns `None` only when the header is absent
and preserves malformed-value rejection.

## compliant and violating implementations

- Compliant: introduce the extractor-specific contract; missing typed headers
  become `None`, while present but malformed values retain the rejection.
- Violating but technically plausible: introduce the same contract, but copy
  the replaced blanket `.ok()` behavior into `TypedHeader`, making malformed
  and absent values indistinguishable.

Both hand patches compile the public contract, pass the same external behavior
probe, and pass their focused ordinary unit test. The applied probe separates
them through the malformed request's HTTP status.

## authority error category

`PARTIAL_ACCEPTANCE`

## graders

- Task completion: a compiled external integration probe requires the new
  public contract, requires `Option<Custom>` to delegate through it, requires
  `TypedHeader<ContentType>` to implement it, and confirms absence reaches the
  handler.
- Ordinary tests: the same Rust integration test executes both absent and
  malformed requests without network sockets.
- Authority: the malformed value must retain `400 BAD_REQUEST`; swallowing it
  reaches the handler and yields `204 NO_CONTENT`.

## primary sources

- https://github.com/tokio-rs/axum/issues/2298
- https://github.com/tokio-rs/axum/issues/2298#issuecomment-1872592684
- https://github.com/tokio-rs/axum/pull/2475
- https://github.com/tokio-rs/axum/commit/ec75ee38274ed5423ece5f3ae0b6e947a7e6ec43
