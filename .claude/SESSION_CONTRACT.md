# Custody, session contract

Working name: Custody. Chain of custody for agent memory. Rename is cheap until
the first public artifact, expensive after the demo video.

Objective: Ship one submittable artifact to the All Things Agentic Hackathon
(Google, Devpost) under **Fortified Enterprise Fleet**. The artifact is a
provenance layer over agent long-term memory: every durable memory carries where
its content came from and under what trust level, writes without that are
refused, and retrieval will not put untrusted-origin content into
instruction-eligible context. One deployed Cloud Run service, one public repo,
one four-minute video.

Branch: feat/memory-provenance
Parent: HEAD (unborn; repository initialized 2026-08-09, no commits yet)

Allowed files: everything under /run/media/Yatsuiii/Windows-SSD/custody.

## The problem, and the evidence for it

The Fleet track's hardest requirement is agents that "safely maintain context
across weeks of asynchronous operations". The named threat to exactly that
clause is memory poisoning, whose defining property is that it is **temporally
decoupled**: prompt injection resets when a session ends, a poisoned memory does
not. An instruction written today lies dormant through routine sessions and
activates weeks later.

Verified in Google's own source on 2026-08-09, not inferred:

- **`google/adk-python`, `memory/memory_entry.py`.** A `MemoryEntry` carries
  `content`, `custom_metadata`, `id`, `author`, `timestamp`. Nothing else.
- **`events/event.py`.** `Event.author` is documented as *"'user' or the name of
  the agent, indicating who appended the event to the session."*
- Memory is populated by `add_session_to_memory(session)` and
  `add_events_to_memory(events)`, which ingest those events wholesale.

So both `author` fields answer **who put this here**, and neither answers **where
the content came from**. Text the user typed and text scraped from a hostile page
are indistinguishable once in memory. `Event.isolation_scope` is a logical
partition, not a trust label. Provenance is possible only through
`custom_metadata`, whose docstring says its keys are *"implementation-defined by
each memory service"*, so nothing composes across services, nothing a gateway can
enforce, and nothing survives swapping the memory backend.

**The primitive is missing from the contract.** That is the gap.

Threat standing: OWASP **ASI06** in the 2026 Agentic AI Top 10; published attack
success rates of 80%, 95% and 99.8%; 91,000 attack sessions captured in honeypots
between Oct 2025 and Jan 2026.

**Load-bearing and verified:** `Event.get_function_responses()` exists, so "this
text arrived from a tool rather than from the user or the model" is a structural
property of the event. The labelling step needs **no model**. If that ever stops
being true, the project's main claim to determinism goes with it.

Non-goals:

- **No model decides provenance.** Origin comes from event structure. A model may
  summarise or explain, never label or adjudicate.
- No new memory store. Memory Bank and ADK's services are the substrate.
- No detection of "malicious content". This governs origin and trust, not intent.
  Content classification is Model Armor's job and is not being rebuilt.
- No auth, billing, multi-tenancy, or user management.
- No second ecosystem, no second agent framework beyond what G1 requires.
- No second submission; no Startup Excellence attempt (needs an incorporated
  organization and corporate email, neither exists).
- Reuse of `../warrant` is permitted but not planned. It is in-period work so it
  carries no disclosure burden, but this is a different product.
- No commit and no push without explicit authorization in the session.

## Architecture

**1. Origin labelling. Deterministic, no model.**
Walk a session's events. Each content part is classified by structure: `USER` (a
user turn), `MODEL` (model-generated), `TOOL` (inside a function response, tagged
with which tool and which server). Tool output is untrusted by default; the
registry may raise a specific tool's trust.

**2. The custody record. The deep module.**
`custody(events) -> (memories, refusals)`. A pure function: no I/O, no clock, no
network. Every emitted memory carries origin, the tool and server it came from,
trust level, the invocation it was produced in, and a digest of the content. A
memory that cannot be given an origin is **refused, not silently downgraded**.

