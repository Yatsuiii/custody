# Decisions

Everything a Custody session needs that is not in the code, the contract, or
`HANDOFF.md`. The contract says *what* the scope is; this says *why*, and what
was rejected. A session that reads only conclusions will re-open settled
questions and re-make cut mistakes.

All decisions dated 2026-08-09 unless noted.

---

## 1. The product is two clauses, and must stay two clauses

> Poisoned content never enters your agents' memory, and if a tool is later found
> compromised, you can pull everything descended from it.

Every proposed addition gets sorted into: serves clause one, serves clause two,
demo surface, or drift. **If a change cannot be placed, it is drift.**

This test exists because the predecessor's value proposition grew until nobody
could state it, and it died with 356 passing tests.

---

## 2. Derivation, not just origin. This is the shape change.

**Decision:** custody records carry `derived_from[]`, making the record set a
traversable graph rather than a set of independent labels.

**Why it changes the project's shape:** origin alone only protects you from tools
you already distrusted. The dangerous case is a tool you **vouched for** that is
later found compromised. Trust is a point-in-time judgement, so a write-time
control without a revocation path is half a product.

Evidence this case is real rather than theoretical: 97% of actively maintained
MCP servers changed their published tool surface between first and latest
release, and one registry audit of 3,984 skills found 76 confirmed malicious
payloads. Tools do get discovered bad after adoption.

**What it unlocks:** you discover on Friday that a tool was compromised on
Tuesday. Every memory descended from it, including model restatements several
hops downstream, across every department and session since, can be identified and
pulled. Without a derivation graph that question is unanswerable.

**This is the subscription product**, and it is the hardest technical problem in
the design, which is the right thing for a judge to see.

**Consequence accepted with it:** revocation reintroduces a read-side concern
that the write-side split had removed, because an admitted memory can become
untrusted later. Deletion from Memory Bank is preferred and doubles as
right-to-be-forgotten. **Checked live 2026-08-13 against Agent Engine
`6936011268348182528`, and rejected: no reliable mapping exists.** The
`memories.delete(name=...)` API call itself works, but nothing in the write
path can name what to delete it with. `ingest_events`'s own
`MemoryBankIngestEventsOperation` type has no `response` field at all (only
`name`, `metadata`, `done`, `error`), confirmed live: `operation.response` is
returned empty on every call. `IngestionDirectContentsSourceEvent` accepts no
custom metadata that could carry a `CustodyRecord` id through to the generated
`Memory`, only `content`, `event_id`, `event_time`. And a post-hoc
content-match lookup (`memories.retrieve`/`list`, then match `fact` text back
to a record) is not just fragile, it is unsound: ingesting a second event into
the same scope on the same topic as a first was observed live to update the
**same** memory resource name in place (`update_time` changed, `create_time`
did not), overwriting the first fact's text entirely. A memory resource is not
a 1:1 destination for one ingested event; it is a mutable, server-consolidated
target that later, unrelated, still-trusted writes can overwrite. Deleting it
to revoke one compromised record risks destroying content Memory Bank has
since merged in from other sources, and the reverse failure is silent too: the
compromised text can already be gone, superseded, while the record believes it
is still live. Fallback is post-filtering retrieval, and it is no longer a
fallback, it is the only sound option through this write path.

**A narrower fix was also tried and also failed live, same day.**
`IngestEventsConfig` exposes request-level `metadata` plus
`metadata_merge_strategy=REQUIRE_EXACT_MATCH`, documented as "restrict
consolidation to memories that have exactly the same metadata as the
request." The idea was to tag every ingest with `{"custody_record_id": <id>}`
so consolidation could never merge two different records, making deletion
safe. Live test: two ingests into the same scope, same topic, different
`custody_record_id` values each, `REQUIRE_EXACT_MATCH` set on both. They
still collapsed into one memory resource, its fact rewritten to merge both
inputs. The documented guarantee did not hold in practice for this write
path. No architecture change is worth making on top of that; the limitation
is closed for the `ingest_events` write path specifically.

**Correction, same day, live-verified, not reasoned from a docstring this
time:** `agent_engines.memories.create(fact=..., config={"memory_id": <id>,
...})` does not share `ingest_events`'s consolidation behavior. Live test:
`memory_id` set to a custody record id, two calls into the same scope, same
topic, deliberately contradictory facts ("requires two approvals" then
"requires one approval, not two, correction"). Both persisted as two
separate memory resources, named exactly `rec-a-<proof>` and `rec-b-<proof>`
as requested, `create_time` distinct for each, neither overwritten.
`memories.delete()` on the predicted name for the first removed exactly that
one and left the second's fact untouched. **This is a real, working,
deterministic mapping** between a `CustodyRecord` id and a deletable Memory
Bank resource name: no search, no content matching, no metadata filter, just
`memory_id = record.id`.

