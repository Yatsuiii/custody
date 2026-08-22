# Gate 1B — Prior-Work Boundary for Missing Provenance

Status: design and related-work audit only. No receipt, signature, capability,
collector, gateway, or Architecture A code is implemented by this artifact.

## Frozen lineage

- Gate 1A classification: `STRUCTURALLY-INDISTINGUISHABLE`.
- Gate 1A commit: `4ed095b14dcfc099ed50dd71f28226f24209fe90`.
- Gate 1 preregistration: `c561e253f97822d45d0a31bb68163738c6a36f4f`.
- Gate 1 execution: `37becdfd8163f9520c7af3e7eee435f21b2c27f8`.
- Gate 1 canonical digest:
  `ef0d8a0aebc1e63acb530774fc0aaf1f860c90e312ac4234b04eb4f4278e358e`.
- Pinned attack source:
  `yedidel/mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1`.

Gate 1A found that the trusted benign relay and the tool-echo attack have the
same authority-bearing structural projection. A returned value and its copied
action target differ, but neither is authenticated provenance. This audit asks
whether a non-oracular authority proof is already known, not whether a new
textual detector can be added.

## Audit rule

The missing primitive must bind a specific authority-bearing upstream object or
claim to a trusted issuer. A bare label such as `origin=trusted`, a trusted
relay identity, or a scorer-populated `true_origin` field is not sufficient.

For each prior system below, the audit records:

- primitive and issuer/verifier;
- trust root and relay minting power;
- identity versus action authority;
- transformation, generation, revocation, and multi-parent behavior;
- deployment assumptions; and
- whether it separates the Gate 1 benign and tool-echo cases.

The assessment distinguishes what a paper claims from what this repository has
actually reproduced. No paper result is treated as a local measurement.

## Primary prior-work records

### TMA-NM / `mem-inv-bench`

