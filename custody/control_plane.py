"""The control plane, as an HTTP service Cloud Run can run.

Deliberately thin and deliberately stdlib. It adds no logic: every endpoint is a
view onto objects the core already builds, so there is nothing here that could
disagree with `make demo` or `make gates`. A control plane that can drift from
the thing it controls is worse than none.

No mock data path exists. If the graph is empty the endpoints say so rather than
serving something illustrative, because the one thing this service must never do
is make the system look further along than it is.

    python -m custody.control_plane        # local, port 8080
    PORT=8080 python -m custody.control_plane

Cloud Run sets $PORT and requires binding 0.0.0.0.
"""

from __future__ import annotations

import json
import os
import signal
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from custody.catalog import Grant, TrustCatalog, Vouch
from custody.graph import CustodyGraph
from custody.origin import CustodyRecord, Origin, Trust, digest, take_custody
from custody.service import InMemoryQuarantine, Quarantined

#: Cloud Run's contract: listen on $PORT, bind every interface.
DEFAULT_PORT = 8080

#: The one G5 seed record's fixed identity, so a replayed first run resolves
#: to the same document rather than minting a second seed.
G5_SEED_RECORD_ID = "g5-elapsed-time-seed"
G5_SEED_TOOL = "custody_g5_seed"


@dataclass
class InMemoryAuditorLog:
    """The offline/local heartbeat log: no persistence, no elapsed-time claim.

    A real elapsed-time claim needs a durable log across process restarts;
    this default exists so the control plane and its tests run without one.
    """

    days: set[str] = field(default_factory=set)

    def heartbeat(self, day: str) -> bool:
        """Record one UTC day's heartbeat; return True the first time ever."""
        first = not self.days
        self.days.add(day)
        return first


@dataclass
class ControlPlane:
    """Fleet state, and the four questions the service answers about it.

    Holds no HTTP concerns, so it is testable without a socket.
    """

    graph: CustodyGraph = field(default_factory=CustodyGraph)
    catalog: TrustCatalog = field(default_factory=TrustCatalog)
    quarantine: InMemoryQuarantine = field(default_factory=InMemoryQuarantine)
    auditor_log: InMemoryAuditorLog = field(default_factory=InMemoryAuditorLog)
    runs: dict[str, dict] = field(default_factory=dict)

    def ingest(self, payload: dict) -> dict:
        """Take custody of one session's events and report what was withheld.

        The trigger G1 asks for: accepts work, returns a run id, and the run is
        retrievable afterwards.
        """
        department = payload.get("department", "unknown")
        events = [_event(e) for e in payload.get("events", [])]
        custody = take_custody(events, self.catalog.trust_for(department))

        untrusted = [
            a for a in custody.admitted if a.record.trust is Trust.UNTRUSTED
        ]
        for admitted in untrusted:
            self.quarantine.hold(
                Quarantined(
                    app_name=payload.get("app_name", "fleet"),
                    user_id=department,
                    session_id=payload.get("session_id", "unknown"),
                    text=admitted.text,
                    record=admitted.record,
                )
            )
        self.graph.extend(
            a.record for a in custody.admitted if a.record.trust is Trust.TRUSTED
        )

        run_id = str(uuid.uuid4())
        run = {
            "run_id": run_id,
            "department": department,
            "seen": len(custody.admitted) + len(custody.refused),
            "admitted": len(custody.admitted) - len(untrusted),
            "quarantined": len(untrusted),
            "refused": len(custody.refused),
            "sources_withheld": sorted(
                {a.record.source_tool or "unnamed" for a in untrusted}
            ),
        }
        self.runs[run_id] = run
        return run

    def vouch(self, payload: dict) -> dict:
        decision = self.catalog.request(
            Vouch(
                actor_department=payload["actor_department"],
                grant=Grant(
                    department=payload["department"],
                    tool=payload["tool"],
                    vouched_by=payload.get("vouched_by", "unknown"),
                    vouched_at=payload.get("vouched_at", ""),
                ),
            )
        )
        return {"allowed": decision.allowed, "reason": decision.reason()}

    def revoke(self, payload: dict) -> dict:
        revocation = self.graph.revoke(
            tool=payload["tool"],
            revocation_id=payload.get("revocation_id") or str(uuid.uuid4()),
        )
        return {
            "revocation_id": revocation.id,
            "tool": revocation.tool,
            "removed": list(revocation.removed),
            "records_remaining": len(self.graph),
        }

    def auditor(self, payload: dict) -> dict:
        """The daily heartbeat Cloud Scheduler calls (G5).

        Idempotent per UTC day: a retried Scheduler invocation on the same
        day is a no-op. On the very first invocation ever, seeds one fixed
        synthetic custody record, so there is a single record whose admission
        can be read back and, later, compared against its eventual
        revocation timestamp to prove genuine elapsed time.
        """
        del payload
        today = datetime.now(UTC).date().isoformat()
        first = self.auditor_log.heartbeat(today)
        seeded_record_id = None
        if first:
            seed = CustodyRecord(
                origin=Origin.TOOL,
                trust=Trust.TRUSTED,
                author="custody-auditor",
                invocation_id="g5-seed",
                content_sha256=digest(
                    "Custody G5 elapsed-time seed record: synthetic, no "
                    "customer data."
                ),
                source_tool=G5_SEED_TOOL,
                id=G5_SEED_RECORD_ID,
            )
            self.graph.add(seed)
            seeded_record_id = seed.id
        return {"day": today, "first_run": first, "seeded_record_id": seeded_record_id}

    def record(self, record_id: str) -> dict | None:
        """Durable view of one record: its admission, and revocation if any."""
        found = self.graph.record(record_id)
        if found is None:
            return None
        record, revocation = found
        return {
            "id": record.id,
            "origin": record.origin.value,
            "trust": record.trust.value,
            "source_tool": record.source_tool,
            "admitted_at": record.admitted_at,
            "revocation_id": revocation.id if revocation else None,
            "revoked_at": revocation.revoked_at if revocation else None,
        }

    def census(self) -> dict:
        return {
            "records": len(self.graph),
            "revocations": len(self.graph.revocations()),
            "quarantined": len(self.quarantine.items),
            "runs": len(self.runs),
            "departments": sorted({r["department"] for r in self.runs.values()}),
        }


