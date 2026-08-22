# Issue #2298 — accepted direction

Source: https://github.com/tokio-rs/axum/issues/2298

The issue identifies that blanket `Option<Extractor>` behavior caused users to
expect different semantics for particular extractors. It proposes separate
`OptionalFromRequest` and `OptionalFromRequestParts` traits, implemented only
for the types where discarding a specific missing-value error makes sense.

The complete issue discussion contains two comments. Contributor Jonas Platte
asks maintainer David Pedersen how positive he is about that proposal. Pedersen
answers, “I think that sounds like a good path!” The issue is closed by the
merge of PR #2475.

- Proposal question: https://github.com/tokio-rs/axum/issues/2298#issuecomment-1872586851
- Maintainer acceptance: https://github.com/tokio-rs/axum/issues/2298#issuecomment-1872592684