Sources: [paper](https://arxiv.org/abs/2606.24322), [pinned
repository](https://github.com/yedidel/mem-inv-bench/tree/63f1359d677efbe1a65b982b2a54cabfec97f1e1),
and the pinned fixture
[`code/laundering.py`](https://github.com/yedidel/mem-inv-bench/blob/63f1359d677efbe1a65b982b2a54cabfec97f1e1/code/laundering.py).

| Boundary question | Finding |
|---|---|
| Exact primitive | Write-time origin binding plus non-malleable propagation of origin-bound authority; the synthetic helper carries `true_origin` and the official monitor consumes it. |
| Issuer | The paper assumes an authenticated origin-labeling monitor at the trusted write boundary. The pinned `tool_echo` fixture materializes the field itself for the benchmark. |
| Verifier | TMA-NM monitor/authorization logic checks origin and action class before dispatch. |
| Trust root | The origin monitor and the trusted channel that supplies its label; a compromised trusted tool is explicitly the laundering threat. |
| Can a relay mint it? | Not soundly. A relay may forward an origin assertion, but cannot be allowed to relabel an attacker value as trusted. |
| Identity or authority? | Origin is used as an authority-bearing input to action eligibility, not merely as an audit identity. |
| Transform survival | TMA-NM's central claim is non-malleable propagation through the benchmark's transformations; cross-agent relay is outside the stated scope. |
| Revocation/generation | No E2F-style per-policy-key generation or retrospective source-compromise revocation is demonstrated by the pinned gate. |
| Multi-parent | The flat benchmark item model does not provide the E2G support-union semantics needed here. |
| Deployment assumption | An authenticated origin monitor/labeling boundary exists and is trusted. |
| Gate 1 problem | Yes. `true_origin=trusted` versus `tool_echo_untrusted` is the missing distinguishing bit. |

**Boundary conclusion.** The minimum P2-style receipt is substantively the
same family as TMA-NM's authenticated origin monitor. It must not be renamed
and claimed as a new provenance primitive. The repository's Gate 1 result
correctly labels B3 `ORACLE-COUPLED` because the synthetic fixture supplies
the field that B6 cannot derive from the common observation.

The pinned fixture's construction is auditable at
[`laundering.py` lines 19–21](https://github.com/yedidel/mem-inv-bench/blob/63f1359d677efbe1a65b982b2a54cabfec97f1e1/code/laundering.py#L19-L21)
and
[`build_items` lines 81–97](https://github.com/yedidel/mem-inv-bench/blob/63f1359d677efbe1a65b982b2a54cabfec97f1e1/code/laundering.py#L81-L97);
the helper reads the origin field in
[`authorized` lines 122–143](https://github.com/yedidel/mem-inv-bench/blob/63f1359d677efbe1a65b982b2a54cabfec97f1e1/code/laundering.py#L122-L143).

The paper also frames origin binding as a necessary security boundary and
separates that boundary from later contributions such as non-malleable
propagation. That leaves a possible composition question, not a new
origin-label invention.

### MemLineage

Sources: [paper](https://arxiv.org/abs/2605.14421), [repository recorded by the
related-work audit](https://github.com/amurlaniakea/memlineage), pinned in the
local audit as `73e770478f044323052a402795690c9d4e62f804`.

| Boundary question | Finding |
|---|---|
| Exact primitive | Cryptographic provenance: per-principal Ed25519-signed entries in an RFC 6962-style Merkle log, plus a weighted derivation DAG. |
| Issuer/verifier | A principal signs its own memory entry; the MemLineage modules verify signatures/log inclusion and evaluate the derivation graph. |
| Trust root | Per-principal signing keys and the log/verifier configuration. |
| Relay minting | A relay cannot forge a source signature, but a trusted signer can still create an incorrect claim; the signer is therefore a real TCB assumption. |
| Identity or authority? | The signature establishes provenance and the gate uses ancestry to restrict sensitive action; the paper's policy turns provenance into action authority. |
| Transform survival | The derivation DAG records influencing entries; the policy refuses sensitive actions whose justification descends from an external ancestor. |
| Revocation/generation | The paper describes chain-of-custody enforcement, but no E2F generation vector or source-policy ABA rule is part of this audit's selected primitive. |
| Multi-parent | The weighted DAG can represent multiple influences; the exact all-parent/no-wash rule required by E2G is not assumed without an adapter audit. |
| Deployment | Key management, append-only logging, and a verifier are required. The independent implementation was not used as a Gate 1 baseline. |
| Gate 1 problem | It can provide a stronger answer than an ID-only handle, but it is already a known cryptographic provenance/lineage solution, not a novel receipt idea. |

MemLineage is the closest non-TMA-NM memory-specific comparator. A future
evaluation must compare against it where it can be legally and reproducibly
run, rather than claiming a receipt is novel because its field names differ.

### PACT — provenance-aware capability contracts

Source: [paper](https://arxiv.org/abs/2605.11039).

PACT assigns semantic roles to tool arguments, tracks value provenance across
replanning, and checks role-specific capability contracts. Its paper reports
that the strongest results use oracle provenance and identifies provenance
inference/contract synthesis as the deployment bottleneck. This is a direct
novelty threat: it binds provenance at the authority-bearing argument level,
which is close to the Gate 1 missing bit. PACT is not a durable policy-
generation receipt, but a claimed distinction based only on naming would not
survive this comparison.

| Boundary question | Finding |
|---|---|
| Issuer/verifier | Runtime monitor and capability-contract policy; the paper's oracle-provenance condition is stronger than Gate 1's shared observation. |
| Relay minting | Not permitted by the contract model if the provenance monitor is trusted; deployment depends on obtaining correct argument provenance. |
| Authority | Explicitly action-argument authority, not just a provenance log. |
| Transform/revocation/generation | Cross-step propagation is central; E2F generation identity, source-compromise revocation, and durable multi-parent support are not established by this audit. |
| Gate 1 problem | Yes, at argument/value provenance level, but with a different trusted-instrumentation assumption. |

### C2PA and authenticated content provenance

Sources: [C2PA specification](https://spec.c2pa.org/specifications/specifications/1.0/specs/C2PA_Specification.html),
[specification repository](https://github.com/c2pa-org/specifications).

C2PA signs provenance manifests/assertions and binds them to content or an
asset through cryptographic claims. It provides a useful P2 analogue for
object/value binding, issuer identity, and verification. It does not by itself
define Custody's action caps, per-policy-key generation freshness, support-root
closure, or selective authority revocation. A C2PA-style signature would need
an additional authority-policy claim to become an action receipt.

| Boundary question | Finding |
|---|---|
| Issuer/verifier | An asserting signer issues a manifest; a verifier checks signatures, claims, and trust configuration. |
| Relay minting | A relay may carry a manifest but cannot alter a signed assertion without detection. |
| Identity or authority? | Primarily content provenance and signer identity; action authority is application policy, not supplied by C2PA alone. |
| Transform/multi-parent | Assertions can describe edits and relationships; exact REGISTERED/FREEFORM authority semantics are application-specific. |
| Revocation/generation | Credential trust and assertion validity exist, but E2F/E2G policy-key generation semantics are not supplied. |
| Gate 1 problem | It can bind a benign upstream object, but it is not by itself an action-authority solution. |

### Capability and delegation systems: Macaroons, SPKI/SDSI, and agent
credentials

Sources: [Macaroons](https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/),
[SPKI RFC 2693](https://www.rfc-editor.org/rfc/rfc2693.html), and the
authenticated-delegation discussion in [PMLR 267
South](https://proceedings.mlr.press/v267/south25a.html).

Macaroons and SPKI/SDSI provide signed/delegated authorization with caveats,
subjects, issuers, and bounded scope. They are strong P3 prior art. A
capability bound to an immutable upstream record, action scope, value/object
commitment, and policy generation can solve the Gate 1 forgery cases. Once so
bound, however, it is functionally an authority receipt (P2), not a new
concept. Unbound capabilities only prove that a holder may act; they do not
prove that a particular tool-returned value is the holder's authorized value.

| Boundary question | Finding |
|---|---|
| Issuer/verifier | Policy authority/issuer creates a delegation; the gateway verifies the chain and caveats. |
| Relay minting | A relay can delegate only what its capability permits; it cannot enlarge scope if caveats are enforced. |
| Identity or authority? | Authority delegation, which is stronger than identity, but object/value binding must be added for this attack. |
| Transform/revocation/generation | Caveats can encode scope/expiry and revocation handles; E2F/E2G exact generation and support closure remain application policy. |
| Gate 1 problem | Yes after object/value binding; the family is established prior art. |

### Fides, CaMeL, and W3C PROV

Sources: [Fides](https://arxiv.org/abs/2505.23643), [CaMeL](https://arxiv.org/abs/2503.18813),
and [W3C PROV](https://www.w3.org/TR/prov-primer/).

Fides provides IFC-style integrity labels and policy enforcement; CaMeL
provides capability/data-flow mediation for tool calls; W3C PROV standardizes
descriptive entity/activity/agent provenance. These are relevant baselines but
do not, on their own, provide the exact cryptographically authenticated,
object-bound action authority receipt required by Gate 1. Labels or a
descriptive graph can be copied or laundered by a trusted relay unless their
issuer and authority binding are separately trusted. They therefore do not
make P2 novel.

## Cross-system conclusion

The minimum information needed to separate the two Gate 1 cases is not
`upstream_trusted=true`. It is a verifiable claim of the form:

> trusted issuer `I` granted cap `c` for action scope `s` over immutable
> authority-bearing object/claim `o`, under policy key `K` at generation `g`.

TMA-NM already supplies the essential origin-authority distinction under its
authenticated monitor assumption. MemLineage supplies signed provenance and
derivation enforcement. Capability systems supply delegation and caveats.
PACT is a particularly close argument-level provenance/capability threat.

Accordingly, the provenance primitive itself is **not** a defensible novelty
claim. The only plausible contribution left for Custody is composition with
the already measured properties that those systems do not establish as one
package here: derivation-stable authority, per-key generation invalidation,
post-hoc selective revocation/repair, multi-parent support preservation,
cross-agent persistence, and real durable recovery.

## Audit disposition

- P0 is the negative baseline and reproduces Gate 1A's indistinguishability.
- P1 is insufficient without cryptographic/object binding.
- P2/P3 are known primitive families; a P2-style receipt is the minimum
  candidate to falsify next.
- P4 adds endorsement surface but does not remove the need for a trusted root.
- P5 is rejected because payload semantics are outside the frozen authority
  boundary.
- Selected design verdict: `COMPOSITION-NOVELTY-ONLY`.

No candidate is implemented or authorized by this audit.
