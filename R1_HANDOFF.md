# R1 hardening handoff, 2026-08-14

> **CLOSED 2026-08-14. Kept as the record of why the change was made.**
> Every step below shipped, plus two upgrades this file had listed as out
> of scope in section 10: the approval now also binds the Cloud Run
> resolved image digest (a `RUNTIME_DRIFT` denial on a same-schema,
> different-image swap), and both `RevisionCatalog` and the dispatch nonce
> ledger are Firestore-backed rather than in-memory. R1 was re-run live
> (`make registry-gates` 9/9), R2 gained a seventh control proving a
> consumed nonce is still refused by a genuinely fresh process
> (`make revision-binding-gates` 16/16), and the suite went 319 -> 345
> with 0 skipped. Remaining submission work is in `SUBMISSION_HANDOFF.md`,
> not here.

This file is for a **fresh session implementing the R1 fix**. It assumes no
prior context. If you are judging the submission instead, read
`EVALUATION_GUIDE.md`. If you are continuing general build work, read
`HANDOFF.md`.

Everything below was found during a read-only judging pass. No code was
changed in that session. `git status` was clean when this file was written.

---

## 0. What you are fixing, in one sentence

`custody/revision.py` computes a tool's `revision` (its identity digest) on
every access, but that digest gets **stored** — in the derivation graph, in
Firestore, in Agent Registry, in every `proof-out/*.json`. Nothing records
which version of the algorithm produced a stored digest, so changing the
algorithm silently invalidates every digest already written, and one of the
three places that compare digests fails **open** when it happens.

This already happened once. It is currently live in the repo.

---

## 1. Reproduce it before you touch anything

Do not start editing on trust. Run this first:

```bash
.venv/bin/python - <<'PY'
import json, sys, hashlib
sys.path.insert(0, '.')
from custody.revision import ToolSurface

e = json.load(open('proof-out/live-registry-attack.json'))
server = e["cloud_run"]["service"]
approved = ToolSurface.from_tools_list(server=server, payload=e["registry"]["content_before_v2"])
observed = ToolSurface.from_tools_list(server=server, payload=e["surfaces"]["live_v2"])

print("recorded approved_revision:", e["surfaces"]["approved_revision"])
print("recomputed now            :", approved.tools[0].revision)
print("recorded observed_revision:", e["surfaces"]["observed_revision"])
print("recomputed now            :", observed.tools[0].revision)
PY
```

Expected output today:

```
recorded approved_revision: e5f7639ef7b959442f4df88e4a61b22e11ca3fa1f664383e4d23270844c37509
recomputed now            : f4e1a2f2941fef78fe0df0a6fdf2c984624dfb5af99ff55b51ed83a2a073a138
recorded observed_revision: a418b10c257cbbc852c3303a7f0a9c149edfaff7ac99f017d503479d957ee3f0
recomputed now            : 32d310a248a39898eb8571e42b6244e0dd73d2eabc25e251e6abbadb58fea8c8
```

Then confirm the consequence:

```bash
.venv/bin/python -c "
import json, sys; sys.path.insert(0,'.')
from scripts.registry_gates import judge
r = judge(json.load(open('proof-out/live-registry-attack.json')))
print(f'{sum(r.values())}/{len(r)} pass')
print('FAILING:', [k for k,v in r.items() if not v])
"
```

Expected today: `4/8 pass`, failing
`['fresh_live_evidence', 'live_surface_changed', 'custody_blocked_before_dispatch', 'revision_specific_descendants_revoked']`.

Only the first is a freshness expiry. The other three are substantive: they
all recompute a digest and compare it to the recorded one.

### The cause, already confirmed

