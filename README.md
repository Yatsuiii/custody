# Custody

Chain of custody for agent memory.

An agent reads a supplier page in week one. The page carries an instruction, not
information. Nothing happens. In week three an ordinary request retrieves what
was remembered, and customer records leave the building.

```
$ make demo

  WITHOUT CUSTODY
    week 1  memories written                3
    week 3  retrieved into instruction context 3
            of those, carrying the injected instruction: 2
    export to compliance-archive@external.example: ALLOWED

  WITH CUSTODY
    week 1  events seen 3, admitted 1, withheld 2
            quarantined: tool     from fetch_page
            quarantined: derived  from fetch_page
    week 3  retrieved into instruction context 1
            of those, carrying the injected instruction: 0
    export to compliance-archive@external.example: REFUSED
            cited content came from untrusted source(s): fetch_page
```

The instruction reached instruction-eligible context in the first run and never
entered memory in the second. **What changed is the memory path, not the model.**

## The gap this fills

ADK gives every memory an author. From `memory/memory_entry.py`, a `MemoryEntry`
carries `content`, `custom_metadata`, `id`, `author`, `timestamp`. And
`events/event.py` documents `Event.author` as *"'user' or the name of the agent,
indicating who appended the event to the session."*

Both answer **who put this here**. Neither answers **where the content came
from**. So text a user typed and text scraped from a hostile page are
indistinguishable once they are in memory, which is the precondition for
[OWASP ASI06](https://owasp.org/www-project-top-10-for-large-language-model-applications/).

Custody adds origin and derivation on top of Memory Bank, through the existing
`BaseMemoryService` port, without modifying anything.

```python
from custody.adapters.adk import CustodyMemoryBank

memory = CustodyMemoryBank(downstream=VertexAiMemoryBankService(...))
```

That is the whole integration.

## What it costs a compromised tool

A tool your fleet trusted turns out to be compromised. Without a derivation
graph, "which memories descended from it" is not a hard question, it is an
unanswerable one. So the options are purge everything, purge every department
that touched it, or leave the poisoned lineage in place.

```
$ make cost

  600 memory records. 'vendor_portal' is found compromised.

  response                                 destroyed   survives
  ------------------------------------------------------------
  purge the whole app                          600          0  (0%)
  purge every department that used it          600          0  (0%)
  remove exactly the descendants                40        560  (93%)
```

That headline is the flattering case, so the same command prints the
sensitivity. Restricting the tool to fewer departments moves the saving from
93% down to 19%, and even at a single department a per-user purge destroys 20%
of fleet memory to remove 1%.

What does not move with the fixture is the granularity, and it is the actual
claim: **with no derivation recorded the smallest unit you can safely purge is a
user. With it, the unit is a record.**

## How it decides

Origin is read off the event graph, never inferred by a model.
`Event.get_function_responses()` makes "this text arrived from a tool" a
structural fact. Each content part is `USER`, `MODEL`, `TOOL`, or `DERIVED`.

**`DERIVED` is the one that matters.** A model turn following an untrusted tool
response inside the same invocation inherits the distrust, because when an agent
summarises a hostile page the summary is what survives into memory and the raw
response is discarded. Labelling only raw tool output would protect nothing.
`InMemoryMemoryService` makes this concrete: it indexes `part.text` only, so a
raw `function_response` is stored and never retrieved. The laundered restatement
is not merely also dangerous, it is the only retrievable form.

Content that cannot be attributed is refused rather than stored as trusted.
Absence of evidence is never a clean bill of health.

## Cross-department isolation

```
$ make isolate

  -- adversarial attempts --
    sales -> support: REFUSED
        sales cannot vouch for support's tools
    support -> sales: REFUSED
        support cannot vouch for sales's tools

  -- sales vouches for its own tool --
    sales trusts crm_lookup: True
    support trusts crm_lookup: False
```

Trust earned in one department does not leak into another's writes, and nothing
quarantined in one is visible from the other.

## Retroactive revocation

```
$ make revoke

    before revocation: 5 record(s)
        sales-inv-1:0:0          user     trusted
        sales-inv-1:1:0          tool     trusted
        sales-inv-1:2:0          model    trusted <- ('sales-inv-1:1:0',)
        support-inv-1:0:0        tool     trusted <- ('sales-inv-1:2:0',)
        support-inv-1:1:0        model    trusted <- ('support-inv-1:0:0',)

    demoting crm_lookup
    revocation rev-2026-08-N: removed 4 record(s)
    after revocation: 1 record(s)
        sales-inv-1:0:0          user     trusted

    replay: 0 further record(s) removed, 1 revocation record(s) total
```

Three derivation hops, across a department boundary, through a real
`load_memory` retrieval rather than a synthetic edge. The user's own question,
unrelated to the tool, survives. Replaying the revocation removes nothing
further and appends no second audit record.

## Spin up

Python 3.12. The core imports no SDK, so the full suite runs with no cloud
account and no network.

```bash
git clone <this repo> && cd custody
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

make check     # ruff, then 104 tests, none skipped
make demo      # the poisoning scenario, with Custody and without
make cost      # what a compromised tool destroys, with the graph and without
make revoke    # retroactive revocation across departments, and a replay
make isolate   # two departments, one catalog, no shared trust unless earned
```

`google-adk` is the only dependency, and it is what the 18 conformance tests
need: they build genuine `google.adk.events.Event` objects and run the core over
them, so the duck-typed core is proved against the real SDK rather than against
stand-ins written in this repo.

Skip the install and the suite still runs, but honestly reports `OK (skipped=18)`
rather than pretending. 86 tests execute against stand-ins; the 18 that prove the
SDK shapes match are the ones you lose.

## Architecture

[Diagrams](docs/architecture.md): what the system is made of, and the path a
piece of content takes from arriving in a tool response to being refused an
export.

Four layers, and the boundary that matters is between deciding facts and
deciding what they mean.

| Layer | File | Role |
| --- | --- | --- |
| Origin labelling | `custody/origin.py` | pure function, no model, no I/O |
| Derivation graph | `custody/graph.py` | traversal and revocation |
| Enforcement | `custody/service.py` | splits a session before the write |
| Export gateway | `custody/action.py` | egress must cite trusted memory |
| Trust catalog | `custody/catalog.py` | per-department grants |
| Durable stores | `custody/store.py` | survive a restart |
| ADK shell | `custody/adapters/adk.py` | `BaseMemoryService` ADK accepts |

Enforcement happens at the **write**, not at retrieval. Memory Bank derives
memories server-side, so a stored memory is not byte-identical to any event and
cannot be matched back to a custody record afterwards; a memory derived from
mixed-trust events has no single origin at all. Splitting before the write also
sidesteps `search_memory` having no filter parameter.

## Status, honestly

| | |
| --- | --- |
| Core, verified against real google-adk 2.6.3 | **built**, 104 tests |
| Derivation graph and retroactive revocation | **built** |
| Cross-department isolation | **built** |
| Durable stores surviving a restart | **built**, SQLite |
| Cloud Run, live Memory Bank, Gemini reviewer | **not built** |
| Agent Registry, Identity, Gateway, Model Armor, Observability | **not built** |

Nothing in this table moves to built without a command that demonstrates it.

**A stated bet, not a finding:** no enterprise incident data exists for memory
poisoning. It has formal standing as OWASP ASI06 and demonstrated attack success
rates in research, but recognised and demonstrated is not the same as happening
to customers. Long-term memory adoption is also early: 2 of 34 official ADK
sample agents use a memory service at all.

## Prior work

`google-adk` and the Vertex AI SDK are consumed unmodified. Everything else is
new work created during the submission period.