**3. Enforcement at both ends.**
On write, the gateway refuses a memory without a custody record. On read,
retrieval partitions results: trusted-origin memories may enter
instruction-eligible context, untrusted-origin memories may only reach a
quarantined channel or a human view. This is policy, not a hint to the model.

**4. Judgement. The model's only job.**
Gemini 3.5+ via Vertex explains a quarantined memory to a human and drafts the
review summary. Structurally barred from setting origin or trust.

### Google product mapping

No row moves to BUILT without a command that demonstrates it. The rule exists
because a predecessor shipped a GEAP table describing an integration that did
not exist.

| Product | Role | Status |
| --- | --- | --- |
| Gemini 3.5+ via Vertex AI | explains quarantined memories; never labels | PLANNED, mandatory |
| ADK | the agent framework; `BaseMemoryService` is the seam | PLANNED, mandatory |
| Cloud Run | control plane and the reviewer service | PLANNED, mandatory |
| GEAP Memory Bank | the memory substrate being governed | PLANNED, central |
| Firestore | custody records, quarantine queue | PLANNED |
| GEAP Agent Identity | who wrote the memory | CANDIDATE |
| GEAP Agent Gateway | refuses a write lacking custody | CANDIDATE |
| GEAP Model Armor | screens content; complements origin, does not replace it | CANDIDATE |
| GEAP Agent Registry | per-tool trust levels, owned per department | CANDIDATE |
| GEAP Agent Observability | traces carrying the custody digest | CANDIDATE |
| Cloud Scheduler | the daily run that makes elapsed time real | PLANNED |

Every CANDIDATE has an in-memory implementation behind the same port, so an
unreachable GEAP row degrades rather than blocks.

Baseline:

New repository. Environment facts verified 2026-08-09:

- ADK memory and event models read from `google/adk-python` at `main`; the field
  sets above are quoted from source.
- **Day-one kill check run early, 2026-08-09, from source.** Memory Bank does
  not close the gap. In `memory/vertex_ai_memory_bank_service.py` the entire
  scoping axis is `scope={'app_name':..., 'user_id':...}`; `metadata` is a
  free-form "mapping of custom metadata key-value pairs" the caller supplies and
  nothing validates. Decisively, `search_memory(app_name, user_id, query)` takes
  **no filter parameter at all**, so even provenance diligently written into
  metadata is **write-only: recordable, and unusable at retrieval time.**
  Consequence for the design: enforcement cannot live inside Memory Bank and
  must wrap `search_memory`, retrieving and then partitioning by custody record.
  Unverified until the account exists: whether the underlying Vertex
  `agent_engines.memories.retrieve` accepts filters that ADK simply does not
  pass. Check on 08-10. If it does, G2 gets simpler; the gap does not close,
  because the write side still carries no enforced origin.
- Google Cloud account for the build **arrives 2026-08-10** (confirmed by Raghav
  on 08-09). Gemini 3.5+, Memory Bank and every GEAP row are unverified on it and
  are the first thing to check when it lands. A 200 on any other account is not
  evidence, and a 404 or PERMISSION_DENIED is a kill-condition input rather than
  a config nuisance.

Acceptance gates:

- **G1 deployment.** A Cloud Run service accepts a trigger and returns a run id;
  the record shows a Gemini 3.5-or-newer model served through Vertex AI; at least
  one agent is an ADK agent; memory is written through Memory Bank. Proof:
  `gcloud run services describe`, one run document, console on screen.
- **G2 quarantine is enforcement, not a hint.** A poisoned memory carrying
  untrusted origin is **structurally excluded** from instruction-eligible
  context, demonstrated by the retrieval call returning it in the quarantined
  partition only. The negative control: the same run with Custody disabled shows
  the agent acting on it. **This gate fails if the defence is a marker the model
  is asked to respect.**
