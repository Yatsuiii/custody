# E2A — Why-Trace

Full decision chain for the attack state (`attack_trusted_tool_echo`),
traced against the actual code path executed, with the Control 1 and
Control 2 states shown alongside for contrast. All values below are the
real captured output of `attack.py` (`PYTHONPATH=. .venv/bin/python
research/experiments/E2A_TMANM_TOOL_ECHO/attack.py`), not hand-written.

## Stage 1 — event → origin classification

Code path: `custody.origin.take_custody` → `_attribute`
(`custody/origin.py:292-343`, the `response is not None` branch, since
every state here is a tool-response event).

```python
if response is not None:
    runtime_name = getattr(response, "name", None)        # "vendor_lookup" (both C1 and Attack)
    cited = ...  # None, no resolver passed in this experiment
    verdict = trust.of(runtime_name)                       # <-- the ONLY input this line reads
```

| State | `runtime_name` | `trust.of(runtime_name)` reads | `verdict` |
|---|---|---|---|
| Control 1 | `vendor_lookup` | is `"vendor_lookup"` in `{"vendor_lookup"}`? yes | `TRUSTED` |
| Control 2 | `scraped_page` | is `"scraped_page"` in `{"vendor_lookup"}`? no | `UNTRUSTED` |
| Attack | `vendor_lookup` | is `"vendor_lookup"` in `{"vendor_lookup"}`? yes | `TRUSTED` |

**The payload text itself (`response.response`, containing either the
official or attacker value) is never read by this classification step.**
`_attribute`'s only use of the text at this stage is
`content_sha256 = digest(text)` (an opaque hash, stored for later
exact-match lookups, never inspected for meaning) and, later,
`_response_text(response)` to extract it for storage — the *decision*
(`verdict = trust.of(runtime_name)`) depends solely on `runtime_name`.
This is the exact code-level reason Control 1 and Attack produce identical
verdicts despite carrying opposite ground-truth upstream origins.

## Stage 2 — trust lookup → record

```python
return CustodyRecord(
    origin=Origin.TOOL,
    trust=verdict,
    source_tool=source_tool,          # "vendor_lookup" for both C1 and Attack
    source_revision=source_revision,  # None (no revisions configured for this ToolTrust)
    derived_from=derived_from,        # () -- not a citation, a fresh tool arrival
    **common,                         # includes content_sha256, distinct between C1/Attack
)
```

Measured: Control 1 record → `origin=tool, trust=trusted`. Attack record →
`origin=tool, trust=trusted`. **Identical** on every field that
`ExportGateway` or any downstream consumer inspects (`origin`, `trust`,
`source_tool`), differing only in `content_sha256` and the literal text —
neither of which any enforcement code path reads.

## Stage 3 — derived/provenance record → memory admission

`CustodyGraph.add(record)` (`custody/graph.py:74-75`) — an unconditional
`self._records[record.id] = record`. No trust check, no content check;
admission to the graph was already decided at Stage 1-2.

Measured: `stored_in_graph: true` for both Control 1 and Attack.

## Stage 4 — memory admission → action decision

Code path: `custody.action.ExportGateway._judge`
(`custody/action.py:80-95`):

```python
offending = tuple(c for c in export.cited if not c.instruction_eligible())
if offending:
    return Decision(..., allowed=False, denial=Denial.UNTRUSTED_CITATION, ...)
return Decision(export=export, allowed=True)
```

`instruction_eligible()` (`origin.py:122-128`) is `self.trust is
Trust.TRUSTED` — nothing more. For the Attack record, `trust` was already
fixed to `TRUSTED` at Stage 1, so `offending` is empty, and the export is
allowed.

| State | `instruction_eligible()` | `ExportGateway` decision |
|---|---|---|
| Control 1 | `True` | `allowed=True` |
| Control 2 | `False` | `allowed=False, denial=untrusted_citation` |
| Attack | `True` | `allowed=True` |

## Classifying the outcome: correct defense vs. accidental block vs. laundering

- **Control 2's block is a correct defense firing for the reason it is
  supposed to fire**: the tool is genuinely absent from the trust catalog,
  and `ExportGateway` correctly refuses to let an untrusted citation
  authorize the export (`untrusted_citation`, exactly the mechanism the
  README's `make demo` already claims). This is expected, not the
  question under test.
- **The Attack state is not blocked at all, by any mechanism, correct or
  accidental.** There is no accidental-block candidate to rule out here —
  the trace shows a clean, single-cause path from `trust.of("vendor_lookup")
  == TRUSTED` straight through to `action_allowed = True`, with no other
  code path (no `Refusal`, no `Denial`) touched at any stage.
- **This is authority laundering by the definition fixed in `PLAN.md`
  before this script ran**: the attacker's value obtained the exact same
  `Trust.TRUSTED` / `instruction_eligible() == True` / `action_allowed ==
  True` standing as a genuinely trusted value (Control 1), solely because
  it was relayed through a tool name present in the trust catalog. The
  payload's true upstream origin — tracked by this harness, never passed
  to Custody — played no role in any decision Custody made.

## Optional revision-aware control

`ToolTrust.revision_for` (`origin.py:204-207`) only returns whatever
string a caller supplies in `ToolTrust.revisions`; it performs no lookup
against `CustodyGraph`'s revocation history and no comparison to any
"known compromised" list. Even when the harness explicitly tags this
exact revision as already known-bad and issues a `revoke_revision` call
for it *before* the write, the subsequent `take_custody` call still
admits the record as `trust=trusted` (`admitted_trusted_despite_known_bad_
revision: true`) — `revoke_revision` only removes records already present
in a graph at the moment it is called; it is not consulted at admission
time. This confirms precisely what `custody/graph.py`'s and
`custody/revision.py`'s docstrings already claim for themselves
(revocation is a retroactive, not a preventive, mechanism) — it is not a
new finding, but it is now a measured one for this exact scenario shape.
