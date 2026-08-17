"""Decision storage abstraction — BUILD_SCOPE.md §11.

`DecisionStore` is the interface the rest of the product depends on. Stage
2's only implementation is local (`JSONFileDecisionStore`) — no GCP
dependency yet, per BUILD_SCOPE.md's staging (Firestore is a later-stage
concern). A Firestore-backed store can satisfy this same interface without
callers changing, which is the point of having it: pull the storage-backend
decision behind a narrow interface now, swap the implementation later.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from models import Decision, DecisionStatus, Evidence, RelationshipType


class DecisionStore(Protocol):
    def save(self, decision: Decision) -> None: ...
    def save_many(self, decisions: list[Decision]) -> None: ...
    def get(self, decision_id: str) -> Decision | None: ...
    def list_all(self) -> list[Decision]: ...


def _decision_to_dict(d: Decision) -> dict:
    raw = asdict(d)
    raw["current_status"] = d.current_status.value
    raw["evidence"] = [
        {"type": e.type, "url": e.url, "quote": e.quote} for e in d.evidence
    ]
    raw["related_decisions"] = [
        [target_id, rel.value] for target_id, rel in d.related_decisions
    ]
    return raw


def _dict_to_decision(raw: dict) -> Decision:
    return Decision(
        id=raw["id"],
        subject=raw["subject"],
        current_status=DecisionStatus(raw["current_status"]),
        context=raw.get("context"),
        chosen_approach=raw.get("chosen_approach"),
        rejected_alternatives=raw.get("rejected_alternatives", []),
        rationale=raw.get("rationale"),
        constraints=raw.get("constraints", []),
        introduced_at=raw.get("introduced_at"),
        superseded_at=raw.get("superseded_at"),
        evidence=[Evidence(**e) for e in raw.get("evidence", [])],
        related_components=raw.get("related_components", []),
        related_decisions=[
            (target_id, RelationshipType(rel)) for target_id, rel in raw.get("related_decisions", [])
        ],
    )


class JSONFileDecisionStore:
    """Local, dependency-free `DecisionStore`. One JSON object per line,
    keyed by decision id in an in-memory index; the file is the durability
    layer, the index is just for fast lookup within a process."""

    def __init__(self, path: Path):
        self.path = path
        self._by_id: dict[str, Decision] = {}
        if path.exists():
            for line in path.open():
                line = line.strip()
                if line:
                    d = _dict_to_decision(json.loads(line))
                    self._by_id[d.id] = d

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as f:
            for d in self._by_id.values():
                f.write(json.dumps(_decision_to_dict(d)) + "\n")

    def save(self, decision: Decision) -> None:
        self._by_id[decision.id] = decision
        self._flush()

    def save_many(self, decisions: list[Decision]) -> None:
        for d in decisions:
            self._by_id[d.id] = d
        self._flush()

    def get(self, decision_id: str) -> Decision | None:
        return self._by_id.get(decision_id)

    def list_all(self) -> list[Decision]:
        return list(self._by_id.values())


def _decision_to_firestore_dict(d: Decision) -> dict:
    """Firestore rejects nested arrays (`related_decisions` is a list of
    `[target_id, type]` pairs in the JSON encoding), so re-shape that one
    field into a list of maps. Everything else matches `_decision_to_dict`."""
    raw = _decision_to_dict(d)
    raw["related_decisions"] = [
        {"target_id": target_id, "type": rel} for target_id, rel in raw["related_decisions"]
    ]
    return raw


def _firestore_dict_to_decision(raw: dict) -> Decision:
    raw = dict(raw)
    raw["related_decisions"] = [
        [entry["target_id"], entry["type"]] for entry in raw.get("related_decisions", [])
    ]
    return _dict_to_decision(raw)


def _firestore_doc_id(decision_id: str) -> str:
    """Decision ids carry `/` (e.g. `rust-lang/rust-pr-149375`), which
    Firestore reads as a path separator rather than literal document-id
    text. Quote it into a single safe path segment; the real id still
    round-trips through the stored payload's own `id` field."""
    from urllib.parse import quote

    return quote(decision_id, safe="")


class FirestoreDecisionStore:
    """Cloud-backed `DecisionStore`, one document per decision, keyed by
    decision id. Exists so Cloud Run's ephemeral filesystem doesn't break
    the persistence guarantee `JSONFileDecisionStore` provides locally."""

    def __init__(self, collection: str, project: str | None = None):
        from google.cloud import firestore

        self._client = firestore.Client(project=project)
        self._collection = self._client.collection(collection)

    def save(self, decision: Decision) -> None:
        self._collection.document(_firestore_doc_id(decision.id)).set(
            _decision_to_firestore_dict(decision)
        )

    def save_many(self, decisions: list[Decision]) -> None:
        batch = self._client.batch()
        for d in decisions:
            batch.set(
                self._collection.document(_firestore_doc_id(d.id)),
                _decision_to_firestore_dict(d),
            )
        batch.commit()

    def get(self, decision_id: str) -> Decision | None:
        doc = self._collection.document(_firestore_doc_id(decision_id)).get()
        return _firestore_dict_to_decision(doc.to_dict()) if doc.exists else None

    def list_all(self) -> list[Decision]:
        return [_firestore_dict_to_decision(doc.to_dict()) for doc in self._collection.stream()]