**The catch is architectural, not technical, and it is the one DECISIONS.md
#3 already named.** `create()` takes `fact` from the caller; it does not
derive it from raw session events the way `ingest_events` does. Using it
means Custody stops being a governance layer over ADK's existing memory
write (`add_session_to_memory` → `ingest_events`, the path G1's live proof
already depends on) and starts authoring memory content itself. That is
exactly the shift the framing rule in decision `#200` warns against: "every
artifact frames the finding as extending Memory Bank, not replacing it."
Selective deletion is now proven buildable, but only by trading away the
"we govern the existing path" claim for a "we are a second memory writer"
one, and by reworking the write path a live gate (G1) already depends on,
this close to the submission deadline. That tradeoff has not been made
system-wide; on explicit request it was made narrowly, for a new opt-in
path only.

**Built and proven live, same day, without touching G1.** `custody/
service.py` gained `RecordWriter`, a capability a downstream can offer
instead of the whole-session `add_session_to_memory`;
`CustodyMemoryService` writes one record at a time through it when present,
unchanged otherwise, so every existing downstream (offline fakes, G1's
`ingest_events` adapter) is untouched. `custody/adapters/memory_bank.py`
adds `AgentEngineMemoryBank` (writes via `memories.create`, `memory_id`
pinned to `memory_id_for(record.id)`) and `RevokingMemoryBankGraph` (wraps
any graph's `revoke`, then deletes each removed record's memory by that
computed name). Live proof: one session wrote two trusted, different-tool
records; both retrievable before revocation; revoking one tool removed
exactly its record from the graph and deleted exactly its memory; a
subsequent `search_memory` no longer returned it while the sibling tool's
memory was untouched. `make memory-deletion-gates`, seven PASS. This is a
second, additive write path, not a replacement: G1's `ingest_events` flow,
its Cloud Run proof, and anything already written through it are unchanged
and remain outside what this mechanism can delete. Migrating G1 onto this
path, if ever wanted, is a separate decision with its own risk, not implied
by this one.

**Migrated 2026-08-14, on request, with a real integration bug found and
fixed first.** `custody/adapters/adk.py`'s `_SessionRebuilding` (the
wrapper `CustodyMemoryBank` puts between `CustodyMemoryService` and any
downstream, needed to hand ADK a real `Session` instead of the core's
SDK-free stand-in) proxied only `add_session_to_memory` and
`search_memory`. `CustodyMemoryService.add_session_to_memory` detects the
`write_record` path via `getattr(self.downstream, "write_record", None)`,
and `self.downstream` there is always `_SessionRebuilding`, so a real ADK
`Runner` going through `CustodyMemoryBank` could never reach `write_record`
even when the wrapped downstream offered it — G1's live proof could not
have used D2's mechanism until this was fixed, regardless of which
downstream it was given. Fixed additively: `_SessionRebuilding.__post_init__`
now sets `self.write_record = inner.write_record` only when the wrapped
downstream offers it, so the capability-detection contract is preserved
through the wrapper rather than always reading as absent. Confirmed safe by
usage: only `scripts/live_memory_bank.py` and tests using
`InMemoryMemoryService` (which never offers `write_record`) construct
`CustodyMemoryBank`, so no other caller's behavior changes.

`scripts/live_memory_bank.py`'s `prove_adk_memory_bank` now builds its
downstream from `AgentEngineMemoryBank` instead of the old
`ingest_events`-based `BlockingAgentPlatformMemoryBank` (removed). The real
Runner/Gemini/conversational leg is unchanged in shape; a second, direct
write adds one real ADK event carrying a trusted tool's
`function_response` through the same `CustodyMemoryBank` instance, because
the conversational turn's records have no `source_tool` and so cannot be
targeted by `revoke(tool=...)` — the tool write is what makes selective
deletion demonstrable through G1's actual wiring, the same shape D2 already
proved standalone. Live-proven end to end against Agent Engine
`6936011268348182528`, `make live-g1` then `make gates`: the tool-origin
memory is retrievable before revocation and gone after, while the
conversational memories are untouched. Retrieval quality checked live, not
assumed: the pre-migration baseline (`ingest_events`, `proof-out/g1.json`
before this change) returned one Memory-Bank-synthesized fact merging both
admitted events' content; the post-migration path (`write_record`) returned
two separate, unmerged, raw per-event facts. This is the tradeoff already
named above made concrete: Custody stops relying on Memory Bank's own
session-level consolidation and instead gets one raw fact per admitted
record, with the loss (no synthesis across events) and the gain
(per-record, deterministic deletability) both real and now measured rather
than only reasoned about.

