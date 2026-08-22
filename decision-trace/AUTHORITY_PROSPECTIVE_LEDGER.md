# Prospective Authority Ground-Truth Ledger

Status: **FROZEN BEFORE INFERENCE**. This ledger was produced only from pinned primary-source artifacts and the separately adjudicated answer key. No DecisionTrace, embedding-RAG, or full-context output existed during selection or adjudication.

## Audit protocol

- Unit: an ordered organizational-decision history queried at explicit checkpoints.
- Allowed truth states: exactly one governing decision, multiple parallel governing decisions, unresolved, or no governing decision.
- Authority requires an explicit source-grounded status/transition. Recency alone is never an authority transition.
- Normalized scope names are public query keys grounded in artifact subjects; they are not hidden answer labels.
- A merged code rollback governs the tested implementation scope. It does not change a separate policy scope unless a source says so.
- Partial or qualified replacement is not promoted to a unique broad-scope winner; those checkpoints are unresolved.
- The same researcher performed a second source-only pass over the required strata. No independent second annotator was available; this is recorded as a validity threat.

## Frozen inventory

- Dataset SHA-256 (public timelines): `e7d88612dcdfe9ef030f03b0dc46fc6134884546b530e737dcac7da4ffba4dac`
- Source-cache SHA-256: `c12b48af30fd3cd4cd3bffab995d5745c66ef3bd48a0e36b39d4ea543e79824f`
- Timelines: 23
- Checkpoints: 101
- Composition: 19 fully real, 4 hybrid, 0 fully synthetic
- Ecosystems: Envoy 1, Go 3, Kubernetes 2, LLVM 1, OpenTofu 1, Python 5, Rust 6, Swift 3, Terraform 1
- Scenario-bearing timelines: conflicting_or_ambiguous 3, explicit_restoration 4, implementation_vs_policy 3, mention_without_transition 5, multi_hop_supersession 3, parallel_scopes 4, partial_supersession 3, proposal_accepted 3, proposal_while_current 16, revert_after_implementation 7, revert_without_automatic_restoration 5, revert_without_policy_restoration 3, simple_supersession 8, withdrawn_decision 3

## Timeline-by-timeline adjudication

### 1. `python-db-api` — Python

Composition: **hybrid**. Repositories: python/peps. Scenarios: simple_supersession, mention_without_transition.

Audit note: Historical PEP creation checkpoints plus a current pinned registry notice; no lifecycle fact is synthetic.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [PEP-248@accepted](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0248.rst) / python-db-api | FINAL / POLICY | none | `Status: Final` |
| 2 | [PEP-249@accepted](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0249.rst) / python-db-api | FINAL / POLICY | replaces PEP-248 | `Status: Final`; `Replaces: 248` |
| 3 | [PEP-248@current-note](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0248.rst) / python-db-api | NOTE / MENTION | none | `Superseded-By: 249` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `python-db-api-c1` | 1 | python-db-api | GOVERNING: PEP-248 | PEP-248@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-db-api-c2` | 2 | python-db-api | GOVERNING: PEP-249 | PEP-249@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-db-api-c3` | 3 | python-db-api | GOVERNING: PEP-249 | PEP-249@accepted + PEP-248@current-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-db-api-c4` | 3 | python-db-api | GOVERNING: PEP-249 | PEP-249@accepted + PEP-248@current-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 2. `python-wsgi` — Python

Composition: **hybrid**. Repositories: python/peps. Scenarios: simple_supersession, mention_without_transition.

Audit note: Historical PEP creation checkpoints plus a current pinned registry notice; no lifecycle fact is synthetic.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [PEP-333@accepted](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0333.rst) / python-wsgi | FINAL / POLICY | none | `Status: Final` |
| 2 | [PEP-3333@accepted](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-3333.rst) / python-wsgi | FINAL / POLICY | replaces PEP-333 | `Status: Final`; `Replaces: 333` |
| 3 | [PEP-333@current-note](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0333.rst) / python-wsgi | NOTE / MENTION | none | `Superseded-By: 3333` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `python-wsgi-c1` | 1 | python-wsgi | GOVERNING: PEP-333 | PEP-333@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-wsgi-c2` | 2 | python-wsgi | GOVERNING: PEP-3333 | PEP-3333@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-wsgi-c3` | 3 | python-wsgi | GOVERNING: PEP-3333 | PEP-3333@accepted + PEP-333@current-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-wsgi-c4` | 3 | python-wsgi | GOVERNING: PEP-3333 | PEP-3333@accepted + PEP-333@current-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 3. `python-exception-context` — Python

Composition: **hybrid**. Repositories: python/peps. Scenarios: simple_supersession, mention_without_transition.

Audit note: Historical PEP creation checkpoints plus a current pinned registry notice; no lifecycle fact is synthetic.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [PEP-409@accepted](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0409.rst) / python-exception-context | FINAL / POLICY | none | `Status: Final` |
| 2 | [PEP-415@accepted](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0415.rst) / python-exception-context | FINAL / POLICY | replaces PEP-409 | `Status: Final`; `Replaces: 409` |
| 3 | [PEP-409@current-note](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0409.rst) / python-exception-context | NOTE / MENTION | none | `Superseded-By: 415` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `python-exception-context-c1` | 1 | python-exception-context | GOVERNING: PEP-409 | PEP-409@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-exception-context-c2` | 2 | python-exception-context | GOVERNING: PEP-415 | PEP-415@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-exception-context-c3` | 3 | python-exception-context | GOVERNING: PEP-415 | PEP-415@accepted + PEP-409@current-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-exception-context-c4` | 3 | python-exception-context | GOVERNING: PEP-415 | PEP-415@accepted + PEP-409@current-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 4. `python-hash-api` — Python

Composition: **hybrid**. Repositories: python/peps. Scenarios: simple_supersession, mention_without_transition.

Audit note: Historical PEP creation checkpoints plus a current pinned registry notice; no lifecycle fact is synthetic.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [PEP-247@accepted](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0247.rst) / python-hash-api | FINAL / POLICY | none | `Status: Final` |
| 2 | [PEP-452@accepted](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0452.rst) / python-hash-api | FINAL / POLICY | replaces PEP-247 | `Status: Final`; `Replaces: 247` |
| 3 | [PEP-247@current-note](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0452.rst) / python-hash-api | NOTE / MENTION | none | `Replaces: 247` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `python-hash-api-c1` | 1 | python-hash-api | GOVERNING: PEP-247 | PEP-247@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-hash-api-c2` | 2 | python-hash-api | GOVERNING: PEP-452 | PEP-452@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-hash-api-c3` | 3 | python-hash-api | GOVERNING: PEP-452 | PEP-452@accepted + PEP-247@current-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-hash-api-c4` | 3 | python-hash-api | GOVERNING: PEP-452 | PEP-452@accepted + PEP-247@current-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 5. `rust-naked-functions` — Rust