Commit `7f7ea00` ("Close R1's dispatch TOCTOU and land selective live Memory
Bank deletion (R2, D2)", 2026-08-13 23:28:11 +0530) added this line to
`ToolSurface.from_tools_list`, now at `custody/revision.py:113`:

```python
identity = {key: value for key, value in raw.items() if key != "_meta"}
```

The reasoning was correct on its own terms (R2's attestation token rides in
`_meta` and is minted fresh on every `tools/list`, so digesting it would make
a revision change on every read). The problem is not the change. The problem
is that it silently redefined every digest already written, and nothing
noticed.

Proof that this is the cause, not a coincidence: sha256 of the recorded
`tools[0]` **including** `_meta` reproduces `e5f7639e…` and `a418b10c…`
exactly. Excluding `_meta` produces the current values. The R1 artifact was
captured 2026-08-13T08:06:46Z, about ten hours before that commit.

### The smoking gun already sitting in `proof-out/`

`proof-out/live-revision-binding.json` (R2, captured after the change)
records:

```
v1_token.revision = f4e1a2f2941fef78fe0df0a6fdf2c984624dfb5af99ff55b51ed83a2a073a138
v2_token.revision = 32d310a248a39898eb8571e42b6244e0dd73d2eabc25e251e6abbadb58fea8c8
```

Those are the same two tools, on the same server, as R1's `e5f7639e…` and
`a418b10c…`. **Two different identities for the same tool sit in the same
evidence directory right now, and nothing in the repo detects it.** Keep
this pair; it is your regression fixture for step 4.

---

## 2. The part that is worse than rotted evidence

`custody/graph.py:110-117`:

```python
def descendants_for_revision(self, *, tool: str, revision: str) -> tuple[str, ...]:
    """Every record descended from one exact admitted tool definition."""
    roots = {
        r.id
        for r in self._records.values()
        if r.source_tool == tool and r.source_revision == revision
    }
    return self._walk(roots)
```

Exact string equality. If the algorithm moved, no stored `source_revision`
matches, `roots` is empty, `_walk` returns `()`, and `_revoke`
(`custody/graph.py:147-163`) deletes nothing, logs a `Revocation` with
`removed=()`, and **returns successfully**.

So after a digest change, a revision-specific revocation against
already-stored records removes nothing and reports success. Fail-open,
silent, on the revocation path. That is the one path this product cannot be
wrong on, and it is the actual bug. The broken R1 artifact is only the
symptom that made it visible.

---

## 3. Complete map: every place a revision string is born, stored, or compared

You need all three lists before editing. They are short, and they are
complete (grepped, not guessed).

**Born — exactly one producer:**

- `custody/revision.py:69-70` — `ToolDefinition.revision`, a property calling
- `custody/revision.py:201-205` — `_digest(definition)`

**Compared — exactly three sites:**

| Site | Code | Correct behavior on version mismatch |
| --- | --- | --- |
| `custody/revision.py:189` | `RevisionCatalog.admit`: `live.revision != approved.revision` | fail **closed**, with its own denial reason |
| `custody/graph.py:115` | `descendants_for_revision`: `r.source_revision == revision` | fail **loud** (raise) |
| `custody/revision.py:307` | `AttestationAuthority.verify`: `token.revision != live_revision` | already correct, see step 5 |

That the same condition needs two different behaviors at two different sites
is the real design work here. Do not paper over it with one shared helper
that returns a bool.

**Stored into:**

- `custody/origin.py:105` — `CustodyRecord.source_revision`, set at
  `origin.py:328` from `ToolTrust.revision_for` (`origin.py:204-207`) and
  propagated at `origin.py:323`, `:335`, `:350-363`, `:375`
- `custody/graph.py:54` — `Revocation.revision`
- `custody/store.py:56` (write) and `:73` (read) — offline SQLite
- `custody/firestore_store.py:45` (write), `:59` (read), `:71`
  (`Revocation.revision`) — live Firestore
- Agent Registry, externally, via `scripts/live_registry_attack.py`
- every `proof-out/*.json` that embeds a digest

---

## 4. Why 319/319 tests passed while this broke

This is the most important paragraph in the file. Do not skip it, because it
tells you what kind of test to write.

Existing coverage is real but structurally blind:

- `tests/test_revision.py:40` `test_schema_key_order_and_tool_order_do_not_change_a_revision` — compares two digests, **both computed in the same process**.
- `tests/test_revision.py:57` `test_per_response_meta_does_not_change_a_revision` — added *with* the breaking change, asserts the new behavior, passes.
- `tests/test_graph.py:118` `RevisionRevocationIsPrecise` — one test, matching-revision case only. No unknown-algorithm case exists.

**Every revision test in this repo compares two digests computed by the same
code in the same process.** The bug is only visible across a code-version
boundary, and nothing in the suite crosses one. That is why the fix needs
two new kinds of test: one that pins an absolute value (step 4a), and one
that reads a value written by an older process (step 7).

---

## 5. The work, in order

Order matters. Regenerating the R1 artifact is **last**, because doing it
first would make the symptom disappear while leaving the hole open.

### Step 1 — Golden-digest test (do this first, ~15 min)

**Why.** It is the only guard that fires at the moment of the edit rather
than hours later. It would have caught `7f7ea00` at commit time.

**Where.** `tests/test_revision.py`, alongside the existing
`StaleRegistryMetadataIsReproducible` class.

**What.** A frozen tool-definition fixture written inline in the test file,
plus a hardcoded expected digest. Inline, not read from `proof-out/` —
`proof-out/` is gitignored (`.gitignore:5`), so a fixture read from there
would silently skip on a fresh clone.

```python
class TheDigestAlgorithmIsPinned(unittest.TestCase):
    """A digest is a stored fact, so its algorithm is a wire contract.

    Changing canonicalization silently redefines every revision already
    written to the graph, to Firestore, to Agent Registry, and to every
    captured artifact. This test exists so that change cannot be made
    accidentally: it must be made together with a version bump.
    """

    def test_a_known_definition_digests_to_a_known_value(self):
        ...
```

**How you know it worked.** Temporarily delete the `if key != "_meta"` filter
at `custody/revision.py:113`, run `make check`, watch this test fail with a
message that names the version bump. Then revert.

### Step 2 — Version the digest so stored revisions are self-describing

**Why.** Detection is the safety property. Once a stored digest carries its
own algorithm tag, a version boundary stops looking identical to a security
event, which is what makes the other two steps possible.

**Where.** `custody/revision.py`.

**What.** Make `_digest` return a prefixed string and add one reader-side
helper:

```python
#: Bumped whenever canonicalization changes. A stored revision carries this
#: tag so a later reader can tell "computed differently" from "changed".
DIGEST_ALGORITHM = "sha256/2"


def _digest(definition: Mapping[str, object]) -> str:
    canonical = json.dumps(
        definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return f"{DIGEST_ALGORITHM}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def algorithm_of(revision: str) -> str:
    """Which algorithm produced this revision string.

    Bare hex predates versioned revisions. It is deliberately reported as
    ``sha256/legacy`` rather than as any real version: revisions written
    before and after the ``_meta`` change are both bare hex and cannot be
    told apart, so neither may be treated as comparable to a current one.
    """
    head, separator, rest = revision.partition(":")
    return head if separator else "sha256/legacy"
```

**Decision you are being handed, already made.** Old algorithm versions are
made **detectable, not recomputable**. Keeping v1 recomputable would mean
`ToolDefinition` retaining the un-stripped `_meta` dict forever, and there is
a real security argument that if the meaning of "identity" changed, prior
approvals should be re-earned rather than grandfathered. If you disagree
after reading step 7, the alternative is to keep both dicts on
`ToolDefinition` and register `{"sha256/1": ..., "sha256/2": ...}` — but do
not do that silently, record the reversal in `DECISIONS.md`.

**Migration.** Existing bare-hex values in Firestore and SQLite stay
readable and stay revocable **by tool** (`CustodyGraph.revoke` ignores
revision entirely). Only `revoke_revision` refuses them, which is the safe
direction. No data migration is required. The only durable graph content
today is proof-run probe records, so if you would rather clear them than
carry `sha256/legacy`, that is acceptable — say which you did in
`DECISIONS.md`.

### Step 3 — Make the revocation path fail loud

**Why.** This is the actual bug from section 2. Fixing it depends on step 2,
because you cannot detect a version boundary without version tags.

**Where.** `custody/graph.py`, `descendants_for_revision`.

**What.** Distinguish the two cases that currently both return `()`:

- **No records for this tool at all** — an empty result is correct, stay
  silent.
- **Records exist for this tool, but none was computed under the requested
  algorithm** — the caller is comparing across a version boundary. Raise.

```python
stored = {
    r.source_revision
    for r in self._records.values()
    if r.source_tool == tool and r.source_revision
}
if stored and algorithm_of(revision) not in {algorithm_of(s) for s in stored}:
    raise RevisionAlgorithmMismatch(...)
```

`custody/graph.py` currently defines no exception classes of its own (only
`Revocation` at line 42 and `CustodyGraph` at line 62), so you are adding the
first one. Put `RevisionAlgorithmMismatch` in `custody/revision.py` next to
the existing `ToolSurfaceError` and `ToolCallDenied` (lines 29 and 46) rather
than in `graph.py`: the condition is about revision identity, which
`revision.py` owns, so importing one error name and `algorithm_of` is a
smaller coupling than teaching `graph.py` to own a revision concept.

Import safety, checked so you do not have to: `graph.py` already imports
`CustodyRecord` from `custody.origin` (`graph.py:38`), `revision.py` imports
`ToolTrust` from the same module (`revision.py:26`), and `origin.py` imports
nothing from `custody` at all. So `graph -> revision -> origin` introduces no
cycle. `graph.py`'s docstring line 19 ("this pure module deliberately does
not import") is about a **live cloud client**, not about sibling pure
modules — it does not forbid this.

Get this condition exactly right — it is the subtle part of the whole change.
An over-eager raise breaks legitimate "nothing matched" revocations; an
under-eager one leaves the fail-open in place.

**Tests to add** in `tests/test_graph.py`, next to `RevisionRevocationIsPrecise`:

1. records exist under `sha256/2`, caller asks under `sha256/legacy` → raises
2. records exist under `sha256/2`, caller asks under `sha256/2` for a
   revision that genuinely has no descendants → returns empty, does not raise
3. no records for the tool at all → returns empty, does not raise

### Step 4 — Make admission fail closed with its own reason

**Why.** Today an algorithm change surfaces as `Denial.REVISION_MISMATCH`,
which is a **security event**. A tooling change must never be reported in the
same vocabulary as an attack: it sends an operator hunting a compromise that
did not happen.

**Where.** `custody/revision.py`, `Denial` (line 33) and
`RevisionCatalog.admit` (line 189).

**What.** Add a member such as `ALGORITHM_SUPERSEDED = "algorithm_superseded"`
with a comment explaining it is an operational condition, not a security one,
and return it from `admit` when
`algorithm_of(live.revision) != algorithm_of(approved.revision)`. Still deny
— fail closed — just under an honest name.

**Test** in `tests/test_revision.py`: an approved pin under one algorithm and
a live surface under another denies with `ALGORITHM_SUPERSEDED`, not
`REVISION_MISMATCH`.

### Step 5 — `AttestationAuthority.verify` needs no change; write down why

`custody/revision.py:307` compares `token.revision != live_revision`. Minting
and verification happen in the same process against the same code, so the
algorithm is always consistent. Across a redeploy that changed the algorithm,
the prefixed strings differ and it returns `Denial.DIGEST_MISMATCH` — already
fail-closed and already correct.

Add one comment saying so. An unexplained absence of a check in a file where
two neighbours just gained one reads as an oversight to the next reader.

### Step 6 — A test that re-judges whatever artifacts exist

**Why.** Steps 1-5 close the digest case. This closes the whole class: any
future change that invalidates any captured artifact turns `make check` red
instead of waiting for a judge to find it.

**Where.** New file, `tests/test_stored_artifacts.py`.

**What.** For each artifact present in `proof-out/`, run its own offline
judge and assert every gate passes **except** freshness. Skip, do not fail,
when the artifact is absent, so a fresh clone stays green.

The freshness keys to exempt are exactly `fresh_live_evidence` and
`fresh_bounded_live_evidence`.

This mapping is verified — every one of these was executed during the judging
pass:

| Artifact | Judge |
| --- | --- |
| `live-registry-attack.json` | `scripts.registry_gates.judge` |
| `live-gateway.json` | `scripts.gateway_gates.judge` |
| `live-revision-binding.json` | `scripts.revision_binding_gates.judge` |
| `live-memory-deletion.json` | `scripts.memory_deletion_gates.judge` |
| `live-model-armor.json` | `scripts.model_armor_gates.judge` |
| `live-observability.json` | `scripts.observability_gates.judge` |
| `live-chain.json` | `scripts.chain_gates.judge_offline` |
| `live-fleet.json` | `scripts.fleet_gates.judge_offline` |
| `live-narration.json` | `scripts.narration_gates.judge_offline` |
| `live-review.json` | `scripts.review_gates.judge_offline` |
| `live-auditor.json` | `scripts.auditor_gates.judge_offline` |

**Expected result when you first write it:** it FAILS, on
`live-registry-attack.json` only, for the three substantive gates. That is
correct and is the point. Step 8 turns it green. Every other artifact passes
its offline judge today (verified: R2 9/9, D1/D2 7/7, Auditor 8/8, Reviewer
8/8, Narration 13/13, Fleet 10/10, F1 14/14; S1 11/12, M1 5/6, O1 4/5 with
freshness as the only failure).

### Step 7 — Record what produced each artifact

**Why.** Turns "digests do not match" into "captured under `7f7ea00` with
`sha256/1`; you are on `560997f` with `sha256/2`". Diagnosis in one line
instead of an afternoon.

**Where.** `scripts/live_registry_attack.py` and
`scripts/live_revision_binding.py` — the two producers whose artifacts embed
digests. Keep the diff to those two.

**What.** At artifact-write time, record `code_revision` (the git SHA of
`HEAD` at capture) and `digest_algorithm` (`custody.revision.DIGEST_ALGORITHM`).
Then have `registry_gates.judge` report the recorded algorithm in its failure
message when it differs from the current one.

Adding these fields to the other ten producers is a mechanical follow-up, not
part of this change. Do not expand the diff.

### Step 8 — Regenerate R1, and only now

**Why last.** Regenerating first hides the symptom and leaves everything
above unbuilt.

**Risk warning.** This is the only step that deploys anything. It deploys a
v1 and then a v2 FastMCP service to Cloud Run and rewrites Agent Registry
metadata. It was **not** re-run during the judging pass, so whether it still
passes end to end today is unverified. Budget for it failing on unrelated
cloud drift, and do not start it with fifteen minutes left.

Credentials, per `EVALUATION_GUIDE.md:86-95`: the project's resources live under
`project-988bc9fe-092c-4b32-90c`, owned by `yoursturuly@gmail.com`. The
environment's default `gcloud` config is authenticated as a **different**
account against an unrelated project, so pass the repo's own config
explicitly:

```bash
CLOUDSDK_CONFIG="$PWD/.gcloud" \
CUSTODY_PROJECT=project-988bc9fe-092c-4b32-90c \
make live-registry-attack

CLOUDSDK_CONFIG="$PWD/.gcloud" make registry-gates   # expect 8/8
```

Then the page:

```bash
make gui        # regenerates web/incident.html and web/architecture.html
```

**Redeploy is manual and needs the user's explicit go-ahead** — it is a
production deploy of a public page. Two things `HANDOFF.md:48-70` learned the
hard way:

- Deploy from disk with the authenticated `vercel` CLI
  (`vercel link --project custody-incident`, then `vercel deploy --prod`).
  Do **not** use the `deploy_to_vercel` MCP tool: passing the large file
  contents as a JSON tool parameter silently corrupted
  `architecture.html`'s inline `<script>` once, leaving every widget blank on
  the live page. It was not visually obvious from a screenshot.
- After any redeploy, check the browser console, not just that the deploy
  call returned success.

---

## 6. Optional, only if step 8 goes smoothly: the GUI badge

Not required for the fix, and genuinely separable. Listed because it is the
reason a broken artifact looked healthy for a day.

`scripts/render_architecture.py` renders each live-proof row from the
artifact's recorded fields and gives every row the same green `EVIDENCE`
chip. `age_string` (`render_architecture.py:109-120`) prints an age but there
is no staleness threshold anywhere in the renderer, so the page's own claim
that "a missing or stale file is labeled as such, not hidden" is only half
true: missing is handled, stale is not. As of this writing R1 (28h), S1
(25h), M1 (25h) and O1 (24h) are all past the project's own 24-hour rule and
carry the same chip as a 14-minute-old artifact.

Fix: compute the chip by calling the row's offline judge (step 6 already
gives you the mapping) and render PASS / STALE / FAILING. The CSS already has
a `BLOCKED` warning style to borrow.

