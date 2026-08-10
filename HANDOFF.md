# Handoff, written 2026-08-10, for a cold Codex session

You have touched nothing in this repo yet. This document exists so you do not
have to re-derive two days of decisions before doing useful work. Read
`.claude/SESSION_CONTRACT.md` in full before editing anything. On the Claude
side an evidence-gate hook blocks edits when it is absent, incomplete, or does
not match the branch; that hook will not fire for you, but the rules in the
contract are the ones this project is held to regardless of which tool is
editing it.

## What Custody is, in one sentence

> Poisoned content never enters your agents' memory, and if a tool is later
> found compromised, you can pull everything descended from it.

A provenance layer over ADK long-term memory (`BaseMemoryService`). Every
durable memory records where its content came from (USER/MODEL/TOOL/DERIVED,
decided from event structure, never by a model) and what it was derived from
(a graph edge). Untrusted-origin content is quarantined before it ever
reaches the memory service. Target: All Things Agentic Hackathon (Google,
Devpost), Fortified Enterprise Fleet track. Submission closes 2026-08-31
17:00 PDT, which is 2026-09-01 05:30 IST, the local date is a day later than
the posted one.

## State right now

Branch `feat/memory-provenance`, working tree clean, nothing uncommitted,
nothing pushed. Latest commit `e447b54` ("Add the control plane and the image
Cloud Run will run"). 113 tests, lint clean, all offline, no network or cloud
account needed for any of it.

```
$ make check   # lint + 113 tests, ~0.03s
$ make gates   # PASS/FAIL per acceptance gate, judged from proof-out/ on disk
```

Current `make gates` output:

```
[PASS   ] G2 enforcement is structural, and reports its cost
[PASS   ] G3 retroactive revocation across the graph
[PASS   ] G4 cross-department isolation
[BLOCKED] G1 deployment and live substrate       -- needs the cloud account
[BLOCKED] G5 four capability groups, real elapsed time -- needs the cloud account
```

Three of five acceptance gates are proven offline, with evidence files
written to `proof-out/` that `gates.py` reads and judges rather than trusting
a script's own printed claim of success. The two blocked gates need one
thing: a usable Google Cloud account with billing enabled. As of the last
check that account was not usable. If it has become usable since, that is
the single highest-leverage thing to check first, see "Next actions" below.

## Repository map

```
custody/
  origin.py      Deep module. take_custody(events) labels every content part
                 USER/MODEL/TOOL/DERIVED, deterministically, no model in the
                 loop. Taint propagates within an invocation: a model turn
                 after an untrusted tool response is DERIVED and inherits
                 the distrust, because a laundered summary is the dangerous
                 form, not the raw response. Also resolves cross-session
                 retrieval: a load_memory tool response earns a derived_from
                 edge back to the CustodyRecord it matches by content hash,
                 via a RecordResolver Protocol passed into take_custody and
                 resolved INLINE during the same forward pass. That inline
                 placement is load-bearing: resolving it as post-processing
                 after the pass was tried, was structurally wrong (it let a
                 stale default-untrusted verdict feed taint tracking for the
                 rest of the invocation before the patch could run), and was
                 caught by test_cross_department.py, not by inspection.
  graph.py       CustodyGraph, pure in-memory derivation graph. add, extend,
                 records, resolve(content_sha256), descendants(tool) via
                 BFS, revoke(tool, revocation_id) idempotent on
                 revocation_id, revocations().
  catalog.py     TrustCatalog, per-department tool grants. request(Vouch)
                 refuses a department vouching for another department's
                 tool and logs the refusal as audit trail either way,
                 allowed or denied. trust_for(department) -> ToolTrust.
  service.py     CustodyMemoryService, the enforcement point. Splits a
                 session by origin before it is ever written downstream.
                 Quarantine sits behind a port (InMemoryQuarantine or the
                 durable SqliteQuarantine).
  store.py       Durable SQLite stand-ins for what would be Firestore
                 collections: SqliteQuarantine, SqliteCustodyGraph,
                 SqliteTrustCatalog. Each wraps the pure in-memory class and
                 rebuilds it on construction by replaying a persisted
                 append-only log through that same class's own methods
                 (add/revoke/request), so the algorithm exists in exactly
                 one place and only the durability is new. Proven to survive
                 a simulated Cloud Run restart in
                 tests/test_durable_integration.py: fresh SQLite
                 connections, zero shared in-memory state, three simulated
                 redeploys, both G3 and G4 checked after each one.
  action.py      The export gateway. An external action must cite the
                 CustodyRecord(s) that justified it and is refused if any
                 cited record's trust is untrusted.
  control_plane.py  The Cloud Run surface (make serve runs it locally on
                 :8080). Not deployed anywhere yet, but exercised offline in
                 test_control_plane.py.
  adapters/adk.py   CustodyMemoryBank(BaseMemoryService), the actual ADK
                 integration point, proven against real ADK objects in
                 test_adk_conformance.py and test_adk_memory_bank.py, not
                 just duck-typed stand-ins.

scripts/
  demo.py        make demo     the poisoning scenario, with Custody and
                 without, side by side.
  revoke.py      make revoke   G3 offline: a tool trusted on day one,
                 demoted on day N, removed across two departments and a
                 real load_memory retrieval earned by content match, not
                 hand-wired for the demo.
  isolate.py     make isolate  G4 offline: adversarial cross-department
                 vouch attempts, both refused and audited; quarantine
                 read-side isolation.
  cost.py        make cost     what a compromised tool costs, with the
                 graph and without, as a number rather than a claim.
  gates.py       make gates    PASS/FAIL per acceptance gate, read from
                 proof-out/.

Dockerfile, .dockerignore   make image builds the Cloud Run container and
                 checks the dependency pins hold. Not pushed or deployed.
docs/architecture.md        the architecture diagram the README points to.
proof-out/       g2.json, g3.json, g4.json, the evidence gates.py reads.
DECISIONS.md     append-only decision log. Read the tail before assuming a
                 design question is open; it may already be settled there,
                 with the reasoning, including the fuller story on why two
                 predecessor projects (Warrant, Vigil) were killed and what
                 survived from each.
```

## Rules that are not optional

- **No model decides a fact.** Origin and derivation come from event
  structure only. A model may summarize, explain, or draft a verdict for a
  human to approve. It must never label, adjudicate, or set trust. This is
  the one idea carried forward from both killed predecessor projects and it
  is not up for renegotiation.
- **No em dashes** anywhere: code, comments, commit messages, docs. Use
  periods, commas, or hyphens with spaces.
- **Commit and push only with explicit authorization** in the session you
  are in. Nothing should reach a remote without being asked for directly.
- **No row in the Google-product mapping table (in the session contract)
  moves to BUILT without a command that demonstrates it.** A predecessor
  project shipped a table describing integrations that did not exist; this
  project's whole discipline is proof over prose. `make gates` is the
  enforcement mechanism for the acceptance gates specifically.
- **Absence of evidence is not a clean bill of health.** Content that cannot
  be attributed to an origin is refused, never defaulted to trusted. If you
  find yourself adding a default trust level anywhere, stop and reconsider
  the design instead.
- **Do not read from or modify** `~/datahub-causality-agent`, `~/priorto`,
  Throughline, or Chronicle. `../warrant` and `../vigil` are the same
  author's own in-period prior work, no disclosure burden, but leave them
  alone too.
- Update `.claude/SESSION_CONTRACT.md` before widening scope, not after.

## What's actually blocking G1 and G5

A usable Google Cloud account with billing. The code side is not the
bottleneck: everything provable offline behind real interfaces (ports for
Quarantine, CustodyGraph, TrustCatalog, all with durable SQLite
implementations already proven to survive a restart) has been proven. Two of
the three day-one questions about the Vertex client library were already
settled by reading `google-cloud-aiplatform` 1.163.0 source directly rather
than waiting for credentials: `agent_engines.memories.delete` exists for the
revocation path, and `Memory.scope` accepts arbitrary string keys so
department isolation can be enforced by Memory Bank itself, not only by
Custody. Full detail is in the contract's "Baseline" section. The one
genuinely unverified thing is whether GEAP components are reachable at all
on a fresh trial project, which needs the account to answer.

Kill condition already recorded in the contract: if the account cannot serve
Gemini 3.5+ through Vertex, or an ADK agent cannot reach Cloud Run, by
**2026-08-20**, stop rather than keep building around it.

## Next actions, roughly in order

1. Check whether a usable cloud account exists yet. If yes, run the
   remaining day-one check (GEAP reachability on the trial project) before
   anything else, then move on G1: deploy the control plane to Cloud Run,
   confirm a Gemini 3.5+ call through Vertex, confirm an ADK agent reaches
   it, confirm a write through live Memory Bank. That single gate unblocks
   most of G5 too.
2. If still no account, remaining offline staging items from the contract:
   department worker agents at scale (item 5), Gemini reviewer plus
   Observability traces (item 6, the reviewer logic can be built and tested
   offline but the live Gemini call itself needs the account), console and
   the four-minute film (item 7).
3. Whichever you build, run `make check` before calling it done and
   `make gates` before claiming any gate moved status.

## Assistant failure modes observed on this project so far

Assume you are capable of all of them too.

- Idea generation was weak on both predecessor projects; both were proposed
  and killed within hours, on measurement, not on taste.
- Numbers reported before the measurement behind them was audited (a
  materiality classifier bug inflated a result by a third before a second
  look caught it).
- A control test that asserted something a mocked service could never have
  proven either way (a poisoned function_response asserted retrievable
  through a service that never indexes function_response content).
- Prose written ahead of the code it described (a capability table claiming
  an integration that did not exist).
- A demo built before the integration it claimed to demonstrate was
  installed and actually run against.
- A post-processing fix that looked correct but changed the wrong pass (the
  cross-session derivation bug described under `origin.py` above): caught by
  a failing test, not by re-reading the diff.

Before writing a sentence claiming something works, run the thing that would
prove it.
