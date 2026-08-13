"""The one deterministic mapping a `CustodyRecord` needs to be deletable.

Verified live 2026-08-13 against Agent Engine `6936011268348182528`:
`agent_engines.memories.create(config={"memory_id": <id>})` does not share
`ingest_events`'s server-side consolidation, so pinning `memory_id` to a
record's own id gives a real, one-to-one, independently deletable memory,
with nothing to search for and nothing to store: given a record id, the
`memory_id` it was written under is always this same computation. See
`DECISIONS.md` #2 for the finding this closes.
"""

from __future__ import annotations

import hashlib

#: Every character this project's account rejected a `memory_id` for is
#: something a hash never produces, regardless of what `record.id` contains.
_PREFIX = "cr-"


def memory_id_for(record_id: str) -> str:
    """A Memory Bank `memory_id`: lowercase letters, digits, hyphens only,
    starting with a letter. `CustodyRecord.id` is colon-joined
    (`f"{invocation}:{index}:{part_index}"`) and not valid on its own;
    hashing sidesteps that instead of sanitizing it field by field.
    """
    digest = hashlib.sha256(record_id.encode("utf-8")).hexdigest()
    return f"{_PREFIX}{digest[:32]}"
