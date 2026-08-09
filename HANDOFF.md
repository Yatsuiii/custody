# Handoff, written 2026-08-09

You are picking up Custody. Two projects were killed on the day this was
written, both on measurement rather than taste, and the reasons are recorded
here so you do not rebuild either of them by accident.

Read `.claude/SESSION_CONTRACT.md` first. It governs scope and it is not
decoration: an evidence-gate hook blocks edits when it is absent, incomplete, or
does not match the branch.

## What Custody is

A provenance layer over agent long-term memory. Every durable memory carries
where its content came from and under what trust level. Untrusted-origin content
never reaches the memory service, so it cannot be retrieved into context the
model treats as instructions.

The gap it fills, quoted from Google's own source rather than inferred:

- `google/adk-python`, `memory/memory_entry.py`. A `MemoryEntry` carries
  `content`, `custom_metadata`, `id`, `author`, `timestamp`.
- `events/event.py`. `Event.author` is *"'user' or the name of the agent,
  indicating who appended the event to the session."*

Both `author` fields answer **who put this here**. Neither answers **where the
content came from**. Text a user typed and text scraped off a hostile page are
indistinguishable once in memory, which is the precondition for OWASP ASI06.

Target: All Things Agentic Hackathon, Fortified Enterprise Fleet track.

## State on 2026-08-09

Branch `feat/memory-provenance`, 6 commits, 52 tests, lint clean, everything
runs offline. Nothing pushed.

```
a7c78d7  Make it a BaseMemoryService ADK will actually accept
e6460f2  Prove the duck-typed core against real ADK objects
1a93b92  Guard the export, and run the poisoning scenario both ways
51bed56  Split a session by origin before it is ever written to memory
3f88353  Decide where remembered content came from, by structure
b0c7019  Contract Custody: chain of custody for agent memory
```

Built and verified against real ADK 2.6.3:

- `custody/origin.py`, the deep module. `take_custody(events)` labels every
  content part USER, MODEL, TOOL or DERIVED, deterministically, with no model.
- `custody/service.py`, the enforcement point. Splits a session before the write.
- `custody/action.py`, the export gateway. G3's guarded action.
- `custody/adapters/adk.py`, `CustodyMemoryBank(BaseMemoryService)`.
- `scripts/demo.py`, the scenario run with Custody and without.

**Not built, and do not imply otherwise:** persistence (quarantine is in memory
only), the Gemini reviewer, Cloud Run, anything touching live Memory Bank, and
five of the GEAP rows in the contract, which are all still CANDIDATE.

The product is roughly a fifth done. It is a domain core plus a harness.

## Two things the code depends on that are easy to break

**Taint propagation.** A model turn following an untrusted tool response *in the
same invocation* is DERIVED and inherits the distrust. When an agent summarises a
hostile page, the summary is what survives into memory and the raw response is
discarded, so labelling only raw tool output lets the laundered copy through.
That is the attack. Custody must therefore be taken over the **whole session in
one pass**; the first implementation evaluated events individually and its own
test caught the bug.

**Absence of evidence is not a clean bill of health.** Content that cannot be
attributed is refused, never stored as trusted. If you find yourself adding a
default trust level, stop.

## Killed: Warrant

`../warrant`, branch `feat/warrant-fleet-mvp`, head `49b5b47`. 356 tests, 10 of
10 red-team refusals, 3 gates green. Killed anyway, and not for bugs.

A governed multi-agent control plane that refused to act on any conclusion until
a second agent re-derived it. The kill, in one line: **every guarantee in the
system, HMAC warrants, evidence binding, an at-most-once ledger, gateway least
privilege, reputation, and 120 audit records per investigation, guarded exactly
one external action, `incident.create` at `warrant/fleet.py:48`, whose failure
mode is a spurious ticket someone closes.** The guarantee cost more than the
thing it guarded.

Three findings narrowed it before that one closed it, and all four commands
still run in that repo:

- `make shell` reproduces the causal search **and corroboration** in 86 lines of
  bash over four untrusted worker processes, matching `make liar` exactly.
- `make approvals` holds decisions a human must approve at exactly 1 from one
  agent to sixteen, while probes go 10 to 42. `require_confirmation` is
  sufficient at every size measured, and free.
- `make strikes` showed the reputation system withdrawing honest agents against
  a merely flaky service. Fixed, then the project died of the point above.
- `make compromised` showed corroboration **failing safe**: no number of
  colluding workers produces a wrong name, only `nothing proven`.

**Do not revive:** warrants, corroboration, agent reputation, or the causal
search. The one idea carried forward is that a model may plan and narrate but
must never decide the fact. In Warrant that was I8. Here it is origin labelling.