Composition: **fully_real**. Repositories: rust-lang/rfcs. Scenarios: proposal_while_current, simple_supersession, withdrawn_decision.

Audit note: PR open/merge events and current explicit RFC supersession text are primary-source pinned.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [RFC-1201@merged](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/1201-naked-fns.md) / rust-naked-functions | MERGED / POLICY | none | mergedAt=`2016-03-21T19:39:06Z` |
| 2 | [RFC-2972@open](https://github.com/rust-lang/rfcs/pull/2972) / rust-naked-functions | OPEN / POLICY | replaces RFC-1201 | createdAt=`2020-08-07T13:27:05Z` |
| 3 | [RFC-2972@current-authority](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/2972-constrained-naked.md) / rust-naked-functions | MERGED / POLICY | replaces RFC-1201 | mergedAt=`2021-11-16T19:33:46Z`; `In short this RFC was superseded by RFC 2972. For details see the [summary comment].` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `rust-naked-functions-c1` | 1 | rust-naked-functions | GOVERNING: RFC-1201 | RFC-1201@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-naked-functions-c2` | 2 | rust-naked-functions | GOVERNING: RFC-1201 | RFC-1201@merged + RFC-2972@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-naked-functions-c3` | 3 | rust-naked-functions | GOVERNING: RFC-2972 | RFC-2972@current-authority | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-naked-functions-c4` | 3 | rust-naked-functions | GOVERNING: RFC-2972 | RFC-2972@current-authority | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 6. `rust-global-allocator` — Rust

Composition: **fully_real**. Repositories: rust-lang/rfcs. Scenarios: proposal_while_current, simple_supersession.

Audit note: PR open/merge events and current explicit RFC supersession text are primary-source pinned.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [RFC-1183@merged](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/1183-swap-out-jemalloc.md) / rust-global-allocator | MERGED / POLICY | none | mergedAt=`2015-07-29T21:39:23Z` |
| 2 | [RFC-1974@open](https://github.com/rust-lang/rfcs/pull/1974) / rust-global-allocator | OPEN / POLICY | replaces RFC-1183 | createdAt=`2017-04-16T20:52:56Z` |
| 3 | [RFC-1974@current-authority](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/1974-global-allocators.md) / rust-global-allocator | MERGED / POLICY | replaces RFC-1183 | mergedAt=`2017-06-18T01:51:00Z`; `*Note:* this RFC has been superseded by [RFC 1974][].` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `rust-global-allocator-c1` | 1 | rust-global-allocator | GOVERNING: RFC-1183 | RFC-1183@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-global-allocator-c2` | 2 | rust-global-allocator | GOVERNING: RFC-1183 | RFC-1183@merged + RFC-1974@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-global-allocator-c3` | 3 | rust-global-allocator | GOVERNING: RFC-1974 | RFC-1974@current-authority | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-global-allocator-c4` | 3 | rust-global-allocator | GOVERNING: RFC-1974 | RFC-1974@current-authority | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 7. `rust-inline-const` — Rust

Composition: **fully_real**. Repositories: rust-lang/rfcs. Scenarios: proposal_while_current, partial_supersession, conflicting_or_ambiguous.

Audit note: PR open/merge events and current explicit RFC supersession text are primary-source pinned.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [RFC-2203@merged](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/2203-const-repeat-expr.md) / rust-const-repeat-simple-case | MERGED / POLICY | none | mergedAt=`2018-03-18T20:55:04Z` |
| 2 | [RFC-2920@open](https://github.com/rust-lang/rfcs/pull/2920) / rust-inline-const | OPEN / POLICY | replaces RFC-2203 | createdAt=`2020-05-04T18:50:34Z` |
| 3 | [RFC-2920@current-authority](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/2920-inline-const.md) / rust-inline-const | MERGED / POLICY | replaces RFC-2203 | mergedAt=`2020-08-27T19:44:58Z`; `> ⚠ This RFC has mostly been superseded ⚠` |
| 4 | [RFC-2203@partial-note](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/2203-const-repeat-expr.md) / rust-inline-const-broad | NOTE / MENTION | none | `> ⚠ This RFC has mostly been superseded ⚠` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `rust-inline-const-c1` | 1 | rust-const-repeat-simple-case | GOVERNING: RFC-2203 | RFC-2203@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-inline-const-c2` | 2 | rust-const-repeat-simple-case | GOVERNING: RFC-2203 | RFC-2203@merged + RFC-2920@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-inline-const-c3` | 3 | rust-inline-const | GOVERNING: RFC-2920 | RFC-2920@current-authority | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-inline-const-c4` | 4 | rust-inline-const-broad | UNRESOLVED | RFC-2203@partial-note + RFC-2203@merged + RFC-2920@current-authority | The primary source says only partially/mostly superseded, so broad authority is insufficiently specified. |

### 8. `rust-drop-check` — Rust

Composition: **fully_real**. Repositories: rust-lang/rfcs. Scenarios: proposal_while_current, partial_supersession, conflicting_or_ambiguous.

Audit note: PR open/merge events and current explicit RFC supersession text are primary-source pinned.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [RFC-769@merged](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/0769-sound-generic-drop.md) / rust-generic-drop-safety | MERGED / POLICY | none | mergedAt=`2015-02-10T17:19:59Z` |
| 2 | [RFC-1238@open](https://github.com/rust-lang/rfcs/pull/1238) / rust-dropck-parametricity | OPEN / POLICY | replaces RFC-769 | createdAt=`2015-08-05T18:30:09Z` |
| 3 | [RFC-1238@current-authority](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/1238-nonparametric-dropck.md) / rust-dropck-parametricity | MERGED / POLICY | replaces RFC-769 | mergedAt=`2015-09-18T19:14:05Z`; `2015.09.18 -- This RFC was partially superseded by [RFC 1238], which` |
| 4 | [RFC-769@partial-note](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/0769-sound-generic-drop.md) / rust-dropck-parametricity-broad | NOTE / MENTION | none | `2015.09.18 -- This RFC was partially superseded by [RFC 1238], which` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `rust-drop-check-c1` | 1 | rust-generic-drop-safety | GOVERNING: RFC-769 | RFC-769@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-drop-check-c2` | 2 | rust-generic-drop-safety | GOVERNING: RFC-769 | RFC-769@merged + RFC-1238@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-drop-check-c3` | 3 | rust-dropck-parametricity | GOVERNING: RFC-1238 | RFC-1238@current-authority | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-drop-check-c4` | 4 | rust-dropck-parametricity-broad | UNRESOLVED | RFC-769@partial-note + RFC-769@merged + RFC-1238@current-authority | The primary source says only partially/mostly superseded, so broad authority is insufficiently specified. |

### 9. `rust-tait-capture` — Rust

Composition: **fully_real**. Repositories: rust-lang/rfcs. Scenarios: multi_hop_supersession, proposal_while_current.

Audit note: Each hop is an accepted RFC with source-explicit replacement/supersession wording.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [RFC-2071@merged](https://github.com/rust-lang/rfcs/pull/2071) / rust-type-alias-impl-trait-capture | MERGED / POLICY | none | mergedAt=`2017-09-18T21:30:26Z` |
| 2 | [RFC-2515@open](https://github.com/rust-lang/rfcs/pull/2515) / rust-type-alias-impl-trait-capture | OPEN / POLICY | replaces RFC-2071 | createdAt=`2018-08-05T12:09:14Z` |
| 3 | [RFC-2515@merged](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/2515-type_alias_impl_trait.md) / rust-type-alias-impl-trait-capture | MERGED / POLICY | replaces RFC-2071 | mergedAt=`2019-07-28T06:13:16Z`; `Allow type aliases and associated types to use `impl Trait`, replacing the prototype `existential type` as a way to declare type aliases and associated types for opaque, uniquely inferred types.` |
| 4 | [RFC-3498@merged](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/3498-lifetime-capture-rules-2024.md) / rust-type-alias-impl-trait-capture | MERGED / POLICY | replaces RFC-2515 | mergedAt=`2023-11-04T20:08:21Z`; `This updates and supersedes the behavior specified in [RFC 2071] and [RFC 2515].` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `rust-tait-capture-c1` | 1 | rust-type-alias-impl-trait-capture | GOVERNING: RFC-2071 | RFC-2071@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-tait-capture-c2` | 2 | rust-type-alias-impl-trait-capture | GOVERNING: RFC-2071 | RFC-2071@merged + RFC-2515@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-tait-capture-c3` | 3 | rust-type-alias-impl-trait-capture | GOVERNING: RFC-2515 | RFC-2515@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-tait-capture-c4` | 4 | rust-type-alias-impl-trait-capture | GOVERNING: RFC-3498 | RFC-3498@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 10. `rust-rpit-capture` — Rust

Composition: **fully_real**. Repositories: rust-lang/rfcs. Scenarios: multi_hop_supersession, proposal_while_current.

Audit note: RFC 1951 explicitly stabilizes and expands RFC 1522 behavior; RFC 3498 explicitly supersedes both.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [RFC-1522@merged](https://github.com/rust-lang/rfcs/pull/1522) / rust-impl-trait-capture-rules | MERGED / POLICY | none | mergedAt=`2016-06-27T22:28:41Z` |
| 2 | [RFC-1951@open](https://github.com/rust-lang/rfcs/pull/1951) / rust-impl-trait-capture-rules | OPEN / POLICY | replaces RFC-1522 | createdAt=`2017-03-15T06:04:11Z` |
| 3 | [RFC-1951@merged](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/1951-expand-impl-trait.md) / rust-impl-trait-capture-rules | MERGED / POLICY | replaces RFC-1522 | mergedAt=`2017-05-24T01:07:59Z`; `This RFC proposes to stabilize the `impl Trait` feature with its current syntax, while also expanding it to encompass argument position.` |
| 4 | [RFC-3498@rpit-authority](https://github.com/rust-lang/rfcs/blob/354518a8c9025f40be6f730452c1bfe71a12dc22/text/3498-lifetime-capture-rules-2024.md) / rust-impl-trait-capture-rules | MERGED / POLICY | replaces RFC-1951 | mergedAt=`2023-11-04T20:08:21Z`; `This updates and supersedes the behavior specified in [RFC 1522] and [RFC 1951].` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `rust-rpit-capture-c1` | 1 | rust-impl-trait-capture-rules | GOVERNING: RFC-1522 | RFC-1522@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-rpit-capture-c2` | 2 | rust-impl-trait-capture-rules | GOVERNING: RFC-1522 | RFC-1522@merged + RFC-1951@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-rpit-capture-c3` | 3 | rust-impl-trait-capture-rules | GOVERNING: RFC-1951 | RFC-1951@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `rust-rpit-capture-c4` | 4 | rust-impl-trait-capture-rules | GOVERNING: RFC-3498 | RFC-3498@rpit-authority | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 11. `swift-property-wrappers` — Swift

Composition: **fully_real**. Repositories: swiftlang/swift-evolution. Scenarios: withdrawn_decision, simple_supersession, mention_without_transition.

Audit note: Current proposal headers explicitly record withdrawal, successor, and accepted implementation status.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [SE-0030@withdrawn](https://github.com/swiftlang/swift-evolution/blob/0105e139a22938561c700cfbb89ddc3ebe402f0c/proposals/0030-property-behavior-decls.md) / swift-property-wrappers | WITHDRAWN / POLICY | none | `* Status: **Withdrawn**` |
| 2 | [SE-0258@accepted](https://github.com/swiftlang/swift-evolution/blob/0105e139a22938561c700cfbb89ddc3ebe402f0c/proposals/0258-property-wrappers.md) / swift-property-wrappers | ACCEPTED / POLICY | replaces SE-0030 | `* Status: **Implemented (Swift 5.1)**`; `* Superseded by: [SE-0258](0258-property-wrappers.md)` |
| 3 | [SE-0030@historical-note](https://github.com/swiftlang/swift-evolution/blob/0105e139a22938561c700cfbb89ddc3ebe402f0c/proposals/0030-property-behavior-decls.md) / swift-property-wrappers | NOTE / MENTION | none | `* Superseded by: [SE-0258](0258-property-wrappers.md)` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `swift-property-wrappers-c1` | 1 | swift-property-wrappers | NO_GOVERNING_DECISION | SE-0030@withdrawn | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-property-wrappers-c2` | 2 | swift-property-wrappers | GOVERNING: SE-0258 | SE-0258@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-property-wrappers-c3` | 3 | swift-property-wrappers | GOVERNING: SE-0258 | SE-0258@accepted + SE-0030@historical-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-property-wrappers-c4` | 3 | swift-property-wrappers | GOVERNING: SE-0258 | SE-0258@accepted + SE-0030@historical-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 12. `swift-plugin-api` — Swift

Composition: **fully_real**. Repositories: swiftlang/swift-evolution. Scenarios: simple_supersession, partial_supersession, parallel_scopes.

Audit note: SE-0325 explicitly supersedes one entry point while retaining the previous API.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [SE-0303@accepted](https://github.com/swiftlang/swift-evolution/blob/0105e139a22938561c700cfbb89ddc3ebe402f0c/proposals/0303-swiftpm-extensible-build-tools.md) / swiftpm-plugin-legacy-api, swiftpm-plugin-entry-point | ACCEPTED / POLICY | none | `* Status: **Implemented (5.6)**` |
| 2 | [SE-0325@accepted](https://github.com/swiftlang/swift-evolution/blob/0105e139a22938561c700cfbb89ddc3ebe402f0c/proposals/0325-swiftpm-additional-plugin-apis.md) / swiftpm-plugin-entry-point | ACCEPTED / POLICY | replaces SE-0303 | `* Status: **Implemented (Swift 5.6)**`; `The `BuildToolPlugin` protocol entry point defined by SE-0303 is superseded by a new entry point that takes the new `PluginContext` type and a reference to the `Target` for which build commands should be generate. The previous API remains so that existing plugins continue to work.` |
| 3 | [SE-0325@compatibility-note](https://github.com/swiftlang/swift-evolution/blob/0105e139a22938561c700cfbb89ddc3ebe402f0c/proposals/0325-swiftpm-additional-plugin-apis.md) / swiftpm-plugin-legacy-api | NOTE / MENTION | none | `The `BuildToolPlugin` protocol entry point defined by SE-0303 is superseded by a new entry point that takes the new `PluginContext` type and a reference to the `Target` for which build commands should be generate. The previous API remains so that existing plugins continue to work.` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `swift-plugin-api-c1` | 1 | swiftpm-plugin-entry-point | GOVERNING: SE-0303 | SE-0303@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-plugin-api-c2` | 2 | swiftpm-plugin-entry-point | GOVERNING: SE-0325 | SE-0325@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-plugin-api-c3` | 3 | swiftpm-plugin-legacy-api | GOVERNING: SE-0303 | SE-0303@accepted + SE-0325@compatibility-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-plugin-api-c4` | 3 | swiftpm-plugin-entry-point, swiftpm-plugin-legacy-api | MULTIPLE_GOVERNING: SE-0303, SE-0325 | SE-0303@accepted + SE-0325@accepted + SE-0325@compatibility-note | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 13. `go-type-parameters` — Go

Composition: **fully_real**. Repositories: golang/go, golang/proposal. Scenarios: proposal_while_current, proposal_accepted, withdrawn_decision.

Audit note: GitHub proposal issue creation and proposal-review-group acceptance comment are exact primary events.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [go-contracts@superseded](https://github.com/golang/proposal/blob/0be13090fdb0cbae0d71641bb676d924bc1c94de/design/go2draft-contracts.md) / go-type-parameters | WITHDRAWN / POLICY | none | `We will not be pursuing the approach outlined in this design draft.` |
| 2 | [golang/go#43651@open](https://github.com/golang/go/issues/43651) / go-type-parameters | OPEN / POLICY | replaces go-contracts | created_at=`2021-01-12T17:40:04Z` |
| 3 | [golang/go#43651@accepted](https://github.com/golang/go/issues/43651#issuecomment-776944155) / go-type-parameters | ACCEPTED / POLICY | replaces go-contracts | `No change in consensus, so **[accepted]`; `It has been replaced by a [new` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `go-type-parameters-c1` | 1 | go-type-parameters | NO_GOVERNING_DECISION | go-contracts@superseded | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `go-type-parameters-c2` | 2 | go-type-parameters | NO_GOVERNING_DECISION | golang/go#43651@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `go-type-parameters-c3` | 3 | go-type-parameters | GOVERNING: golang/go#43651 | golang/go#43651@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `go-type-parameters-c4` | 3 | go-type-parameters | GOVERNING: golang/go#43651 | golang/go#43651@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 14. `go-loop-variables` — Go

Composition: **fully_real**. Repositories: golang/go, golang/proposal. Scenarios: proposal_while_current, proposal_accepted.

Audit note: GitHub proposal issue creation and proposal-review-group acceptance comment are exact primary events.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [golang/go#60078@open](https://github.com/golang/go/issues/60078) / go-loop-variable-semantics | OPEN / POLICY | none | created_at=`2023-05-09T15:36:18Z` |
| 2 | [golang/go#60078@accepted](https://github.com/golang/go/issues/60078#issuecomment-1642774250) / go-loop-variable-semantics | ACCEPTED / POLICY | none | `No change in consensus, so **[accepted]` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `go-loop-variables-c1` | 1 | go-loop-variable-semantics | NO_GOVERNING_DECISION | golang/go#60078@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `go-loop-variables-c2` | 2 | go-loop-variable-semantics | GOVERNING: golang/go#60078 | golang/go#60078@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `go-loop-variables-c3` | 2 | go-loop-variable-semantics | GOVERNING: golang/go#60078 | golang/go#60078@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `go-loop-variables-c4` | 2 | go-loop-variable-semantics | GOVERNING: golang/go#60078 | golang/go#60078@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 15. `go-range-functions` — Go

Composition: **fully_real**. Repositories: golang/go, golang/proposal. Scenarios: proposal_while_current, proposal_accepted, conflicting_or_ambiguous.

Audit note: GitHub proposal issue creation and proposal-review-group acceptance comment are exact primary events.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [golang/go#61405@open](https://github.com/golang/go/issues/61405) / go-range-function-details | OPEN / POLICY | none | created_at=`2023-07-17T21:17:46Z` |
| 2 | [golang/go#61405@accepted](https://github.com/golang/go/issues/61405#issuecomment-1782052910) / go-range-function-details | ACCEPTED / POLICY | none | `No change in consensus, so **[accepted]` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `go-range-functions-c1` | 1 | go-range-function-details | NO_GOVERNING_DECISION | golang/go#61405@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `go-range-functions-c2` | 2 | go-range-function-details | UNRESOLVED | golang/go#61405@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `go-range-functions-c3` | 2 | go-range-function-details | UNRESOLVED | golang/go#61405@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `go-range-functions-c4` | 2 | go-range-function-details | UNRESOLVED | golang/go#61405@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 16. `python-paramspec-implementation` — Python

Composition: **fully_real**. Repositories: python/cpython, python/peps. Scenarios: implementation_vs_policy, proposal_while_current, revert_after_implementation, parallel_scopes, revert_without_policy_restoration.

Audit note: PEP 612 remains Final while the second PR explicitly reverts part of and changes its implementation.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [PEP-612@final](https://github.com/python/peps/blob/b2120d116aa696f409b4d8333c4020ab8f93c9c7/peps/pep-0612.rst) / python-paramspec-policy | FINAL / POLICY | none | `Status: Final` |
| 2 | [python/cpython#23702@open](https://github.com/python/cpython/pull/23702) / python-paramspec-implementation | OPEN / IMPLEMENTATION | implements PEP-612 | createdAt=`2020-12-08T17:21:09Z` |
| 3 | [python/cpython#23702@merged](https://github.com/python/cpython/pull/23702) / python-paramspec-implementation | MERGED / IMPLEMENTATION | implements PEP-612 | mergedAt=`2020-12-24T04:33:49Z` |
| 4 | [python/cpython#25449@open](https://github.com/python/cpython/pull/25449) / python-paramspec-implementation | OPEN / IMPLEMENTATION | reverts python/cpython#23702 | createdAt=`2021-04-17T02:46:15Z` |
| 5 | [python/cpython#25449@merged](https://github.com/python/cpython/pull/25449) / python-paramspec-implementation | REVERT_MERGED / IMPLEMENTATION | reverts python/cpython#23702 | mergedAt=`2021-04-28T15:38:15Z` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `python-paramspec-implementation-c1` | 1 | python-paramspec-policy | GOVERNING: PEP-612 | PEP-612@final | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-paramspec-implementation-c2` | 2 | python-paramspec-implementation | UNRESOLVED | python/cpython#23702@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-paramspec-implementation-c3` | 3 | python-paramspec-implementation | GOVERNING: python/cpython#23702 | python/cpython#23702@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-paramspec-implementation-c4` | 4 | python-paramspec-implementation | GOVERNING: python/cpython#23702 | python/cpython#23702@merged + python/cpython#25449@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-paramspec-implementation-c5` | 5 | python-paramspec-policy | GOVERNING: PEP-612 | PEP-612@final + python/cpython#25449@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `python-paramspec-implementation-c6` | 5 | python-paramspec-policy, python-paramspec-implementation | MULTIPLE_GOVERNING: PEP-612, python/cpython#25449 | PEP-612@final + python/cpython#25449@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 17. `swift-coroutine-accessors` — Swift

Composition: **fully_real**. Repositories: swiftlang/swift, swiftlang/swift-evolution. Scenarios: implementation_vs_policy, proposal_while_current, revert_after_implementation, parallel_scopes, revert_without_policy_restoration, explicit_restoration.

Audit note: Accepted language policy is separate from an implementation PR, its rollback, and an explicit revert-of-revert restoration.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [SE-0474@accepted](https://github.com/swiftlang/swift-evolution/blob/0105e139a22938561c700cfbb89ddc3ebe402f0c/proposals/0474-yielding-accessors.md) / swift-yielding-accessor-policy | ACCEPTED / POLICY | none | `* Status: **Accepted**` |
| 2 | [swiftlang/swift#90516@open](https://github.com/swiftlang/swift/pull/90516) / swift-coroutine-accessor-implementation | OPEN / IMPLEMENTATION | implements SE-0474 | createdAt=`2026-07-08T20:10:24Z` |
| 3 | [swiftlang/swift#90516@merged](https://github.com/swiftlang/swift/pull/90516) / swift-coroutine-accessor-implementation | MERGED / IMPLEMENTATION | implements SE-0474 | mergedAt=`2026-08-12T09:01:48Z` |
| 4 | [swiftlang/swift#91475@open](https://github.com/swiftlang/swift/pull/91475) / swift-coroutine-accessor-implementation | OPEN / IMPLEMENTATION | reverts swiftlang/swift#90516 | createdAt=`2026-08-14T06:24:43Z` |
| 5 | [swiftlang/swift#91475@merged](https://github.com/swiftlang/swift/pull/91475) / swift-coroutine-accessor-implementation | REVERT_MERGED / IMPLEMENTATION | reverts swiftlang/swift#90516 | mergedAt=`2026-08-14T06:24:57Z` |
| 6 | [swiftlang/swift#91494@open](https://github.com/swiftlang/swift/pull/91494) / swift-coroutine-accessor-implementation | OPEN / IMPLEMENTATION | reverts swiftlang/swift#91475 | createdAt=`2026-08-14T16:52:37Z` |
| 7 | [swiftlang/swift#91494@merged](https://github.com/swiftlang/swift/pull/91494) / swift-coroutine-accessor-implementation | REVERT_MERGED / IMPLEMENTATION | reverts swiftlang/swift#91475 | mergedAt=`2026-08-19T19:44:26Z` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `swift-coroutine-accessors-c1` | 1 | swift-yielding-accessor-policy | GOVERNING: SE-0474 | SE-0474@accepted | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-coroutine-accessors-c2` | 2 | swift-coroutine-accessor-implementation | UNRESOLVED | swiftlang/swift#90516@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-coroutine-accessors-c3` | 3 | swift-coroutine-accessor-implementation | GOVERNING: swiftlang/swift#90516 | swiftlang/swift#90516@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-coroutine-accessors-c4` | 4 | swift-coroutine-accessor-implementation | GOVERNING: swiftlang/swift#90516 | swiftlang/swift#90516@merged + swiftlang/swift#91475@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-coroutine-accessors-c5` | 5 | swift-yielding-accessor-policy | GOVERNING: SE-0474 | SE-0474@accepted + swiftlang/swift#91475@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-coroutine-accessors-c6` | 7 | swift-coroutine-accessor-implementation | GOVERNING: swiftlang/swift#91494 | swiftlang/swift#91494@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `swift-coroutine-accessors-c7` | 7 | swift-yielding-accessor-policy, swift-coroutine-accessor-implementation | MULTIPLE_GOVERNING: SE-0474, swiftlang/swift#91494 | SE-0474@accepted + swiftlang/swift#91494@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 18. `kubernetes-gang-scheduling` — Kubernetes

Composition: **fully_real**. Repositories: kubernetes/enhancements, kubernetes/kubernetes. Scenarios: multi_hop_supersession, implementation_vs_policy, revert_without_policy_restoration, parallel_scopes.

Audit note: Current KEP registry explicitly encodes 583 -> 5832 -> 4671 replacement; implementation rollback does not alter policy status.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [KEP-583@current](https://github.com/kubernetes/enhancements/blob/c4f439c2dd4acb928094660be0ea771bf63f2b76/keps/sig-scheduling/583-coscheduling/kep.yaml) / kubernetes-gang-scheduling-policy | DRAFT / POLICY | none | `status: provisional` |
| 2 | [KEP-5832@current](https://github.com/kubernetes/enhancements/blob/c4f439c2dd4acb928094660be0ea771bf63f2b76/keps/sig-scheduling/5832-decouple-podgroup-api/kep.yaml) / kubernetes-gang-scheduling-policy | ACCEPTED / POLICY | replaces KEP-583 | `status: implementable`; `  - "/keps/sig-scheduling/583-coscheduling"` |
| 3 | [KEP-4671@current](https://github.com/kubernetes/enhancements/blob/c4f439c2dd4acb928094660be0ea771bf63f2b76/keps/sig-scheduling/4671-gang-scheduling/kep.yaml) / kubernetes-gang-scheduling-policy | ACCEPTED / POLICY | replaces KEP-5832, KEP-583 | `status: implementable`; `  - "/keps/sig-scheduling/5832-decouple-podgroup-api"`; `  - "/keps/sig-scheduling/583-coscheduling"` |
| 4 | [kubernetes/kubernetes#137464@merged](https://github.com/kubernetes/kubernetes/pull/137464) / kubernetes-podgroup-admission-implementation | MERGED / IMPLEMENTATION | implements KEP-5832 | mergedAt=`2026-03-19T16:02:34Z` |
| 5 | [kubernetes/kubernetes#139008@merged](https://github.com/kubernetes/kubernetes/pull/139008) / kubernetes-podgroup-admission-implementation | REVERT_MERGED / IMPLEMENTATION | reverts kubernetes/kubernetes#137464 | mergedAt=`2026-05-13T13:31:48Z` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `kubernetes-gang-scheduling-c1` | 1 | kubernetes-gang-scheduling-policy | NO_GOVERNING_DECISION | KEP-583@current | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `kubernetes-gang-scheduling-c2` | 2 | kubernetes-gang-scheduling-policy | GOVERNING: KEP-5832 | KEP-5832@current | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `kubernetes-gang-scheduling-c3` | 3 | kubernetes-gang-scheduling-policy | GOVERNING: KEP-4671 | KEP-4671@current | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `kubernetes-gang-scheduling-c4` | 4 | kubernetes-gang-scheduling-policy | GOVERNING: KEP-4671 | KEP-4671@current + kubernetes/kubernetes#137464@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `kubernetes-gang-scheduling-c5` | 5 | kubernetes-gang-scheduling-policy | GOVERNING: KEP-4671 | KEP-4671@current + kubernetes/kubernetes#139008@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `kubernetes-gang-scheduling-c6` | 5 | kubernetes-gang-scheduling-policy, kubernetes-podgroup-admission-implementation | MULTIPLE_GOVERNING: KEP-4671, kubernetes/kubernetes#139008 | KEP-4671@current + kubernetes/kubernetes#139008@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 19. `kubernetes-pleg-default` — Kubernetes

Composition: **fully_real**. Repositories: kubernetes/kubernetes. Scenarios: proposal_while_current, revert_after_implementation, revert_without_automatic_restoration, explicit_restoration.

Audit note: GitHub PR created/merged events establish proposal, implementation, rollback, and optional restoration.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [kubernetes/kubernetes#137909@open](https://github.com/kubernetes/kubernetes/pull/137909) / kubernetes-pleg-default | OPEN / IMPLEMENTATION | none | createdAt=`2026-03-19T17:08:51Z` |
| 2 | [kubernetes/kubernetes#137909@merged](https://github.com/kubernetes/kubernetes/pull/137909) / kubernetes-pleg-default | MERGED / IMPLEMENTATION | none | mergedAt=`2026-03-19T20:52:40Z` |
| 3 | [kubernetes/kubernetes#137946@open](https://github.com/kubernetes/kubernetes/pull/137946) / kubernetes-pleg-default | OPEN / IMPLEMENTATION | reverts kubernetes/kubernetes#137909 | createdAt=`2026-03-21T14:40:55Z` |
| 4 | [kubernetes/kubernetes#137946@merged](https://github.com/kubernetes/kubernetes/pull/137946) / kubernetes-pleg-default | REVERT_MERGED / IMPLEMENTATION | reverts kubernetes/kubernetes#137909 | mergedAt=`2026-03-25T09:58:21Z` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `kubernetes-pleg-default-c1` | 1 | kubernetes-pleg-default | NO_GOVERNING_DECISION | kubernetes/kubernetes#137909@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `kubernetes-pleg-default-c2` | 2 | kubernetes-pleg-default | GOVERNING: kubernetes/kubernetes#137909 | kubernetes/kubernetes#137909@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `kubernetes-pleg-default-c3` | 3 | kubernetes-pleg-default | GOVERNING: kubernetes/kubernetes#137909 | kubernetes/kubernetes#137909@merged + kubernetes/kubernetes#137946@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `kubernetes-pleg-default-c4` | 4 | kubernetes-pleg-default | GOVERNING: kubernetes/kubernetes#137946 | kubernetes/kubernetes#137946@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 20. `terraform-iam-role-chaining` — Terraform

Composition: **fully_real**. Repositories: hashicorp/terraform. Scenarios: proposal_while_current, revert_after_implementation, revert_without_automatic_restoration.

Audit note: Rollback explicitly says IAM role chaining may return later; that promise is not restoration.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [hashicorp/terraform#35720@open](https://github.com/hashicorp/terraform/pull/35720) / terraform-s3-iam-role-chaining | OPEN / IMPLEMENTATION | none | createdAt=`2024-09-12T17:49:14Z` |
| 2 | [hashicorp/terraform#35720@merged](https://github.com/hashicorp/terraform/pull/35720) / terraform-s3-iam-role-chaining | MERGED / IMPLEMENTATION | none | mergedAt=`2024-09-23T21:26:38Z` |
| 3 | [hashicorp/terraform#35827@open](https://github.com/hashicorp/terraform/pull/35827) / terraform-s3-iam-role-chaining | OPEN / IMPLEMENTATION | reverts hashicorp/terraform#35720 | createdAt=`2024-10-08T22:01:36Z` |
| 4 | [hashicorp/terraform#35827@merged](https://github.com/hashicorp/terraform/pull/35827) / terraform-s3-iam-role-chaining | REVERT_MERGED / IMPLEMENTATION | reverts hashicorp/terraform#35720 | mergedAt=`2024-10-09T00:36:58Z` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `terraform-iam-role-chaining-c1` | 1 | terraform-s3-iam-role-chaining | NO_GOVERNING_DECISION | hashicorp/terraform#35720@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `terraform-iam-role-chaining-c2` | 2 | terraform-s3-iam-role-chaining | GOVERNING: hashicorp/terraform#35720 | hashicorp/terraform#35720@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `terraform-iam-role-chaining-c3` | 3 | terraform-s3-iam-role-chaining | GOVERNING: hashicorp/terraform#35720 | hashicorp/terraform#35720@merged + hashicorp/terraform#35827@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `terraform-iam-role-chaining-c4` | 4 | terraform-s3-iam-role-chaining | GOVERNING: hashicorp/terraform#35827 | hashicorp/terraform#35827@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 21. `opentofu-minimal-image-docs` — OpenTofu

Composition: **fully_real**. Repositories: opentofu/opentofu. Scenarios: proposal_while_current, revert_after_implementation, revert_without_automatic_restoration, explicit_restoration.

Audit note: The second PR explicitly reverts the temporary rollback, so its merged record is the restoration authority.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [opentofu/opentofu#2403@open](https://github.com/opentofu/opentofu/pull/2403) / opentofu-minimal-image-docs | OPEN / IMPLEMENTATION | none | createdAt=`2025-01-21T12:53:14Z` |
| 2 | [opentofu/opentofu#2403@merged](https://github.com/opentofu/opentofu/pull/2403) / opentofu-minimal-image-docs | MERGED / IMPLEMENTATION | none | mergedAt=`2025-01-21T13:04:03Z` |
| 3 | [opentofu/opentofu#2404@open](https://github.com/opentofu/opentofu/pull/2404) / opentofu-minimal-image-docs | OPEN / IMPLEMENTATION | reverts opentofu/opentofu#2403 | createdAt=`2025-01-21T13:04:54Z` |
| 4 | [opentofu/opentofu#2404@merged](https://github.com/opentofu/opentofu/pull/2404) / opentofu-minimal-image-docs | REVERT_MERGED / IMPLEMENTATION | reverts opentofu/opentofu#2403 | mergedAt=`2025-04-25T11:22:19Z` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `opentofu-minimal-image-docs-c1` | 1 | opentofu-minimal-image-docs | NO_GOVERNING_DECISION | opentofu/opentofu#2403@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `opentofu-minimal-image-docs-c2` | 2 | opentofu-minimal-image-docs | GOVERNING: opentofu/opentofu#2403 | opentofu/opentofu#2403@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `opentofu-minimal-image-docs-c3` | 3 | opentofu-minimal-image-docs | GOVERNING: opentofu/opentofu#2403 | opentofu/opentofu#2403@merged + opentofu/opentofu#2404@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `opentofu-minimal-image-docs-c4` | 4 | opentofu-minimal-image-docs | GOVERNING: opentofu/opentofu#2404 | opentofu/opentofu#2404@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 22. `envoy-ext-authz-empty-values` — Envoy

Composition: **fully_real**. Repositories: envoyproxy/envoy. Scenarios: proposal_while_current, revert_after_implementation, revert_without_automatic_restoration.

Audit note: GitHub PR created/merged events establish proposal, implementation, rollback, and optional restoration.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [envoyproxy/envoy#45103@open](https://github.com/envoyproxy/envoy/pull/45103) / envoy-ext-authz-empty-values | OPEN / IMPLEMENTATION | none | createdAt=`2026-05-17T06:43:15Z` |
| 2 | [envoyproxy/envoy#45103@merged](https://github.com/envoyproxy/envoy/pull/45103) / envoy-ext-authz-empty-values | MERGED / IMPLEMENTATION | none | mergedAt=`2026-05-24T01:08:21Z` |
| 3 | [envoyproxy/envoy#45321@open](https://github.com/envoyproxy/envoy/pull/45321) / envoy-ext-authz-empty-values | OPEN / IMPLEMENTATION | reverts envoyproxy/envoy#45103 | createdAt=`2026-05-27T20:39:43Z` |
| 4 | [envoyproxy/envoy#45321@merged](https://github.com/envoyproxy/envoy/pull/45321) / envoy-ext-authz-empty-values | REVERT_MERGED / IMPLEMENTATION | reverts envoyproxy/envoy#45103 | mergedAt=`2026-05-27T23:37:06Z` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `envoy-ext-authz-empty-values-c1` | 1 | envoy-ext-authz-empty-values | NO_GOVERNING_DECISION | envoyproxy/envoy#45103@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `envoy-ext-authz-empty-values-c2` | 2 | envoy-ext-authz-empty-values | GOVERNING: envoyproxy/envoy#45103 | envoyproxy/envoy#45103@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `envoy-ext-authz-empty-values-c3` | 3 | envoy-ext-authz-empty-values | GOVERNING: envoyproxy/envoy#45103 | envoyproxy/envoy#45103@merged + envoyproxy/envoy#45321@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `envoy-ext-authz-empty-values-c4` | 4 | envoy-ext-authz-empty-values | GOVERNING: envoyproxy/envoy#45321 | envoyproxy/envoy#45321@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

### 23. `llvm-openmp-target-fast` — LLVM

Composition: **fully_real**. Repositories: llvm/llvm-project. Scenarios: proposal_while_current, revert_after_implementation, revert_without_automatic_restoration, explicit_restoration.

Audit note: GitHub PR created/merged events establish proposal, implementation, rollback, and optional restoration.

| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |
|---:|---|---|---|---|
| 1 | [llvm/llvm-project#205775@open](https://github.com/llvm/llvm-project/pull/205775) / llvm-openmp-target-fast | OPEN / IMPLEMENTATION | none | createdAt=`2026-06-25T11:11:44Z` |
| 2 | [llvm/llvm-project#205775@merged](https://github.com/llvm/llvm-project/pull/205775) / llvm-openmp-target-fast | MERGED / IMPLEMENTATION | none | mergedAt=`2026-08-03T13:21:04Z` |
| 3 | [llvm/llvm-project#213769@open](https://github.com/llvm/llvm-project/pull/213769) / llvm-openmp-target-fast | OPEN / IMPLEMENTATION | reverts llvm/llvm-project#205775 | createdAt=`2026-08-03T21:51:34Z` |
| 4 | [llvm/llvm-project#213769@merged](https://github.com/llvm/llvm-project/pull/213769) / llvm-openmp-target-fast | REVERT_MERGED / IMPLEMENTATION | reverts llvm/llvm-project#205775 | mergedAt=`2026-08-03T22:27:46Z` |
| 5 | [llvm/llvm-project#213911@open](https://github.com/llvm/llvm-project/pull/213911) / llvm-openmp-target-fast | OPEN / IMPLEMENTATION | reverts llvm/llvm-project#213769 | createdAt=`2026-08-04T11:29:17Z` |
| 6 | [llvm/llvm-project#213911@merged](https://github.com/llvm/llvm-project/pull/213911) / llvm-openmp-target-fast | REVERT_MERGED / IMPLEMENTATION | reverts llvm/llvm-project#213769 | mergedAt=`2026-08-04T12:05:39Z` |

| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |
|---|---:|---|---|---|---|
| `llvm-openmp-target-fast-c1` | 1 | llvm-openmp-target-fast | NO_GOVERNING_DECISION | llvm/llvm-project#205775@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `llvm-openmp-target-fast-c2` | 2 | llvm-openmp-target-fast | GOVERNING: llvm/llvm-project#205775 | llvm/llvm-project#205775@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `llvm-openmp-target-fast-c3` | 3 | llvm-openmp-target-fast | GOVERNING: llvm/llvm-project#205775 | llvm/llvm-project#205775@merged + llvm/llvm-project#213769@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `llvm-openmp-target-fast-c4` | 4 | llvm-openmp-target-fast | GOVERNING: llvm/llvm-project#213769 | llvm/llvm-project#213769@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `llvm-openmp-target-fast-c5` | 5 | llvm-openmp-target-fast | GOVERNING: llvm/llvm-project#213769 | llvm/llvm-project#213769@merged + llvm/llvm-project#213911@open | Authority follows the visible explicit lifecycle state; no later artifact is visible. |
| `llvm-openmp-target-fast-c6` | 6 | llvm-openmp-target-fast | GOVERNING: llvm/llvm-project#213911 | llvm/llvm-project#213911@merged | Authority follows the visible explicit lifecycle state; no later artifact is visible. |

## Required second-pass spot audit

This was a separate source-only pass after the first adjudication and before any benchmark inference. Each listed timeline was re-opened against the pinned proof above; no ground truth changed during this pass.

- Supersession (6; minimum 5): `python-db-api`, `python-wsgi`, `python-exception-context`, `python-hash-api`, `rust-tait-capture`, `rust-rpit-capture`.
- Revert (all 7; minimum 5): `python-paramspec-implementation`, `swift-coroutine-accessors`, `kubernetes-pleg-default`, `terraform-iam-role-chaining`, `opentofu-minimal-image-docs`, `envoy-ext-authz-empty-values`, `llvm-openmp-target-fast`.
- Proposal not authoritative (6; minimum 5): `rust-naked-functions`, `rust-global-allocator`, `rust-inline-const`, `go-type-parameters`, `go-loop-variables`, `go-range-functions`.
- Parallel scope (all 4): `swift-plugin-api`, `python-paramspec-implementation`, `swift-coroutine-accessors`, `kubernetes-gang-scheduling`.
- Ambiguous (all 3): `rust-inline-const`, `rust-drop-check`, `go-range-functions`.

## Pre-output exclusions

These candidates were excluded or narrowed before any system output. Qualified partial replacements remain in the benchmark only as unresolved broad-scope checkpoints.

| Candidate | Pre-output reason |
|---|---|
| OpenTofu context propagation #835 | Promised revert-of-revert never occurred; later PR explicitly says so, making a restoration checkpoint indefensible. |
| Terraform IAM role chaining future reintroduction | Rollback promises a future return but no source-grounded accepted restoration was found. |
| Swift SE-0030 historical acceptance checkpoint | Primary status says Withdrawn and decision notes indicate rejection; no authoritative pre-withdrawal state was assumed. |
| Rust RFC 2203 broad replacement | Source says mostly superseded and preserves a simpler case; broad winner is adjudicated unresolved, not forced. |
| Rust RFC 769 broad replacement | Source says partially superseded; broad winner is adjudicated unresolved, not forced. |

## Independence attestation

The collection order was source discovery → source-grounded adjudication → manual audit → dataset freeze. The prospective run directory did not exist during those steps. Once this ledger and the byte manifest are committed, inclusion, ground truth, scenario tags, prompts, model settings, and resolver bytes are immutable for the run.