---

## 7. Acceptance gates

1. `custody/revision.py`'s canonicalization cannot change without a failing
   test that names the version bump.
2. `CustodyGraph.revoke_revision` against records whose algorithm differs
   raises, proven by a test. It never returns an empty success.
3. A genuinely empty revision-revocation under a matching algorithm still
   returns empty and does **not** raise, proven by a separate test.
4. An algorithm boundary denies admission under its own reason, never as
   `REVISION_MISMATCH`.
5. `make check` fails if any artifact in `proof-out/` fails its own offline
   judge for a reason other than freshness.
6. After step 8, `make registry-gates` reports 8/8.

Gates 1-5 are what make this foolproof. Gate 6 is cleanup.

---

## 8. Verification

```bash
make check      # expect: ruff clean, 322+ tests (319 today + the new ones), 0 skipped
make gates      # expect: G1-G4 PASS, G5 BLOCKED, unchanged
make incident   # expect: unchanged output
```

Baseline measured 2026-08-14, before any of this work:

- `make check` — ruff clean, **319 tests, 0 skipped, 0 failures**, 0.12s, no network
- `make gates` — G1 PASS, G2 PASS, G3 PASS, G4 PASS, G5 BLOCKED
- `make registry-gates` (offline half) — **4/8**, three substantive failures
- google-adk 2.6.3 installed; `tests/test_adk_conformance.py` runs 9 real tests, not skipped