---

## 3. Split before the write, not filter on read

**Decision:** untrusted content never reaches the memory service.

**Why, and this was decided from source rather than preference:** `ingest_events`
is Memory Bank's default path and memories are **derived server-side**. A stored
memory is therefore not byte-identical to any event and cannot be matched back to
a custody record afterwards. Worse, a memory derived from a mix of trusted and
untrusted events has no single origin at all, because the derivation destroys the
provenance.

Filtering on read was the obvious design and it is wrong. It also conveniently
sidesteps `search_memory` having no filter parameter.

---

## 4. Taint propagates through the model

**Decision:** a model turn following an untrusted tool response *in the same
invocation* is DERIVED and inherits the distrust.

**Why:** when an agent summarises a hostile page, the summary is what survives
into memory and the raw tool response is discarded. Labelling only raw tool
output lets the laundered copy through, and the laundered copy is the attack.

Confirmed accidentally and usefully: `InMemoryMemoryService.search_memory`
matches on `part.text` only, so a raw `function_response` is stored and never
retrieved. **The laundered restatement is not merely also dangerous, it is the
only retrievable form.** A design labelling raw tool output alone would protect
nothing.

Taint is scoped to the invocation. Without that scope every session ends
untrusted and the system is an outage.

---

## 5. The fleet is the governed population, not a pipeline

**Decision:** N department worker agents being governed, plus two service agents
(Provenance Auditor, Custody Reviewer).

**Why:** the predecessor invented five roles in a pipeline (Router, Scout,
Investigator, Verifier, Steward) and that was ceremony. The track's own words are
"agents cataloged for cross-department use", which describes a *population*, not
a relay. Governing many ordinary agents is both the honest reading and the
literal requirement.

**Rule for admitting any agent:** it must enforce a correctness property or
change what a human does. Anything else is a box added to look fleet-shaped.

---

## 6. Two agents designed and cut

Recorded so they are not silently reinstated.

**Trust Steward, cut.** Would have owned the catalog lifecycle, assembling
evidence when a department requests trust for a tool. Cut because **a catalog
needs a form and a database, not an agent.** It was proposed because the fleet
needed another box, which is precisely the reasoning that killed the predecessor.
The catalog itself stays.

**Red Team agent, cut.** Would have continuously attempted injection paths
against the live fleet. Genuine assurance value and the predecessor's red team
was its strongest demo asset. Cut because it is separable and competes for the
fourteen days. **First thing to build after submission.**

---

## 7. Bigness helps the track and hurts the sale

**Recognised tension, resolved deliberately.**

A drop-in wrapper is a ten-minute integration and *is* the go-to-market:
`CustodyMemoryBank(downstream=your_service)`. A multi-tenant platform with a
catalog, graph store, agents and a console is a procurement decision, and
procurement decisions are not made by the engineer who would otherwise try it on
a Tuesday.

**Resolution:** a small core anyone can adopt in ten minutes, plus a control
plane that makes it enterprise. The core is the product; the control plane is the
upsell and the demo. **If the console ever becomes required to use it, the sale
is dead.**

Also noted: raw size carries its own credibility risk. Four thousand shallow
lines across six subsystems reads worse to an architecture judge than fifteen
hundred that are provably correct.

---

## 8. Optimize for the four capability groups, not for line count

**Decision:** GEAP coverage is the first priority, provenance graph second, scale
third.

**Why:** the track rules name four scored capability groups: discovery and
lifecycle, execution and state, security and governance, telemetry. Most entries
will hit one or two convincingly. **Hitting all four genuinely is worth more than
another thousand lines**, and it is a checklist rather than a matter of taste.

This is why G5 exists and why the GEAP table demands an artifact per row.

---

## 9. Prize strategy: build for the floor, aim at the ceiling

Assessed against the published prize table.

