# Action-compliance task discovery funnel

This is a search ledger, not an acceptance ledger. A Stage-A row records only a
cheap lead. Authority claims remain hypotheses until Stage C proves them from
primary sources and pins code.

## Stage A — cheap discovery pool

The pool deliberately includes likely failures so structural triage can reject
them without clones, builds, or coding-agent work.

| ID | Repository / source | Link or identifier | Rough category | One-sentence reason it may be useful |
|---|---|---|---|---|
| A01 | django/django | [ticket #27236](https://code.djangoproject.com/ticket/27236) | SUPERSEDED_DESIGN | `Meta.index_together` remained functional after Django explicitly replaced it with `Meta.indexes`. |
| A02 | golang/go | [issue #61626](https://github.com/golang/go/issues/61626) + [#61900](https://github.com/golang/go/issues/61900) | PROPOSAL_NOT_ACCEPTED | A slice-returning maps helper was declined while iterator-returning helpers were accepted. |
| A03 | opentofu/opentofu | `rfc/20260808-ignore-provider-meta.md` | PARTIAL_ACCEPTANCE | The RFC appears to accept warning now while deferring ignore/removal behavior to a future minor release. |
| A04 | kubernetes/kubernetes | [PR #141182](https://github.com/kubernetes/kubernetes/pull/141182), KEP-4671 | SUPERSEDED_DESIGN | PlacementFeasible is described as replacing Permit for gang scheduling, but corroborating implementation was still open in salvaged notes. |
| A05 | django/django | `Meta.unique_together` documentation | AUTHORITY_NOT_EXPLICIT | Modern docs recommend `UniqueConstraint`, but the authority transition may never have been accepted. |
| A06 | django/deps | DEP 0009 | WRONG_AUTHORITY_SCOPE | Accepted async design assigns WebSockets to Channels rather than Django core. |
| A07 | django/deps | DEP 0005 / `MiddlewareMixin` | IMPLEMENTATION_VS_POLICY | A transition implementation could be mistaken for policy governing new middleware. |
| A08 | django/django | ticket #26029 / commit `32940d390a` | SUPERSEDED_DESIGN | `DEFAULT_FILE_STORAGE` and `STATICFILES_STORAGE` were replaced by `STORAGES`. |
| A09 | rust-lang/rust | PR #149375 / revert #154930 | REVERTED_DESIGN | Const checks were merged and later reverted with an explicit regression rationale. |
| A10 | rust-lang/rust | PR #148937 / revert #150096 | EXPLICIT_RESTORATION | `BorrowedBuf` initialized-byte tracking was removed and later restored after performance fallout. |
| A11 | kubernetes/kubernetes | PR #127300 / revert #128694 | REVERTED_DESIGN | Kubelet resize error propagation has a concrete merge/revert history and materially different code. |
| A12 | kubernetes/kubernetes | PR #140448 / revert #140990 | IMPLEMENTATION_VS_POLICY | EventBroadcaster concurrency code was reverted, though it may be only a race fix rather than authority. |
| A13 | kubernetes/kubernetes | PR #137274 | REVERTED_DESIGN | `maxLength` graduation was reverted, but the code effect may be only metadata. |
| A14 | kubernetes/kubernetes | PR #139008 / KEP-5832 | REVERTED_DESIGN | The PodGroup admission plugin was removed wholesale after initial acceptance. |
| A15 | pypa/packaging | PR #828 / PEP 639 | PARTIAL_ACCEPTANCE | License-expression parsing intentionally left mutual-exclusion policy to callers. |
| A16 | python/peps | PEP 345 → PEP 426 → PEP 566 | SUPERSEDED_DESIGN | A withdrawn metadata redesign sits between an older accepted format and its later replacement. |
| A17 | pypa/packaging | PEP 513/571/599/600, packaging#293 | PARALLEL_DECISIONS | Legacy manylinux tags remain recognizable while PEP 600 defines the forward compatibility policy. |
| A18 | python/peps / PyPA | PEP 609 / PEP 772 | MENTION_WITHOUT_TRANSITION | A later packaging-governance proposal may coexist with or supersede only part of PEP 609. |
| A19 | pypa/pip / python/peps | [PEP 722](https://peps.python.org/pep-0722/) → [PEP 723](https://peps.python.org/pep-0723/), pip PR #12891 | SUPERSEDED_DESIGN | Both define runnable-script dependencies, but only the TOML block syntax became authoritative. |
| A20 | python/cpython | PEP 563 → PEP 649 → PEP 749 | SUPERSEDED_DESIGN | Postponed annotation evaluation has multiple explicit replacement transitions with observable runtime behavior. |
| A21 | pypi/warehouse / pip | PEP 381 / PEP 449 / PEP 464 | PARALLEL_DECISIONS | Mirror discovery and mirror authenticity occupy separate valid scopes that an implementation could collapse. |
| A22 | python/cpython | PEP 597, PR #25103 / revert #25108 | IMPLEMENTATION_VS_POLICY | A CPython implementation was reverted while the accepted encoding policy remained in force. |
| A23 | python/cpython | PEP 489, PR #19084 / revert #19128 | IMPLEMENTATION_VS_POLICY | A module conversion was reverted without reverting the governing multi-phase-initialization policy. |
| A24 | rust-lang/rust | PR #151603 / revert #152963 / PR #152971 | EXPLICIT_RESTORATION | `str::as_str` was merged, reverted, then proposed again, making restoration timing explicit. |
| A25 | elastic/elasticsearch | PR #147071 / revert #147360 | REVERTED_DESIGN | Multi-value behavior changed and was reverted in a mature Java subsystem. |
| A26 | kubernetes/enhancements | KEP-575 CRD defaulting | PARTIAL_ACCEPTANCE | Accepted defaulting rules include rejected alternatives that could alter generated API behavior. |
| A27 | kubernetes/enhancements | KEP-279 node labels | WRONG_AUTHORITY_SCOPE | Node-label restrictions distinguish Kubernetes-owned prefixes from user-scoped labels. |
| A28 | kubernetes/enhancements | KEP-1205 bound service-account tokens | SUPERSEDED_DESIGN | Projected expiring tokens explicitly replace long-lived secret-backed behavior. |
| A29 | kubernetes/enhancements | KEP-2718 client exec proxy | WRONG_AUTHORITY_SCOPE | Proxy configuration and credential-plugin authority may apply at different client boundaries. |
| A30 | kubernetes/enhancements | KEP-2133 kubelet credential providers | PARTIAL_ACCEPTANCE | Credential-provider matching/caching rules contain scoped accepted and rejected alternatives. |
| A31 | kubernetes/enhancements | KEP-2332 pruning unknown fields | PARALLEL_DECISIONS | Structural-schema pruning and preserve-unknown-fields behavior coexist in explicit scopes. |
| A32 | kubernetes/enhancements | KEP-2382 exec-based secret generation | PROPOSAL_NOT_ACCEPTED | A proposed generator design may have an implementable but never-adopted API surface. |
| A33 | kubernetes/enhancements | KEP-647 API server tracing | PARTIAL_ACCEPTANCE | Tracing propagation and backend/export policy are separable accepted scopes. |
| A34 | kubernetes/enhancements | KEP-1790 pod resize | PARTIAL_ACCEPTANCE | In-place resize has explicit deferred behaviors and implementation-stage boundaries. |
| A35 | kubernetes/enhancements | KEP-3488 CEL admission | WRONG_AUTHORITY_SCOPE | CEL expressions apply at selected admission-policy scopes, not every validation path. |
| A36 | kubernetes/enhancements | KEP-2523 resourceVersion semantics | PARALLEL_DECISIONS | Exact, not-older-than, and cache-serving semantics coexist by request mode. |
| A37 | kubernetes/enhancements | KEP-2885 unknown-field validation | PARTIAL_ACCEPTANCE | Server-side field validation has warn/strict/ignore modes with staged defaults. |
| A38 | kubernetes/enhancements | KEP-2876 CRD validation expressions | WRONG_AUTHORITY_SCOPE | CRD CEL rules have explicit type/scope limits that a neighboring validator could over-apply. |
| A39 | kubernetes/enhancements | KEP-5229 asynchronous API calls | PROPOSAL_NOT_ACCEPTED | A recent design may expose attractive unaccepted API machinery. |
| A40 | kubernetes/enhancements | KEP-1979 object storage | PROPOSAL_NOT_ACCEPTED | The abandoned/proposed storage backend would materially change persistence code if treated as policy. |
| A41 | swiftlang/swift-evolution | SE-0009 | PROPOSAL_NOT_ACCEPTED | A rejected language proposal could still suggest a plausible compiler/library implementation. |
| A42 | swiftlang/swift-evolution | commonly-rejected change later accepted as SE-0380 | EXPLICIT_RESTORATION | A formerly discouraged pattern only becomes valid after a named accepted proposal. |
| A43 | swiftlang/swift-evolution | SE-0264 revision history | PARTIAL_ACCEPTANCE | A proposal was returned for revision before acceptance, potentially leaving rejected portions. |
| A44 | envoyproxy/envoy | runtime-guard policy / deprecation docs | WRONG_AUTHORITY_SCOPE | Runtime guards for risky changes may be mistaken for permanent API policy. |
| A45 | hashicorp/terraform | import-in-plan design issues | PROPOSAL_NOT_ACCEPTED | Proposed import planning behavior has multiple issue-era designs before implementation authority. |
| A46 | opentofu/opentofu | issue #1042 constant locals/variables | PARTIAL_ACCEPTANCE | Interpolation was discussed while label interpolation was explicitly out of scope. |
| A47 | opentofu/opentofu | issue #3414 new runtime | IMPLEMENTATION_VS_POLICY | A walking skeleton/dead-code phase can be mistaken for an activated architecture. |
| A48 | pypa/pip | PR #12891 / PEP 723 | SUPERSEDED_DESIGN | Pip's implementation offers a bounded Python task for distinguishing PEP 723 from rejected PEP 722 syntax. |
| A49 | pypa/packaging | issue #293 / PEP 600 | PARALLEL_DECISIONS | Packaging's tag parser can test coexistence of legacy tags and perennial policy without compiling a large project. |
| A50 | tokio-rs/axum | PR #2645 | SUPERSEDED_DESIGN | Route capture syntax changed from `/:id` to `/{id}` with explicit compatibility behavior. |
| A51 | tokio-rs/axum | PR #2974 | SUPERSEDED_DESIGN | `WebSocket::close` was removed in favor of sending an explicit close message. |
| A52 | tokio-rs/axum | PR #2475 | PARTIAL_ACCEPTANCE | Optional extractors stopped swallowing all errors, preserving only missing-value optionality. |
| A53 | tokio-rs/axum | PR #2956 | WRONG_AUTHORITY_SCOPE | Host extraction moved to `axum-extra`, creating an explicit core-versus-extra scope boundary. |
| A54 | tokio-rs/axum | issue/PR #3190, yanked 0.8.2 | EXPLICIT_RESTORATION | A breaking route behavior caused a yank and may have been restored only after a targeted fix. |
| A55 | python/peps / packaging tools | PEP 665 → PEP 751 | SUPERSEDED_DESIGN | A rejected lock-file proposal was followed by an accepted successor with materially different format choices. |
| A56 | python/peps / Python launchers | PEP 582 | PROPOSAL_NOT_ACCEPTED | The rejected `__pypackages__` import convention remains technically implementable and attractive to tooling authors. |
| A57 | golang/go | [issue #51082](https://github.com/golang/go/issues/51082) → [accepted reconsideration #54312](https://github.com/golang/go/issues/54312) | EXPLICIT_RESTORATION | `go/doc` changed ASCII double-prime text into a closing quote, and an explicit later proposal accepted restoring non-mutating behavior. |

Stage-A count: **57**.

## Cheap-discovery cost accounting (checkpoint 1)

- 52 direct web-search queries in thirteen deterministic batches; twelve
  direct primary-page opens.
- Local `rg`, `git log`, `git ls-tree`, and JSON metadata inspection over the
  salvaged repository and the pre-existing authority-timeline branch.
- GitHub CLI authentication was checked once and found unavailable; no auth
  mutation was attempted.
- Repository clones: 0.
- Builds/tests: 0.
- Coding agents, research agents, or subagents: 0.
- Expensive/deep model calls for discovery: 0.

## Stage B — structural triage

Legend: `Y` is already supported by cheap evidence, `?` must be proved in
Stage C, and `N` is a gate failure. G1 is allowed to remain `?` only for a
promoted candidate; no accepted task may retain a question mark.

| Serious ID | Stage-A lead | G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 | G9 | G10 | Triage decision |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| C14 | A01 Django `index_together` | Y | Y | Y | Y | Y | Y | Y | Y | Y | ? | PROMOTE: salvaged complete fixture needs fresh semantic-grader replay. |
| C15 | A02 Go maps slice helper | Y | Y | Y | Y | Y | Y | Y | Y | Y | ? | PROMOTE: salvaged complete fixture needs fresh typed/AST replay. |
| C16 | A03 OpenTofu `provider_meta` | Y | ? | Y | ? | Y | Y | Y | Y | Y | ? | PROMOTE: finish missing task/context and prove RFC authority plus replay. |
| C17 | A04 Kubernetes gang scheduling | Y | N | ? | ? | ? | ? | ? | ? | ? | ? | REJECT `AUTHORITY_NOT_EXPLICIT`: the salvaged corroborating removal PR was open, so a KEP direction alone does not prove the proposed activation is current code authority. |
| C18 | A08 Django `STORAGES` | Y | Y | Y | Y | Y | Y | Y | Y | Y | ? | REJECT `DUPLICATE_SCENARIO`: same repo, mechanism, and SUPERSEDED_DESIGN shape as C14; it adds no authority/category diversity. |
| C19 | A16 metadata 1.x/2.x redesign | ? | Y | ? | Y | N | ? | ? | ? | ? | ? | REJECT `NO_EXECUTABLE_TASK`: PEP 426 was withdrawn in favor of 566, but no bounded implementation target was found where both interpretations implement the same ordinary request. |
| C20 | A17 packaging manylinux policy | ? | Y | Y | Y | Y | ? | Y | Y | Y | ? | PROMOTE: bounded tag parser/generator may expose legacy/perennial coexistence. |
| C21 | A19/A48 pip PEP 722/723 | ? | Y | Y | Y | Y | ? | Y | Y | Y | ? | PROMOTE: pip has a bounded script-metadata parser and targeted tests. |
| C22 | A20 annotation semantics | ? | Y | Y | ? | Y | ? | Y | ? | ? | N | REJECT `TOOLCHAIN_COST_TOO_HIGH`: validating alternative runtime annotation semantics requires a CPython build and cross-version behavior matrix, not a bounded package test. |
| C23 | A21 PyPI mirror decisions | ? | Y | Y | Y | Y | ? | Y | ? | ? | ? | PROMOTE: inspect old pip/warehouse mirror code for a bounded parallel-scope patch. |
| C24 | A22 PEP 597 implementation revert | ? | Y | Y | Y | Y | ? | Y | ? | ? | ? | PROMOTE: test whether pure-Python `_pyio` can provide a bounded policy-vs-implementation task. |
| C25 | A23 PEP 489 `_weakref` revert | ? | Y | Y | Y | Y | ? | Y | ? | ? | ? | PROMOTE: inspect whether a single extension-module test can avoid a full interpreter rebuild. |
| C26 | A24 Rust `str::as_str` restoration | Y | Y | Y | Y | Y | Y | Y | ? | ? | N | REJECT `TOOLCHAIN_COST_TOO_HIGH`: the authority-sensitive change is in rustc/libstd and needs the rust bootstrap/compiletest path already found infeasible. |
| C27 | A31 Kubernetes pruning scopes | ? | Y | Y | ? | Y | ? | Y | ? | ? | N | REJECT `CONTEXT_TOO_LARGE`: CRD schema, apiserver, client compatibility, and versioned KEP state cannot be safely reduced to a replayable narrow task. |
| C28 | A37 Kubernetes field-validation modes | ? | Y | Y | ? | Y | ? | Y | ? | ? | N | REJECT `BUILD_INFEASIBLE`: the meaningful behavior crosses apiserver request handling and field-manager integration rather than a targetable leaf package. |
| C29 | A46 OpenTofu constant labels | ? | ? | Y | ? | Y | ? | Y | ? | ? | ? | PROMOTE: explicit out-of-scope label interpolation may yield a wrong-scope task if source boundaries are small. |
| C30 | A47 OpenTofu new runtime skeleton | ? | ? | ? | N | ? | ? | ? | ? | ? | ? | REJECT `IMPLEMENTATION_VS_POLICY`/`CONTEXT_TOO_LARGE`: a walking skeleton is evidence of implementation staging, but the full runtime migration is too broad and does not define one governing coding choice. |
| C31 | A50 axum route syntax | ? | Y | Y | Y | Y | Y | Y | Y | Y | ? | PROMOTE: small Rust package tests can determine whether the old syntax is a viable wrong patch or simply panics. |
| C32 | A52 axum optional extractors | ? | Y | Y | Y | Y | Y | Y | Y | Y | ? | PROMOTE: accepted separation of absence from malformed-input errors is behaviorally testable. |
| C33 | A55 PEP 665/751 lock files | ? | Y | Y | ? | Y | ? | Y | ? | ? | ? | PROMOTE: find a small packaging-tool parser snapshot with both formats plausibly implementable. |
| C34 | A57 Go doc quote restoration | ? | Y | Y | Y | Y | Y | Y | Y | Y | ? | PROMOTE: accepted restoration is a leaf `go/doc` behavior with a host-toolchain test path. |

Stage-B serious candidates: **21** (C14-C34). Promoted to Stage C: **13**.
Rejected at Stage B: **8**. Together with the thirteen salvaged serious
candidates already recorded in `ACTION_COMPLIANCE_LEDGER.md`, the cumulative
serious-candidate count is **34**; the scarcity stop threshold is therefore
already enforceable without pretending every Stage-A lead was serious.

## Stage C — deep validation

Deep-validation queue, in cost order:

1. C14 Django and C15 Go: replay salvaged fixtures under the strengthened
   completion rule.
2. C16 OpenTofu: complete missing primary context, task, and test-bearing
   sanity patches.
3. C20 packaging, C21 pip, C24 CPython `_pyio`, C34 Go doc: cheap Python/Go
   leaf-package validation.
4. C31/C32 axum: one shared shallow clone, targeted crate tests only.
5. C23 mirrors, C25 `_weakref`, C29 OpenTofu labels, C33 lock files: validate
   only if earlier finalists do not reach the inventory gate.

### Deep-validation checkpoint 1

| Candidate | Result | Evidence-producing work |
|---|---|---|
| C14 Django | ACCEPT | Fresh pinned setup; applied-state Python AST grader; real schema tests; A `(true,true,true)`, B `(true,false,false)`. |
| C15 Go maps | ACCEPT | Fresh pinned overlay; applied-state Go AST probe; real package tests; A `(true,true,true)`, B `(true,true,false)`. |
| C16 OpenTofu `provider_meta` | REJECT `AUTHORITY_NOT_EXPLICIT` | Pinned shallow checkout and primary RFC read; discovered that purported acceptance PR #4436 remains open. No patches or tests run. |
| C20 packaging | CONTINUE | Primary PEP/PR evidence and pre-merge pin established; narrow implementation/grader feasibility not yet proved. |
| C21 pip | ACCEPT | Fresh pinned shallow checkout; behavioral PEP 723/722 probe and unit tests; A `(true,true,true)`, B `(true,true,false)`. |

No benchmark arm, coding agent, subagent, or model-generated patch was used.
The three accepted tasks use hand-built sanity patches only. C16 was rejected
instead of repairing its authority premise after fixture construction.