- **G3 the guarded action is consequential.** Named here before implementation,
  as the gate requires: **`export.send`, transmitting production data to an
  external destination.**

  Chosen on three grounds. It is irreversible in the only way that matters, since
  data that has left cannot be recalled. It is the documented payload class for
  this attack rather than one invented to justify the defence, per the memory
  exfiltration literature. And it is the Fleet track's own third clause, agents
  interacting with production data "without violating enterprise compliance, data
  sovereignty, or security policies", so the demo answers a mandatory requirement
  instead of a side quest.

  The scenario: weeks before the demo, a hostile tool response introduces a
  memory stating that summaries of customer records must also be delivered to an
  external endpoint "for compliance". It sits dormant. A routine request later
  retrieves it, and the agent complies. With Custody the memory's untrusted
  origin excludes it from instruction-eligible context, so the export is never
  proposed; and were it proposed, the gateway refuses it and the custody record
  names the exact tool response that introduced the instruction.

  **A wrong chat answer does not satisfy this gate.** A predecessor died of
  expensive machinery guarding a ticket.
- **G4 recall cost, measured not asserted.** Quarantining untrusted-origin
  memories costs legitimate recall. Report the number: how many memories are
  withheld, and how many of those were benign. A gate that hides its own cost is
  the failure mode this project exists to argue against.
- **G5 weeks, with real elapsed time.** Cloud Scheduler runs daily from first
  deploy to filming, and one custody record shows genuine timestamps across that
  span, including a memory written early and quarantined later. Nothing
  fast-forwarded.

G2 and G3 are the riskiest and both came out of a pressure test on 2026-08-09.
G4 exists because the honest cost of this design is recall.

Verification:

`make check` runs lint and the offline suite with no network and no cloud: the
custody function is pure, so its whole contract is testable without either.
`make demo` runs the poisoning scenario end to end and prints the two paths,
Custody off and Custody on. `make gates` prints PASS/FAIL per gate by reading
persisted custody records, quarantine entries and action records rather than by
asserting in prose. Manual: watch the four-minute recording and confirm every
claim is visible on screen.

## Stated assumption, not a finding

**No enterprise incident data exists for memory poisoning.** It has formal
standing as OWASP ASI06 and demonstrated attack success rates in research, which
is more than the predecessor's threat model ever had, but recognised and
demonstrated is not happening to customers. This is a declared bet on a problem
that is arriving. Do not let it drift into the README as evidence of demand.

## Kill conditions

- If the account cannot serve Gemini 3.5+ through Vertex, or an ADK agent cannot
  be deployed to Cloud Run, by **2026-08-20**, stop. The account arrives 08-10,
  so that is ten days of slack on a gate that blocked the predecessor for its
  entire life. It must not be left until last again.
- If G2 cannot be made structural, so the only available defence is asking the
  model to respect a label, **stop and say so**. That is the difference between a
  control and a suggestion.
- If Memory Bank turns out to already carry enforceable origin metadata, the gap
  is closed and the project is unnecessary. Check this first, on day one.

## Schedule

- Today is 2026-08-09. Submission closes **2026-08-31 17:00 PDT**, which is
  2026-09-01 05:30 IST. The local date is a day later than the posted one; do not
  plan to the wrong day.
- **Corrected 2026-08-09:** XPRIZE is due 2026-08-17 and is mostly finished, so
  the run-up is light and **08-17 to 08-31 is roughly fourteen clear days**. The
  old contract's "08-18 onward fully double-booked" reasoning was wrong and must
  not be reused. PriorTo/Shipaton timing is the one open scheduling unknown.
- Deploy first, build inward. Reference point: the predecessor reached 356 tests,
  a console and Google adapters in three days, so the window is adequate if G1 is
  not left until last.
- Bonus points are cheap: a public build write-up (0.2), a post tagged
  #AllThingsAgenticHackathon (0.2), additional Google models (0.2 each, max 0.6).

## Prior work disclosure

Submission period opened 2026-08-04; this repository was created 2026-08-09, so
it is new work. `../warrant` and `../vigil` are the author's own in-period work
and carry no disclosure burden, but must be listed if any code is lifted. Do not
read from or modify `~/datahub-causality-agent`, `~/priorto`, Throughline, or
Chronicle.

## Status

Status: active