| Award | Value | Read |
| --- | --- | --- |
| Best Architectural Design ×2 | $5k | Highest probability. The category rewards contracts, gates and evidence, which is how this project already works. |
| Individual / Hobbyist solo ×2 | $10k | High. The field is other solo builders. |
| Fortified Enterprise Fleet | $20k | Real shot. Hardest track to enter, therefore least crowded. |
| Honorable Mention ×5 | $2k | Floor. |
| Grand Prize | $50k | Genuine stretch, not a write-off. |

**Correction worth carrying:** Grand Prize was first assessed as "low, do not
optimize for it," on the reasoning that infrastructure does not win top slots.
That was under-argued, and one prior winner contradicts it directly: **Unravel**,
five agents continuously monitoring new genomic evidence and reassessing
conclusions already reached, is structurally the same shape as Custody and won.

The real handicap is narrower and fixable: **the success case for a security
control is invisible.** Nothing happens. That is a demo legibility problem, not a
value problem.

Also corrected: optimizing for Fleet and for Grand Prize are roughly ninety
percent the same work. The conflict originally claimed between them does not
exist.

---

## 10. Lead with the breach

**Decision:** the first thirty seconds of the video show data leaving the
building in the ungoverned run, before anything about architecture.

**Why:** prevention shown without harm reads as an assertion. The harm has to be
visible first or the control looks like a claim about itself.

---

## 11. Extension, never correction

**Decision:** every artifact frames the finding as extending Memory Bank, not
fixing it.

**Why:** the thesis is "ADK's memory model records who appended content, never
where it came from." To a Google judge that can read as criticism of their
product, which is the wrong note. Memory Bank gives scope and identity; Custody
adds origin and derivation on top, through the existing port, without
modification. Same finding, and it flatters the platform instead of scoring
points off it.

Applies to the README, the video narration, and the Devpost copy.

---

## 12. Bonus points are nearly free and almost everyone skips them

Up to 1.0 available: a public build write-up (0.2), a post tagged
**#AllThingsAgenticHackathon** (0.2), additional Google models at 0.2 each to a
maximum of 0.6. In a tight ranking 1.0 is decisive.

**Claim Gemma honestly** for cheap first-pass triage of the quarantine queue.
**Do not invent a Veo or Lyria use.** A forced integration reads worse than an
absent one, and this project's whole credibility rests on not overclaiming.

---

## 13. Deployment sits third in the build order, on purpose

The predecessor left deployment until last and G1 stayed blocked for its entire
life, which is why two of its five gates never went green. Cloud Run comes after
the differentiator and persistence, and before catalog, scale, agents and
console. Kill date 2026-08-20.

---

## 14. Schedule correction

The predecessor's contract recorded XPRIZE as due 2026-08-18 with 08-18 to 08-31
fully double-booked. **Both were wrong.** XPRIZE is due 2026-08-17 and is mostly
finished, so 08-17 to 08-31 is roughly fourteen genuinely clear days.

Do not reuse the "the extra time is contested" reasoning. PriorTo / Shipaton
timing was never re-confirmed and is the one open scheduling unknown.

Submission closes 2026-08-31 17:00 PDT, which is 2026-09-01 05:30 IST. The local
date is a day later than the posted one.

---

## 15. Standing rule: evidence before architecture

Carried from two dead projects, and it is the reason this one exists.

**Before any contract, architecture or GEAP mapping: name the triggering event
and measure how often it occurs in real data.** No design until that number
exists.

**Corrected the same day, after being challenged and then tested.** The original
wording claimed Custody skips the frequency test because it has no triggering
event. The first half is true: every memory write either carries origin or it
does not, permanently. The conclusion drawn from it was wrong. The failure that
killed Warrant and Vigil is *the thing you protect is not used*, and that risk
applies here as **adoption** rather than as an event.

Measured rather than assumed: of **34 official ADK sample agents, 2 use a memory
service at all and 1 writes to it.** Long-term memory adoption is around 6% in
Google's own samples.

The exposure splits into two different bets and they must not be conflated:

- **The hackathon bet is fine, arguably ideal.** The Fleet track mandates
  "context across weeks of asynchronous operations", so every serious entry must
  use long-term memory. Within the judged population adoption is effectively
  total.
