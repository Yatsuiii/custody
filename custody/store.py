"""Durable quarantine, behind the same port `InMemoryQuarantine` implements.

Quarantine has to survive a process restart: a real deployment quarantines
content, gets redeployed, and the Custody Reviewer still needs to find it.
SQLite is the offline stand-in for the `quarantine/{item_id}` collection in
the contract's Firestore layout, and the row key gives it the one primitive
that layout promises: a write that is a no-op the second time, so a session
replayed after a crash does not double-quarantine the same item.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from custody.origin import CustodyRecord, Origin, Trust
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