## Killed: Vigil

`../vigil`, branch `feat/standing-verdicts`, head `b4ccb6d`. Contracted and
killed the same day, for no implementation, at a cost of about ninety minutes.

Standing reachability verdicts over Go dependencies, re-opened when either the
code or the advisory database moved. Killed because the triggering event does
not happen: **zero code-side flips across 862 commits**, in five
dependency-frozen windows of `cli/cli` and three of `ollama`, every window chosen
so `go.mod` is byte-identical across it.

The spike that sold the idea was a fifteen-line module where adding `ssh.Dial`
took a package from never-imported to imported. Real codebases are saturated:
once a package is used at all, the reachable symbol set is already broad and
stable. **Reachability is a good filter and a bad event source.**

Confirmed on the way out: live symbol revisions in `golang/vulndb` ran at 17 in
2023 and **2 in 2025**.

## Measurements worth keeping

Gathered while choosing between candidates. Reusable, and cheaper to cite than
to redo.

- Official MCP registry: **7,046 servers, 20,000 published versions**, roughly
  **2,033 new servers per month** and accelerating, 39% publishing more than one
  version.
- **97%** of actively-maintained MCP servers changed their published tool surface
  between first and latest release; **16%** of description rewrites are materially
  different instructions rather than prose.
- Symbol-level advisory data exists in Go only: PyPI 0 of 143, npm 0 of 30, Go 21
  of 40.
- Memory Bank's scope is `app_name` and `user_id` only, its `metadata` is
  free-form and unvalidated, and `search_memory` takes **no filter parameter**,
  so provenance written into metadata is write-only.
- `InMemoryMemoryService.search_memory` matches on `part.text` only, so a raw
  `function_response` is stored and never retrieved. The laundered restatement is
  the dangerous form because it is the retrievable one.

## The rule that killed both projects, and should govern the next one

**Before any contract, architecture or GEAP mapping: name the triggering event
and measure how often it occurs in real data.** No design until that number
exists.

Warrant proved corroboration defeats a liar written for it, and never asked
whether anyone has that liar. Vigil proved a commit flips dormant advisories in
a module written for it, and never asked whether that happens in real
repositories. Both mechanisms worked perfectly. Both frequencies were zero.

Corollary, learned the same day: **measure on a representative sample.** Six MCP
reference servers said tool definitions never change; the 7,046-server registry
said 97% do. The reference servers are maintained by the protocol authors and are
frozen. When a tidy sample gives a clean answer, get breadth before believing it.

## Assistant failure modes observed on this project

Assume you have all of them.

- **Idea generation was 0 for 2.** Both candidates proposed here died. The
  process caught them in hours; the proposals themselves were not good.
- **Numbers reported before the measurement was audited.** A materiality
  classifier counted "Authoritative" as gaining the sensitive word `auth` and
  "whenever" as gaining `never`, inflating a result by a third until word-boundary
  matching fixed it.
- **A control test that proved nothing.** A poisoned `function_response` was
  asserted retrievable when that service never indexes them, which would have
  left the real assertion passing for the wrong reason.
- **Prose ahead of the code.** In Warrant a GEAP table described an integration
  that did not exist. In this repo, no row moves to BUILT without a command.
- **The demo built before the integration.** The user caught it. The core had
  been validated only against stand-ins written in this repo; installing ADK and
  running the conformance tests is what made the 52 green tests mean anything.

Before writing a sentence about behaviour, run the thing.

## Next actions, in order

1. **The day-one check, when the cloud account lands.** Whether Vertex's
   `agent_engines.memories.retrieve` accepts filters ADK does not pass through.
   If it does, G2 gets simpler. The gap does not close either way, because the
   write side still carries no enforced origin.
2. **G1 before anything else.** Deployment blocked Warrant for its entire life
   and the failure mode was leaving it until last. Kill date 2026-08-20.
3. Durable quarantine behind the existing `QuarantineStore` port.
4. A `Runner`-level test proving a real ADK agent receives the governed service.
5. The Gemini reviewer, which explains a quarantined memory and never labels one.

## Rules from the user that stay in force

- Commit and push only when explicitly authorized. Commits so far were
  authorized for the Windows SSD repos only.
- No em dashes anywhere in code, comments, commits, or docs.
- Do not read from or modify `~/datahub-causality-agent`, `~/priorto`,
  Throughline, or Chronicle.
- Update the session contract before widening scope, not after.
- Submission closes **2026-08-31 17:00 PDT**, which is 2026-09-01 05:30 IST. Do
  not plan to the wrong local day. XPRIZE was due 08-17 and is mostly finished,
  so 08-17 to 08-31 is roughly fourteen clear days.
