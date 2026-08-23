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

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterable, Mapping

from custody.authority import (
    AdmissionEnvelope,
    AdmissionState,
    AuthorityConflict,
    AuthorityDataError,
    AuthorityDecision,
    AuthorityDependency,
    AuthorityReceipt,
    AuthorityStateReader,
    AuthorityUnavailable,
    LinearizedAuthorityDecision,
    PolicyKey,
    PolicySnapshot,
    RootRevocation,
    canonical_json_bytes,
)
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
            "admitted_at": record.admitted_at,
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
        admitted_at=data.get("admitted_at"),
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


_AUTHORITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS authority_issuer_key (
    issuer_id TEXT NOT NULL,
    issuer_key_id TEXT NOT NULL,
    public_key BLOB NOT NULL,
    PRIMARY KEY (issuer_id, issuer_key_id)
);
CREATE TABLE IF NOT EXISTS authority_policy (
    policy_key_digest TEXT PRIMARY KEY,
    snapshot TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authority_envelope (
    record_id TEXT PRIMARY KEY,
    envelope TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authority_dependency (
    record_id TEXT NOT NULL,
    dependency_digest TEXT NOT NULL,
    root_key_digest TEXT,
    dependency TEXT NOT NULL,
    PRIMARY KEY (record_id, dependency_digest),
    FOREIGN KEY (record_id) REFERENCES authority_envelope(record_id)
);
CREATE INDEX IF NOT EXISTS authority_dependency_root
    ON authority_dependency(root_key_digest, record_id);
CREATE TABLE IF NOT EXISTS authority_receipt_root (
    receipt_binding_digest TEXT PRIMARY KEY,
    root_record_id TEXT NOT NULL UNIQUE,
    FOREIGN KEY (root_record_id) REFERENCES authority_envelope(record_id)
);
CREATE TABLE IF NOT EXISTS authority_root_revocation (
    revocation_id TEXT PRIMARY KEY,
    revocation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authority_revoked_root (
    root_key_digest TEXT PRIMARY KEY,
    revocation_id TEXT NOT NULL,
    FOREIGN KEY (revocation_id)
        REFERENCES authority_root_revocation(revocation_id)
);
CREATE TABLE IF NOT EXISTS authority_action_decision (
    request_id TEXT PRIMARY KEY,
    request_digest TEXT NOT NULL,
    decision TEXT NOT NULL
);
"""


class SqliteAuthorityStore:
    """Durable B7 store with create-or-identical transactional semantics."""

    def __init__(self, path: str | Path, *, timeout: float = 5.0) -> None:
        self._connection = sqlite3.connect(
            path,
            timeout=timeout,
            isolation_level=None,
            check_same_thread=False,
        )
        self._lock = threading.RLock()
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.executescript(_AUTHORITY_SCHEMA)
        except sqlite3.Error as error:
            self._connection.close()
            raise AuthorityUnavailable("could not initialize B7 SQLite state") from error

    def put_issuer_key(
        self, *, issuer_id: str, issuer_key_id: str, public_key: bytes
    ) -> None:
        if not isinstance(issuer_id, str) or not issuer_id:
            raise AuthorityDataError("issuer_id must be a non-empty string")
        if not isinstance(issuer_key_id, str) or not issuer_key_id:
            raise AuthorityDataError("issuer_key_id must be a non-empty string")
        if not isinstance(public_key, bytes):
            raise AuthorityDataError("issuer public key must be bytes")
        with self._transaction():
            row = self._connection.execute(
                "SELECT public_key FROM authority_issuer_key "
                "WHERE issuer_id = ? AND issuer_key_id = ?",
                (issuer_id, issuer_key_id),
            ).fetchone()
            if row is not None:
                if bytes(row[0]) != public_key:
                    raise AuthorityConflict(
                        "issuer key identity already has other bytes"
                    )
                return
            self._connection.execute(
                "INSERT INTO authority_issuer_key "
                "(issuer_id, issuer_key_id, public_key) VALUES (?, ?, ?)",
                (issuer_id, issuer_key_id, public_key),
            )

    def public_key_for(self, *, issuer_id: str, issuer_key_id: str) -> bytes | None:
        row = self._read_one(
            "SELECT public_key FROM authority_issuer_key "
            "WHERE issuer_id = ? AND issuer_key_id = ?",
            (issuer_id, issuer_key_id),
        )
        return None if row is None else bytes(row[0])

    def put_policy(
        self,
        snapshot: PolicySnapshot,
        *,
        expected_generation: int | None = None,
    ) -> None:
        if not isinstance(snapshot, PolicySnapshot):
            raise AuthorityDataError("policy write requires a PolicySnapshot")
        payload = canonical_json_bytes(snapshot.as_dict()).decode("utf-8")
        with self._transaction():
            current = self._policy_unlocked(snapshot.policy_key)
            if current == snapshot:
                return
            if current is None:
                if expected_generation is not None:
                    raise AuthorityConflict("policy does not have expected generation")
                self._connection.execute(
                    "INSERT INTO authority_policy "
                    "(policy_key_digest, snapshot) VALUES (?, ?)",
                    (snapshot.policy_key.digest, payload),
                )
                return
            if (
                current.policy_key != snapshot.policy_key
                or expected_generation is None
                or current.generation != expected_generation
                or snapshot.generation != expected_generation + 1
            ):
                raise AuthorityConflict("policy generation compare-and-set failed")
            self._connection.execute(
                "UPDATE authority_policy SET snapshot = ? "
                "WHERE policy_key_digest = ?",
                (payload, snapshot.policy_key.digest),
            )

    def policy(self, key: PolicyKey) -> PolicySnapshot | None:
        if not isinstance(key, PolicyKey):
            raise AuthorityDataError("policy lookup requires a PolicyKey")
        with self._lock:
            try:
                return self._policy_unlocked(key)
            except sqlite3.Error as error:
                raise AuthorityUnavailable("B7 policy read failed") from error

    def commit_admission(
        self,
        envelope: AdmissionEnvelope,
        dependencies: tuple[AuthorityDependency, ...],
        *,
        expected_policies: Mapping[PolicyKey, int],
        receipt_binding_digest: str | None = None,
    ) -> AdmissionEnvelope:
        self._validate_admission(envelope, dependencies)
        if receipt_binding_digest is not None:
            _require_sha256(receipt_binding_digest, "receipt_binding_digest")
        canonical_dependencies = tuple(
            sorted(dependencies, key=lambda item: item.canonical_bytes())
        )
        with self._transaction():
            existing = self._envelope_unlocked(envelope.record_id)
            if existing is not None:
                if (
                    existing != envelope
                    or self._dependencies_unlocked(envelope.record_id)
                    != canonical_dependencies
                    or self._receipt_binding_unlocked(envelope.record_id)
                    != receipt_binding_digest
                ):
                    raise AuthorityConflict(
                        "record ID already has other authority bytes"
                    )
                return existing
            for key, generation in expected_policies.items():
                current = self._policy_unlocked(key)
                if current is None or current.generation != generation:
                    raise AuthorityConflict("policy changed during admission")
            for parent_id in envelope.direct_parent_ids:
                parent = self._envelope_unlocked(parent_id)
                if parent is None or parent.admission_state is not AdmissionState.COMMITTED:
                    raise AuthorityConflict("required parent is missing or incomplete")
            if receipt_binding_digest is not None:
                row = self._connection.execute(
                    "SELECT root_record_id FROM authority_receipt_root "
                    "WHERE receipt_binding_digest = ?",
                    (receipt_binding_digest,),
                ).fetchone()
                if row is not None and row[0] != envelope.record_id:
                    raise AuthorityConflict("receipt is already bound to another root")
            self._connection.execute(
                "INSERT INTO authority_envelope (record_id, envelope) VALUES (?, ?)",
                (envelope.record_id, envelope.canonical_bytes().decode("utf-8")),
            )
            for dependency in canonical_dependencies:
                self._connection.execute(
                    "INSERT INTO authority_dependency "
                    "(record_id, dependency_digest, root_key_digest, dependency) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        envelope.record_id,
                        hashlib.sha256(dependency.canonical_bytes()).hexdigest(),
                        dependency.root_key_digest,
                        dependency.canonical_bytes().decode("utf-8"),
                    ),
                )
            if receipt_binding_digest is not None:
                self._connection.execute(
                    "INSERT INTO authority_receipt_root "
                    "(receipt_binding_digest, root_record_id) VALUES (?, ?)",
                    (receipt_binding_digest, envelope.record_id),
                )
            return envelope

    def envelope(self, record_id: str) -> AdmissionEnvelope | None:
        with self._lock:
            try:
                return self._envelope_unlocked(record_id)
            except (sqlite3.Error, AuthorityDataError) as error:
                raise AuthorityUnavailable("B7 envelope read failed") from error

    def dependencies(self, record_id: str) -> tuple[AuthorityDependency, ...]:
        with self._lock:
            try:
                return self._dependencies_unlocked(record_id)
            except (sqlite3.Error, AuthorityDataError) as error:
                raise AuthorityUnavailable("B7 dependency read failed") from error

    def records(self) -> tuple[AdmissionEnvelope, ...]:
        with self._lock:
            try:
                rows = self._connection.execute(
                    "SELECT envelope FROM authority_envelope ORDER BY record_id"
                ).fetchall()
                return tuple(_load_envelope(row[0]) for row in rows)
            except (sqlite3.Error, AuthorityDataError) as error:
                raise AuthorityUnavailable("B7 record scan failed") from error

    def root_record_id_for_receipt(
        self, receipt: AuthorityReceipt
    ) -> str | None:
        row = self._read_one(
            "SELECT root_record_id FROM authority_receipt_root "
            "WHERE receipt_binding_digest = ?",
            (receipt.binding_digest,),
        )
        return None if row is None else str(row[0])

    def is_root_revoked(self, root_key_digest: str) -> bool:
        _require_sha256(root_key_digest, "root_key_digest")
        return self._read_one(
            "SELECT 1 FROM authority_revoked_root WHERE root_key_digest = ?",
            (root_key_digest,),
        ) is not None

    def linearize_action(
        self,
        *,
        request_id: str,
        request_digest: str,
        decide: Callable[[AuthorityStateReader], AuthorityDecision],
    ) -> LinearizedAuthorityDecision:
        _require_sha256(request_digest, "request_digest")
        with self._transaction():
            row = self._connection.execute(
                "SELECT request_digest, decision FROM authority_action_decision "
                "WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is not None:
                if row[0] != request_digest:
                    raise AuthorityConflict(
                        "action request ID already has different request bytes"
                    )
                return LinearizedAuthorityDecision(
                    _load_decision(row[1]), False
                )
            decision = decide(self)
            if (
                not isinstance(decision, AuthorityDecision)
                or decision.request_id != request_id
                or decision.request_digest != request_digest
            ):
                raise AuthorityDataError(
                    "action decision does not match its linearization request"
                )
            self._connection.execute(
                "INSERT INTO authority_action_decision "
                "(request_id, request_digest, decision) VALUES (?, ?, ?)",
                (
                    request_id,
                    request_digest,
                    decision.canonical_bytes().decode("utf-8"),
                ),
            )
            return LinearizedAuthorityDecision(decision, True)

    def action_decisions(self) -> tuple[AuthorityDecision, ...]:
        with self._lock:
            try:
                rows = self._connection.execute(
                    "SELECT decision FROM authority_action_decision "
                    "ORDER BY request_id"
                ).fetchall()
                return tuple(_load_decision(row[0]) for row in rows)
            except (sqlite3.Error, AuthorityDataError) as error:
                raise AuthorityUnavailable("B7 action decision scan failed") from error

    def commit_root_revocation(
        self, revocation: RootRevocation
    ) -> RootRevocation:
        if not isinstance(revocation, RootRevocation):
            raise AuthorityDataError("root revocation write requires RootRevocation")
        with self._transaction():
            row = self._connection.execute(
                "SELECT revocation FROM authority_root_revocation "
                "WHERE revocation_id = ?",
                (revocation.revocation_id,),
            ).fetchone()
            if row is not None:
                existing = _load_root_revocation(row[0])
                if existing.selector_bytes() != revocation.selector_bytes():
                    raise AuthorityConflict(
                        "revocation ID already has other receipt-root selectors"
                    )
                return existing
            self._connection.execute(
                "INSERT INTO authority_root_revocation "
                "(revocation_id, revocation) VALUES (?, ?)",
                (
                    revocation.revocation_id,
                    canonical_json_bytes(revocation.as_dict()).decode("utf-8"),
                ),
            )
            for root_key in revocation.root_keys:
                self._connection.execute(
                    "INSERT OR IGNORE INTO authority_revoked_root "
                    "(root_key_digest, revocation_id) VALUES (?, ?)",
                    (root_key.digest, revocation.revocation_id),
                )
            return revocation

    def affected_record_ids(
        self, root_key_digests: Iterable[str]
    ) -> tuple[str, ...]:
        digests = tuple(sorted(set(root_key_digests)))
        for digest in digests:
            _require_sha256(digest, "root_key_digest")
        if not digests:
            return ()
        placeholders = ",".join("?" for _ in digests)
        with self._lock:
            try:
                rows = self._connection.execute(
                    "SELECT DISTINCT record_id FROM authority_dependency "
                    f"WHERE root_key_digest IN ({placeholders}) ORDER BY record_id",
                    digests,
                ).fetchall()
                return tuple(str(row[0]) for row in rows)
            except sqlite3.Error as error:
                raise AuthorityUnavailable("B7 reverse dependency read failed") from error

    def root_revocations(self) -> tuple[RootRevocation, ...]:
        with self._lock:
            try:
                rows = self._connection.execute(
                    "SELECT revocation FROM authority_root_revocation "
                    "ORDER BY revocation_id"
                ).fetchall()
                return tuple(_load_root_revocation(row[0]) for row in rows)
            except (sqlite3.Error, AuthorityDataError) as error:
                raise AuthorityUnavailable("B7 revocation scan failed") from error

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @contextmanager
    def _transaction(self):
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                yield
                self._connection.execute("COMMIT")
            except (AuthorityConflict, AuthorityDataError):
                self._connection.execute("ROLLBACK")
                raise
            except sqlite3.Error as error:
                try:
                    self._connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise AuthorityUnavailable("B7 SQLite transaction failed") from error
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise

    def _read_one(self, statement: str, parameters: tuple):
        with self._lock:
            try:
                return self._connection.execute(statement, parameters).fetchone()
            except sqlite3.Error as error:
                raise AuthorityUnavailable("B7 SQLite read failed") from error

    def _policy_unlocked(self, key: PolicyKey) -> PolicySnapshot | None:
        row = self._connection.execute(
            "SELECT snapshot FROM authority_policy WHERE policy_key_digest = ?",
            (key.digest,),
        ).fetchone()
        if row is None:
            return None
        snapshot = _load_policy(row[0])
        if snapshot.policy_key != key:
            raise AuthorityDataError("stored PolicyKey digest does not match fields")
        return snapshot

    def _envelope_unlocked(self, record_id: str) -> AdmissionEnvelope | None:
        row = self._connection.execute(
            "SELECT envelope FROM authority_envelope WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            return None
        envelope = _load_envelope(row[0])
        if envelope.record_id != record_id:
            raise AuthorityDataError("stored record ID does not match envelope")
        return envelope

    def _dependencies_unlocked(
        self, record_id: str
    ) -> tuple[AuthorityDependency, ...]:
        rows = self._connection.execute(
            "SELECT dependency FROM authority_dependency "
            "WHERE record_id = ? ORDER BY dependency",
            (record_id,),
        ).fetchall()
        dependencies = tuple(_load_dependency(row[0]) for row in rows)
        if any(dependency.record_id != record_id for dependency in dependencies):
            raise AuthorityDataError("stored dependency has wrong record ID")
        return tuple(sorted(dependencies, key=lambda item: item.canonical_bytes()))

    def _receipt_binding_unlocked(self, record_id: str) -> str | None:
        row = self._connection.execute(
            "SELECT receipt_binding_digest FROM authority_receipt_root "
            "WHERE root_record_id = ?",
            (record_id,),
        ).fetchone()
        return None if row is None else str(row[0])

    @staticmethod
    def _validate_admission(
        envelope: AdmissionEnvelope,
        dependencies: tuple[AuthorityDependency, ...],
    ) -> None:
        if not isinstance(envelope, AdmissionEnvelope):
            raise AuthorityDataError("admission write requires an AdmissionEnvelope")
        if not isinstance(dependencies, tuple) or any(
            not isinstance(item, AuthorityDependency) for item in dependencies
        ):
            raise AuthorityDataError("admission dependencies must be a tuple")
        if any(item.record_id != envelope.record_id for item in dependencies):
            raise AuthorityDataError("dependency belongs to a different record")


def _load_policy(payload: str) -> PolicySnapshot:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise AuthorityDataError("stored policy is not an object")
    return PolicySnapshot.from_mapping(value)


def _load_envelope(payload: str) -> AdmissionEnvelope:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise AuthorityDataError("stored envelope is not an object")
    return AdmissionEnvelope.from_mapping(value)


def _load_dependency(payload: str) -> AuthorityDependency:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise AuthorityDataError("stored dependency is not an object")
    return AuthorityDependency.from_mapping(value)


def _load_decision(payload: str) -> AuthorityDecision:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise AuthorityDataError("stored decision is not an object")
    return AuthorityDecision.from_mapping(value)


def _load_root_revocation(payload: str) -> RootRevocation:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise AuthorityDataError("stored root revocation is not an object")
    return RootRevocation.from_mapping(value)


def _require_sha256(value: str, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AuthorityDataError(f"{field} must be lowercase SHA-256 hex")