Manual: after step 8, load `custody-incident-cave2.vercel.app/architecture.html`
in a browser and confirm R1's two digests match a fresh recomputation, and
that the console is clean.

---

## 9. Paste this into `.claude/SESSION_CONTRACT.md` before you edit anything

The global evidence-gate hook blocks edits when the contract does not cover
the work.

```
## Sub-build: R1 digest versioning and the fail-open revocation path (opened <date>)

Objective: a change to custody/revision.py's canonicalization silently
invalidated every revision digest already written, and CustodyGraph's
revision-specific revocation fails open when that happens: it removes
nothing and reports success. Make a stored digest self-describing, make
the revocation path fail loud, make admission fail closed under its own
reason, and add the two kinds of test that would have caught it.

Branch: feat/memory-provenance
Parent: 560997f

Allowed files: custody/revision.py, custody/graph.py, tests/test_revision.py,
tests/test_graph.py, a new tests/test_stored_artifacts.py,
scripts/registry_gates.py, scripts/live_registry_attack.py,
scripts/live_revision_binding.py, DECISIONS.md, HANDOFF.md,
.claude/SESSION_CONTRACT.md, proof-out/*. Optionally
scripts/render_architecture.py and web/* for the badge in section 6.

Non-goals:

- No change to custody/origin.py, custody/service.py, custody/store.py,
  custody/firestore_store.py or any custody/adapters/* file. Stored
  bare-hex revisions stay readable and stay revocable by tool; only
  revoke_revision refuses them, which is the safe direction. No data
  migration.
- No new live capability, no new Cloud Run service beyond what
  make live-registry-attack already redeploys, no new GUI section.
- Do not add code_revision/digest_algorithm to the other ten producers.

Baseline: make check 319/319 offline with 0 skipped, make gates G1-G4
PASS / G5 BLOCKED, make registry-gates 4/8 offline with three substantive
failures (live_surface_changed, custody_blocked_before_dispatch,
revision_specific_descendants_revoked). Record all three before editing.

Acceptance gates: the six in R1_HANDOFF.md section 7.

Verification: make check, make gates, make incident, then
make live-registry-attack and make registry-gates (8/8), then make gui
and a manual browser check of the redeployed page.

Status: active
```

