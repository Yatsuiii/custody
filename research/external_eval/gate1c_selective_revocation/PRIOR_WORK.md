# Gate 1C — Prior-Work Boundary

Status: related-work analysis only. No implementation or novelty claim is
authorized.

The local Gate 1B boundary audit is the source index for this review:
`research/external_eval/gate1b_provenance/PRIOR_WORK_BOUNDARY.md`. It cites the
primary papers/specifications and pinned repositories below. The present
question is selector granularity and descendant invalidation, not whether
signed provenance exists.

## TMA-NM / mem-inv-bench

Primary sources: [paper](https://arxiv.org/abs/2606.24322) and pinned
[`mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1`](https://github.com/yedidel/mem-inv-bench/tree/63f1359d677efbe1a65b982b2a54cabfec97f1e1).

TMA-NM supplies an authenticated-origin assumption and non-malleable propagation
within its benchmark model. The Gate 1B audit found no demonstrated
per-receipt, per-generation, post-hoc source-compromise revocation equivalent
to the Gate 1C target. It remains the closest origin-bound authority boundary,
but Gate 1C must not claim that root revocation is new merely because TMA-NM's
public fixture does not expose this selector.

## MemLineage

Primary sources: [paper](https://arxiv.org/abs/2605.14421) and the recorded
repository [amurlaniakea/memlineage](https://github.com/amurlaniakea/memlineage).

MemLineage provides signed entries, an append-oriented log, and a derivation
DAG. This is the closest memory-specific prior art for retaining ancestry and
resolving descendants. Its provenance/lineage machinery is a direct novelty
threat to root-bound descendant invalidation. The local audit does not establish
that it implements Custody's exact per-PolicyKey generation, bounded compromise
interval, all-required-parent rule, or selective post-hoc action revocation;
those claims require a separate reproducibility audit before comparison.

## PACT and capability/delegation systems

PACT ([paper](https://arxiv.org/abs/2605.11039)) tracks provenance at
authority-bearing argument positions and uses capability contracts. Macaroons
([paper](https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/))
and SPKI/SDSI ([RFC 2693](https://www.rfc-editor.org/rfc/rfc2693.html)) provide
scoped delegation, caveats, and revocation handles. A capability or receipt
bound to a concrete object/root and revoked by a handle is established prior
art. Gate 1C must therefore compare composition and deployment assumptions,
not field names or API shape.

## C2PA, W3C PROV, Fides, and CaMeL

C2PA ([specification](https://spec.c2pa.org/specifications/specifications/1.0/specs/C2PA_Specification.html))
binds signed provenance manifests to assets. W3C PROV
([primer](https://www.w3.org/TR/prov-primer/)) standardizes descriptive
entity/activity/agent provenance. Fides ([paper](https://arxiv.org/abs/2505.23643))
and CaMeL ([paper](https://arxiv.org/abs/2503.18813)) mediate integrity or
capability/data flow. These systems are relevant comparators, but the local
audit found no basis to claim that any one of them supplies all of the
receipt-root, generation, support-closure, and selective-action semantics as a
single deployed mechanism.

## Conservative novelty conclusion

Selective revocation by an authenticated root/receipt handle is not a defensible
standalone novelty claim. The strongest remaining hypothesis is composition:

```text
authenticated authority root
+ immutable derivation/support closure
+ per-PolicyKey generation freshness
+ cross-agent persistence
+ post-hoc bounded selective invalidation
```

That composition is currently **untested** beyond R3's coarse-selector failure.
Gate 1C must preserve this prior-art warning and must not call a passing result
a novel provenance primitive.
