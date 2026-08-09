# Bootstrap prompt for a cold Custody session

Paste this as the first message. It assumes nothing and points at the three
documents that carry the rest.

---

Read @.claude/SESSION_CONTRACT.md, @HANDOFF.md and @DECISIONS.md before doing
anything else. They are not background reading. The contract governs scope and a
global evidence-gate hook will block your edits if they do not match it.

Context in three lines. Custody is a provenance layer over ADK agent memory,
targeting the All Things Agentic Hackathon under the Fortified Enterprise Fleet
track; submission closes 2026-08-31 17:00 PDT, which is 2026-09-01 05:30 IST. Two
predecessor projects were killed on measurement, both recorded so you do not
rebuild them. The core is built and verified against real google-adk 2.6.3: 52
tests, lint clean, entirely offline.

**Start by telling me whether the Google Cloud account is usable, then take the
matching branch.**

If it is usable, run the three day-one checks before writing any code, and report
each with the command you ran:

1. Does Memory Bank support **deleting** a memory? G3's revocation path assumes
   it. The fallback is post-filtering retrieval, and knowing which one applies
   changes the design.
2. Does Vertex's `agent_engines.memories.retrieve` accept **filters** that ADK
   does not pass through? If it does, G2 gets simpler.
3. Are the GEAP components reachable on a fresh trial account at all? A 200 on
   any other account is not evidence, and a 404 or PERMISSION_DENIED is a
   kill-condition input rather than a config nuisance.

Then G1: the smallest deployed skeleton on Cloud Run with one ADK agent, a real
Gemini 3.5+ call through Vertex, and memory written through live Memory Bank.
Deploy before building inward. The predecessor left deployment last and it stayed
blocked for the project's entire life.

If the account is not usable, build staging item one instead: the **derivation
graph and retroactive revocation**, offline. Custody records need `derived_from`,
and G3 needs graph traversal plus a replay that removes nothing further and
creates no duplicate records. This is the differentiator and it needs no cloud.

Five rules that matter more than they look:

1. **Test the load-bearing claim before you commit around it.** On 2026-08-09,
   three separate times, a risk was named in a commit message instead of checked,
   and every check turned out to be cheap. If a decision rests on an assumption,
   verify it first or say plainly that you have not.
2. **No model decides a fact.** Origin and derivation come from event structure,
   which is why `Event.get_function_responses()` is load-bearing. Gemini may
   summarise, explain and rank. It may never label, adjudicate or set trust.
3. **No GEAP row moves to BUILT without a command that demonstrates it.** A
   predecessor shipped a table describing an integration that did not exist.
4. **No new agent unless it enforces a correctness property or changes what a
   human does.** Two were designed and cut under this rule; `DECISIONS.md` §6
   names them and says why they must not return.
5. **Commit only when I authorize it, and never push without asking.** No em
   dashes anywhere in code, comments, commits or docs. Update the contract before
   widening scope, not after.

Work in small verified steps and run `make check` before every commit. If
anything I ask for contradicts the contract or the evidence already gathered, say
so instead of building it.