---

## 10. What this does not fix

State these plainly; do not let the fix drift into claiming them.

- **Declared surface only.** A behavior-only change under an identical
  `tools/list` stays undetected. Nothing here attests the server's running
  code, only the schema it declares. The cheap real upgrade, if you want one
  later, is to bind the Cloud Run **revision name and image digest** into the
  approval alongside the surface digest — `scripts/live_registry_attack.py`
  already reads Cloud Run revisions, so the data is at hand. That would take
  R1 from "declared surface drift" to "declared surface or running image
  drift". Full runtime attestation is Binary Authorization territory; do not
  claim it.
- **`RevisionCatalog` is an in-memory spike**, by its own docstring
  (`custody/revision.py:158-165`: "A production pivot must add a durable
  implementation behind this same interface before claiming a live Registry
  integration"). Approved pins do not survive a restart. `README.md`'s
  "Agent Registry and live stale-tool admission — **built**" row sits on top
  of that. Either back it with the Firestore store that already exists, or
  narrow the row's wording. Out of scope here, but a judge can find the
  docstring.
- **The replay ledger is process-local**, the same single-instance scope R1,
  R2 and S1 already state.
- **Time-of-check/time-of-use** between a surface read and a later allowed
  dispatch is closed by R2 for the owned server, not by R1. R1's README
  paragraph should point at R2 rather than restating the gap as open.

---

## 11. What was not verified when this was written

Named explicitly so the next session does not inherit them as facts.

- **No live proof was re-run.** Every finding above is from offline judges,
  stored artifacts, source, and git history. The live half of every gate —
  Memory Bank rereads, Cloud Logging insert-ID rereads, Cloud Run revision
  rereads, the Gemini and Cloud Text-to-Speech re-calls — is unverified.
- **Whether `make live-registry-attack` still passes end to end today is
  unknown.** It was last run 2026-08-13T08:06Z. Step 8 is the first time
  anyone will find out.
- **Whether a fresh `sha256/2` R1 run passes all eight gates** is therefore
  also unknown. If it does not, the failure is more likely cloud drift than
  this change; check `registry-gates` output before assuming you broke
  something.
- The Cloud Run control plane was confirmed live during the judging pass
  (`GET https://custody-control-plane-anexdhueiq-uc.a.run.app/health` returned
  HTTP 200 `{"status":"ok"}`), and both Vercel pages were confirmed live,
  byte-identical to `web/`, and rendering with zero console errors. Those are
  the only live facts in this file.
