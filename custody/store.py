"""Durable stores, behind the same ports their in-memory counterparts serve.

A real deployment gets redeployed. Quarantine, the derivation graph, and the
trust catalog all have to survive that or G3 and G5 cannot be demonstrated
with genuine elapsed time: a Cloud Run restart would otherwise erase every
custody record, revocation, and grant made before it. SQLite is the offline
stand-in for the `quarantine/{item_id}`, `custody/{record_id}`,
`revocations/{revocation_id}`, and `departments/{dept}/grants/{tool}`
collections in the contract's Firestore layout.

`SqliteCustodyGraph` and `SqliteTrustCatalog` do not reimplement traversal,
revocation, or the refusal rule: each wraps the pure in-memory class that
`graph.py` and `catalog.py` already prove correct, persists every mutation as
it happens, and rebuilds the wrapped object on construction by replaying the
persisted log through that same class's own methods. The algorithm exists in
exactly one place either way; only the durability is new.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from custody.catalog import Grant, TrustCatalog, Vouch, VouchDecision
from custody.graph import CustodyGraph, Revocation
from custody.origin import CustodyRecord, Origin, ToolTrust, Trust
from custody.service import Quarantined

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quarantine (
    item_id TEXT PRIMARY KEY,
    app_name TEXT NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    text TEXT NOT NULL,
    record TEXT NOT NULL
)
"""


def _item_id(item: Quarantined) -> str:
    """Idempotency key: the same event quarantined twice is the same row."""
    return f"{item.session_id}:{item.record.content_sha256}"


def _dump(record: CustodyRecord) -> str:
    return json.dumps(
        {
            "origin": record.origin.value,
            "trust": record.trust.value,
            "author": record.author,
            "invocation_id": record.invocation_id,
            "content_sha256": record.content_sha256,
            "source_tool": record.source_tool,
            "source_revision": record.source_revision,
            "id": record.id,
            "derived_from": list(record.derived_from),
        }
    )


def _load(payload: str) -> CustodyRecord:
    data = json.loads(payload)
    return CustodyRecord(
        origin=Origin(data["origin"]),
        trust=Trust(data["trust"]),
        author=data["author"],
        invocation_id=data["invocation_id"],
        content_sha256=data["content_sha256"],
        source_tool=data["source_tool"],
        source_revision=data.get("source_revision"),
        id=data["id"],
        derived_from=tuple(data["derived_from"]),
    )


class SqliteQuarantine:
    """Serves the same `hold` / `held` port as `InMemoryQuarantine`.

    One connection for the store's lifetime; SQLite serializes writes itself,
    so nothing here needs its own lock.
    """

    def __init__(self, path: str | Path):
        self._connection = sqlite3.connect(path)
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def hold(self, item: Quarantined) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO quarantine "
            "(item_id, app_name, user_id, session_id, text, record) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                _item_id(item),
                item.app_name,
                item.user_id,
                item.session_id,
                item.text,
                _dump(item.record),
            ),
        )
        self._connection.commit()

    def held(self, *, app_name: str, user_id: str) -> tuple[Quarantined, ...]:
        rows = self._connection.execute(
            "SELECT app_name, user_id, session_id, text, record "
            "FROM quarantine WHERE app_name = ? AND user_id = ? "
            "ORDER BY item_id",
            (app_name, user_id),
        ).fetchall()
        return tuple(
            Quarantined(
                app_name=row[0],
                user_id=row[1],
                session_id=row[2],
                text=row[3],
                record=_load(row[4]),
            )
            for row in rows
        )

    def close(self) -> None:
        self._connection.close()


_RECORD_SCHEMA = """
CREATE TABLE IF NOT EXISTS custody_record (
    id TEXT PRIMARY KEY,
    record TEXT NOT NULL
)
"""

_REVOCATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS revocation (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    revocation_id TEXT NOT NULL UNIQUE,
    tool TEXT NOT NULL
)
"""


class SqliteCustodyGraph:
    """Serves the same port `CustodyGraph` does: `add`, `extend`, `records`,
    `resolve`, `descendants`, `revoke`, `revocations`, `__len__`,
    `__contains__`.

    Every record ever added is kept, even after a revocation removes it from
    the live traversal, because the log has to outlive the state it produced:
    a revocation is only provably correct if the record it removed is still
    on record as having existed. Reload replays the revocation log through
    the wrapped `CustodyGraph`'s own `revoke`, so the removal logic runs once,
    not twice in two languages.
    """

    def __init__(self, path: str | Path):
        self._connection = sqlite3.connect(path)
        self._connection.execute(_RECORD_SCHEMA)
        self._connection.execute(_REVOCATION_SCHEMA)
        self._connection.commit()
        self._graph = CustodyGraph()
        self._reload()

    def _reload(self) -> None:
        for (payload,) in self._connection.execute(
            "SELECT record FROM custody_record"
        ):
            self._graph.add(_load(payload))
        for revocation_id, tool in self._connection.execute(
            "SELECT revocation_id, tool FROM revocation ORDER BY seq"
        ):
            self._graph.revoke(tool=tool, revocation_id=revocation_id)

    def add(self, record: CustodyRecord) -> None:
        self._graph.add(record)
        self._connection.execute(
            "INSERT OR REPLACE INTO custody_record (id, record) VALUES (?, ?)",
            (record.id, _dump(record)),
        )
        self._connection.commit()

    def extend(self, records) -> None:
        for record in records:
            self.add(record)

    def __contains__(self, record_id: str) -> bool:
        return record_id in self._graph

    def __len__(self) -> int:
        return len(self._graph)

    def records(self) -> tuple[CustodyRecord, ...]:
        return self._graph.records()

    def descendants(self, tool: str) -> tuple[str, ...]:
        return self._graph.descendants(tool)

    def resolve(self, content_sha256: str) -> CustodyRecord | None:
        return self._graph.resolve(content_sha256)

    def revoke(self, *, tool: str, revocation_id: str) -> Revocation:
        revocation = self._graph.revoke(tool=tool, revocation_id=revocation_id)
        self._connection.execute(
            "INSERT OR IGNORE INTO revocation (revocation_id, tool) VALUES (?, ?)",
            (revocation.id, revocation.tool),
        )
        self._connection.commit()
        return revocation

    def revocations(self) -> tuple[Revocation, ...]:
        return self._graph.revocations()

    def close(self) -> None:
        self._connection.close()


_VOUCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS vouch (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_department TEXT NOT NULL,
    department TEXT NOT NULL,
    tool TEXT NOT NULL,
    vouched_by TEXT NOT NULL,
    vouched_at TEXT NOT NULL,
    evidence TEXT NOT NULL
)
"""


class SqliteTrustCatalog:
    """Serves the same port `TrustCatalog` does: `request`, `denials`,
    `grants`, `trust_for`.

    Every vouch attempt is logged, allowed or refused alike, because the
    refusal is the audit trail G4 asks for and it has to survive a restart
    the same as the grants that were allowed. Reload replays the log through
    the wrapped `TrustCatalog`'s own `request`, so the refusal rule runs once.
    """

    def __init__(self, path: str | Path):
        self._connection = sqlite3.connect(path)
        self._connection.execute(_VOUCH_SCHEMA)
        self._connection.commit()
        self._catalog = TrustCatalog()
        self._reload()

    def _reload(self) -> None:
        rows = self._connection.execute(
            "SELECT actor_department, department, tool, vouched_by, "
            "vouched_at, evidence FROM vouch ORDER BY seq"
        ).fetchall()
        for actor_department, department, tool, vouched_by, vouched_at, evidence in rows:
            self._catalog.request(
                Vouch(
                    actor_department,
                    Grant(department, tool, vouched_by, vouched_at, evidence),
                )
            )

    def request(self, vouch: Vouch) -> VouchDecision:
        decision = self._catalog.request(vouch)
        self._connection.execute(
            "INSERT INTO vouch (actor_department, department, tool, "
            "vouched_by, vouched_at, evidence) VALUES (?, ?, ?, ?, ?, ?)",
            (
                vouch.actor_department,
                vouch.grant.department,
                vouch.grant.tool,
                vouch.grant.vouched_by,
                vouch.grant.vouched_at,
                vouch.grant.evidence,
            ),
        )
        self._connection.commit()
        return decision

    def denials(self) -> tuple[VouchDecision, ...]:
        return self._catalog.denials()

    def grants(self, department: str) -> tuple[Grant, ...]:
        return self._catalog.grants(department)

    def trust_for(self, department: str) -> ToolTrust:
        return self._catalog.trust_for(department)

    @property
    def decisions(self) -> list[VouchDecision]:
        return self._catalog.decisions

    def close(self) -> None:
        self._connection.close()
