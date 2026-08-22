# E2C — Why-Trace

All values below are the real captured output of `attack.py`
(`PYTHONPATH=. .venv/bin/python
research/experiments/E2C_EXACT_VS_TRANSFORMED/attack.py`).

## Common chain, all four cases

```
Root: vendor_registry (TRUSTED) -> "Acme's payment account is ACCT-SAFE-11."
    -> take_custody -> CustodyRecord(origin=TOOL, trust=TRUSTED)
    -> graph.add(root_record)   # trusted, so it enters the searchable graph

Case <X>: load_memory -> <case text>
    -> graph.resolve(digest(case_text))
    -> _attribute (origin.py:312-318): cited = resolver.resolve(content_sha256)
```

## The exact code line where every case's fate is decided

`custody/graph.py:187-197`, `CustodyGraph.resolve`:

```python
def resolve(self, content_sha256: str) -> CustodyRecord | None:
    for record in self._records.values():
        if record.content_sha256 == content_sha256:
            return record
    return None
```

`content_sha256` is `hashlib.sha256(text.encode("utf-8")).hexdigest()`
(`custody/origin.py:174-175`, `digest()`) — a cryptographic hash with no
distance/similarity structure at all. `==` on two SHA-256 digests is
binary: either the underlying bytes were identical, or the digests share
no informative relationship whatsoever, regardless of how small the
underlying text change was.

| Case | Text vs. root | `digest(text) == digest(root)`? | `resolve()` |
|---|---|---|---|
| A | byte-identical | `True` | **hit**, returns root record |
| B | root minus one trailing period | `False` | **miss**, `None` |
| C | same proposition, reworded | `False` | **miss**, `None` |
| D | unrelated proposition | `False` | **miss**, `None` |

**This is the first, and only, point of divergence between Case A and
every other case.** Nothing downstream of `resolve()` treats B, C, and D
differently from each other in any way — they are, from this line onward,
structurally indistinguishable to Custody.

## What happens after the miss (B, C, D identically)

```python
# origin.py:312-329, when cited is None:
verdict = trust.of(runtime_name)   # runtime_name == "load_memory"
```

`ToolTrust.of("load_memory")` (`origin.py:194-197`): is `"load_memory"` in
`{"vendor_registry"}` (the only entry in this experiment's trust set)? No.
`verdict = Trust.UNTRUSTED`, unconditionally, for B, C, and D alike.

Measured: `trust`, `derived_from` (`[]`), `instruction_eligible`
(`False`), and the `ExportGateway` decision (`allowed=False,
denial=untrusted_citation`) are **byte-for-byte identical** across B, C,
and D — not merely similar outcomes reached by different paths, but the
literal same values, because they are the literal same code path
(`trust.of(runtime_name)` returning `UNTRUSTED`, then
`ExportGateway._judge` refusing on `not c.instruction_eligible()`).

## What happens on the hit (Case A only)

```python
# origin.py:319-323, when cited is not None:
verdict = cited.trust                 # TRUSTED (the root's own trust)
derived_from = (cited.id,)            # a real graph edge to the root
source_tool = cited.source_tool
source_revision = cited.source_revision
```

Measured: `trust=trusted`, `derived_from=["inv-e2c-root:0:0"]` (the root's
actual id), `instruction_eligible=True`, `action_allowed=True`. This
record genuinely inherits the root's standing through a real graph edge —
not a default, an actual inheritance.

## Boundary characterization

There is no gradient and no partial credit. `SHA-256` equality is the
entire test; a single removed character (Case B) produces exactly as
total a miss as a fully reworded sentence (Case C) or a wholly unrelated
proposition (Case D). The three failing cases are not merely similar in
outcome, they are computationally identical in outcome — `resolve()`
cannot express "close" in any sense; a match is total or the record is
evaluated as if it had never been written at all.