- **The market bet is early, and the evidence says new rather than dead.**
  Measured: the Memory Bank client landed in ADK on 2025-06-24, has 29 commits,
  and was last touched 2026-08-03. The official `memory-bank` sample first
  appeared 2026-04-14, alongside GEAP's launch at Next '26. So 6% adoption is a
  four-month-old, actively developed capability rather than an abandoned one.

  This is a materially better kind of early than Warrant's. Warrant bet on agent
  fleets taking unattended external actions, where no vendor shipped a product
  and nothing was driving adoption. Custody bets on agent long-term memory, where
  **Google built the product, launched it, wrote the sample, still commits to it
  weekly, and wrote a hackathon track that mandates using it.** A vendor-created
  and vendor-promoted market is not the same as an empty one. It also means no
  entrenched incumbent, which is exactly what killed Vigil's differentiation.

  It still stacks with the other declared bet, that memory poisoning has no
  enterprise incident data. Two arriving-problem bets at once, where Warrant died
  holding one. Price it before selling.

  **The falsifier, so this stays honest:** if adoption is still around 6% in six
  months, it was early-and-static rather than early. The forcing function has to
  actually fire, and a four-month trend is not a law.

What did survive testing, and it matters: the path Custody governs is the
canonical one. ADK's own docstring recommends `await ctx.add_session_to_memory()`
in an after-agent callback, which writes the **entire session** including every
function response. The API server exposes the same operation, and the memory
tools are read-only, so there is no narrower write path a developer would reach
for instead. **When memory is on, tool output goes in.**

Corollary: **measure on a representative sample.** Six MCP reference servers said
tool definitions never change; the 7,046-server registry said 97% do.

Second corollary: **audit your own measurement before reporting it.** Three bugs
in one day inflated or invalidated results, and each was caught only by looking
again.

---

## 16. Close the three named gaps, and keep durability out of the pure modules

R1_HANDOFF.md's "What this does not fix" section named three gaps on purpose,
deferred rather than fixed at the time, so the digest-versioning fix could
land small and be reviewed on its own. All three are now closed.

**Decision:** `RevisionCatalog` and `AttestationAuthority`'s replay ledger both
get Firestore-backed durable implementations, gated by `CUSTODY_FIRESTORE_PROJECT`
exactly the way `custody/control_plane.py::_default_plane()` already gates
`CustodyGraph`, `AuditorLog`, and `DemotionLog`: durable when a project is
configured, pure in-memory otherwise, so offline tests and a bare local run
never need a cloud account. R1 additionally binds the Cloud Run revision name
and resolved image digest into admission, not just the declared MCP surface
digest, closing "declared surface drift" to "declared surface or running
image drift" — the cheap upgrade the handoff named but did not build.

**The one design call worth recording:** the durable nonce ledger does not
live in `custody/firestore_store.py` alongside the durable revision catalog,
even though both are Firestore-backed and both close a gap from the same
handoff. `firestore_store.py` already imports `custody.catalog` and
`custody.graph` for its other collaborators, and the ledger is the one
durable backend that gets vendored into the live MCP export server's Docker
build context — the only place a durable ledger is actually used, since
`RevisionCatalog` is client-side admission logic the script itself runs
with the whole repo on its path. Vendoring `firestore_store.py` into that
image would drag graph/catalog into a process that needs neither. So the
ledger got its own file, `custody/nonce_ledger.py`, importing only
`google.cloud.firestore` and satisfying `custody.revision.NonceLedger`
structurally, no import of `revision.py` required. Two Firestore-backed
classes closing two gaps from the same handoff, in two different files, for
a real dependency-boundary reason rather than an arbitrary split.

**What was proven live, not just offline:** an in-memory nonce ledger's
actual gap is invisible within a single process, which is all the existing
R2 proof (`live_revision_binding.py`) ever exercised. Proving durability
needed a fresh process serving the *same* MCP digest so no `DIGEST_MISMATCH`
could mask the result — achieved by redeploying v1 a second time (Cloud Run
always creates a new revision/process even for an identical deploy) and
replaying the original token against it. Pre-fix, a fresh process has never
seen the nonce and wrongly accepts it a second time; post-fix, the shared
Firestore document from the first process's consumption already exists, so
the second process correctly refuses it. This is the actual bug being
fixed, made falsifiable rather than argued from design alone.

**Kept out of scope, matching R1's own precedent:** `custody/origin.py` and
`CustodyRecord` are untouched — a runtime binding is an admission-time gate,
not something threaded into stored derivation records. No TTL or pruning
for the growing `dispatch_nonces` collection; unbounded growth was already
true of the in-memory set it replaces, not a regression introduced here. No
attempt at a true multi-instance concurrent proof for the replay ledger;
`--max-instances=1` stays, because other gates' `instance_id` assertions
depend on it, and durability-across-restart is the literal property named
in the gap, not durability-across-concurrency.
