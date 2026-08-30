# Tool Relay Model

E2A showed that a trusted runtime name is not evidence about the upstream
origin of its payload. The design therefore classifies each **operation**, not
each tool binary as a whole.

## Operation roles

```
ToolRole = ORIGIN | RELAY
```

- `ORIGIN`: the operation is the policy-recognized source of a fact for named
  action scopes. Its own root policy may bind `ACT`.
- `RELAY`: the operation transports, retrieves, proxies, mirrors, or reformats
  data whose authority comes from upstream. Its runtime identity cannot raise
  that data's authority.

A tool with both behaviors must expose separate operation identities or output
fields with separate envelopes. If the adapter cannot partition them, the
entire operation is `RELAY`. An unconfigured operation also defaults to
`RELAY`.

## Deterministic binding rules

### ORIGIN

For a genuine root output, the admission gate applies the configured
`source/operation/action-scope` cap. The text is not inspected. A later
compromise window can still make that correctly bound record ineffective; the
write-time decision remains immutable history.

### RELAY with observable Custody parents

The in-TCB adapter supplies the upstream record ids it retrieved. The relay
output is an ordinary derivation:

```
Caps(output) = meet(relay_policy_cap, Caps(parent_1), ...)
Support(output) = union(Support(parent_1), ...)
```

The relay policy cap can restrict scopes but never elevate a parent.

### RELAY with external or hidden upstream

If the upstream object has no trustworthy Custody record id, the envelope
includes `UNKNOWN_CONTEXT`. The result is at most `INFORM` and cannot authorize
an action. This is the honest limit: the system cannot manufacture upstream
provenance from a payload or a tool's assertion about itself.

### Tool-supplied provenance

An arbitrary tool's `source_id`, URL, signature-looking string, or parent list
is untrusted payload. It becomes authoritative only when a configured connector
verifies it against a named external identity/integrity system. That connector,
its verification keys, and its freshness/revocation path then join the trusted
computing base. No such connector is assumed in the core design.

## E2A replay under this model

| State | Operation role | Upstream receipt | Maximum result |
|---|---|---|---|
| Genuine vendor lookup backed by its authoritative database | `ORIGIN` | root | configured per-scope cap, possibly `ACT` |
| Unvouched scraper | `RELAY` by default | unknown | `INFORM`/`NONE`, never `ACT` |
| Trusted vendor tool echoing attacker-controlled input | `RELAY` | attacker/unknown upstream | parent cap or `INFORM`, never elevation from the trusted name |
| Retrieval of a known trusted record | `RELAY` | stored parent id | inherits no more than the parent and transform cap |

This closes the structural condition E2A measured only if the operation policy
is correct and the adapter cannot be bypassed. It does not detect a compromised
`ORIGIN` operation in real time; that is the bounded-window problem handled
after discovery by `DYNAMIC_TRUST_MODEL.md`.

## Policy ownership and audit

The departmental trust catalog owns operation roles and action caps. Every
change records actor, department, source, operation, old role/caps, new
role/caps, evidence, policy version, and authoritative change time. Admission
envelopes bind the policy version used so a later investigation can explain the
decision without reading today's policy as if it were historical truth.

Cross-department writes remain forbidden. A department may configure only its
own source boundary; a shared connector requires an explicitly shared policy
owner rather than implicit inheritance.

Misclassifying a relay as an origin is a security failure with the same shape
as E2A. Required controls are therefore:

1. default `RELAY`;
2. explicit review evidence for every `ORIGIN` operation;
3. deny action authority when a policy version is missing or stale;
4. log every use of an `ORIGIN` cap; and
5. include a misclassified-origin negative control in the future policy test
   suite, even though automatic classification is out of scope.

## Trusted-computing-base statement

Arbitrary tools cannot be required to provide truthful upstream provenance.
Architecture A's claim stops at what Custody's own context collector observes
or what a separately trusted connector verifies. When neither exists, the only
sound result is unknown/informational authority. Any implementation that treats
a tool's self-declared parents as trusted without naming a verifier is outside
this design.
