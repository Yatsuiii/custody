# Research Question

## Rejected framing

> "Can an agent fleet retroactively withdraw authority from a compromised
> source, identify downstream persistent influence, neutralize it, and
> preserve unrelated benign memory?"

Rejected as the headline question because current Custody already answers
yes to this, live-proven, at fleet scale (`make revoke`, `make live-chain`,
`make live-fleet`). Asking this again would not be research, it would be
re-marketing an existing hackathon result.

## Adopted framing

> When a source that was legitimately, correctly trusted at write time is
> later discovered to have been compromised only during a bounded
> sub-interval of its trust lifetime, can a fleet's memory system revoke
> influence scoped to that interval — including influence reached through
> paraphrase, relay, trusted-tool echo, or manufactured corroboration —
> with materially less collateral damage than today's whole-tool
> revocation, and does doing so require a derivation-matching mechanism
> that survives laundering better than exact content-hash matching?

This is two conjoined sub-questions, and both must be addressed or the
thesis is incomplete:

1. **The interval question** (novel per the independent field survey,
   2604.16548, which names this exact gap as unexplored): does scoping
   revocation to `[t_a, t_b]` instead of a tool's whole lifetime reduce
   collateral damage without sacrificing recall? This is H1/H2/H4 in
   `HYPOTHESES.md`.
2. **The laundering question** (not novel in isolation — TMA-NM,
   2606.24322, already proves exact-hash/lineage-only matching is unsound
   under laundering and ships a 0%-ASR alternative): can Custody's
   derivation matching be made laundering-resistant at all, and if so, is
   the result meaningfully different from re-implementing TMA-NM's
   mechanism? This is H3.

## Why both are required, not either

An interval-scoped revocation built on top of today's exact-hash matching
inherits every laundering blind spot the red-team found (D, E, F, G, H, R
in `CURRENT_CUSTODY_REDTEAM.md`) — it would be a more *precise* version of
a mechanism that still silently misses laundered descendants, which is not
a defensible research contribution on its own. Conversely, laundering
resistance alone (i.e., converging toward TMA-NM) would not be novel; that
problem already has a proven, benchmarked answer. The genuinely open
intersection — interval scoping *combined with* laundering resistance — is
the only framing that survives both the red-team and the literature audit.

## What would falsify this framing entirely

- If H3's deterministic multi-parent sub-case does not show the
  near-total fix its cross-cutting kill condition expects (`HYPOTHESES.md`),
  the derivation graph itself is not trustworthy enough to build interval
  scoping on top of, and the framing collapses back into "fix a bug," not
  a research question.
- If a working TMA-NM reproduction turns out to already support
  interval-like scoping once its authority tags are inspected closely
  (not confirmed either way by this audit — the paper's abstract states it
  does not, but the actual released artifact, if reproducible, should be
  checked directly before treating the gap as confirmed empty), the
  interval question could already be answered and the framing would need
  to shrink again.