def _event(raw: dict) -> Any:
    """Rebuild the structural shape `take_custody` reads.

    Kept local rather than importing an SDK type: the control plane accepts
    plain JSON so it can be driven by curl in a demo, and the core is
    duck-typed precisely so this is possible.
    """
    parts = []
    for part in raw.get("parts", []):
        if "tool" in part:
            parts.append(
                _Part(
                    function_response=_Response(
                        name=part["tool"], response=part.get("response", "")
                    )
                )
            )
        else:
            parts.append(_Part(text=part.get("text", "")))
    return _Event(
        author=raw.get("author", "user"),
        invocation_id=raw.get("invocation_id", "inv-1"),
        content=_Content(parts=parts),
    )


@dataclass
class _Response:
    name: str
    response: Any


@dataclass
class _Part:
    text: str | None = None
    function_response: _Response | None = None


@dataclass
class _Content:
    parts: list


@dataclass
class _Event:
    author: str
    invocation_id: str
    content: _Content


class _Handler(BaseHTTPRequestHandler):
    plane: ControlPlane

    def do_GET(self) -> None:  # noqa: N802  (stdlib callback name)
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/census":
            self._json(200, self.plane.census())
        elif self.path == "/quarantine":
            self._json(
                200,
                {
                    "held": [
                        {
                            "department": item.user_id,
                            "origin": item.record.origin.value,
                            "source_tool": item.record.source_tool,
                            "text": item.text[:200],
                        }
                        for item in self.plane.quarantine.items
                    ]
                },
            )
        elif self.path.startswith("/custody/"):
            record_id = self.path.removeprefix("/custody/")
            found = self.plane.record(record_id) if record_id else None
            if found is None:
                self._json(404, {"error": "no such custody record"})
            else:
                self._json(200, found)
        else:
            self._json(404, {"error": "no such endpoint"})

    def do_POST(self) -> None:  # noqa: N802  (stdlib callback name)
        try:
            payload = json.loads(self._body() or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "body is not JSON"})
            return

        routes = {
            "/sessions": self.plane.ingest,
            "/vouch": self.plane.vouch,
            "/revoke": self.plane.revoke,
            "/auditor": self.plane.auditor,
        }
        handler = routes.get(self.path)
        if handler is None:
            self._json(404, {"error": "no such endpoint"})
            return
        try:
            self._json(200, handler(payload))
        except KeyError as missing:
            self._json(400, {"error": f"missing field: {missing}"})

    def _body(self) -> str:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length).decode() if length else ""

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        """Silence per-request logging; Cloud Run captures stdout already."""


def _default_plane() -> ControlPlane:
    """Firestore-backed when deployed with a project configured; pure
    in-memory otherwise, so local runs and tests need no cloud account.
    """
    project = os.environ.get("CUSTODY_FIRESTORE_PROJECT")
    if not project:
        return ControlPlane()
    from google.cloud import firestore

    from custody.firestore_store import FirestoreAuditorLog, FirestoreCustodyGraph

    client = firestore.Client(project=project)
    return ControlPlane(
        graph=FirestoreCustodyGraph(client),
        auditor_log=FirestoreAuditorLog(client),
    )


def serve(port: int | None = None, plane: ControlPlane | None = None) -> HTTPServer:
    _Handler.plane = plane or _default_plane()
    resolved = port if port is not None else int(os.environ.get("PORT", DEFAULT_PORT))
    return HTTPServer(("0.0.0.0", resolved), _Handler)  # noqa: S104


def main() -> int:
    httpd = serve()
    host, port = httpd.server_address
    print(f"custody control plane on http://{host}:{port}", flush=True)

    # Cloud Run sends SIGTERM on every scale-down and waits ~10s before
    # SIGKILL. `serve_forever` only unwinds on KeyboardInterrupt, which is
    # SIGINT, so without this the process ignores the signal and is killed on
    # every single shutdown. Measured: 10,242ms to stop before this existed,
    # against a few milliseconds after.
    def _stop(_signum, _frame) -> None:
        print("SIGTERM received, shutting down", flush=True)
        # shutdown() blocks until serve_forever exits and must not be called
        # from the thread running it.
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _stop)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
