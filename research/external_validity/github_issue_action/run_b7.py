"""Execute the scorer-blind B7 treatment on the frozen GitHub deliveries.

The runner has two deliberately separate state boundaries:

* GitHub delivery/action state lives in a B7-only SQLite file; and
* the production B7 authority state is stored in the same file through
  :class:`custody.store.SqliteAuthorityStore`.

Only ``RUNNER_SCOPE.json`` and the GUID order are read before treatment.  The
case manifest is scorer-only and is never imported here.  GitHub's signed
webhook is the external observation; the adapter issues a short-lived,
repository/actor/object-bound B7 receipt only after the receiver and REST
readbacks agree.  The issuer key is generated in memory and its private bytes
never enter an artifact or log.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding

from custody.action import AuthorityAction, AuthorityGateway, AuthorityExecution
from custody.authority import (
    AdmissionGate,
    AdmissionResult,
    AuthorityOutput,
    AuthorityReceipt,
    Capability,
    PolicyKey,
    PolicySnapshot,
    OperationRole,
    ReceiptRootKey,
    RevocationController,
    SourceAuthorityEvent,
    TransformRef,
    canonical_json_bytes,
)
from custody.store import SqliteAuthorityStore


ROOT = Path(__file__).parent
SCOPE_PATH = ROOT / "RUNNER_SCOPE.json"
ORDER_PATH = ROOT / "DELIVERY_ORDER.json"
RELAY_PATH = ROOT / "RELAY_WORKFLOW.json"
RESULT_PATH = ROOT / "results" / "B7_RESULT.json"
SECRET_DIR = Path("/home/Yatsuiii/.config/custody-execution-secrets")
INGRESS_KEY_PATH = SECRET_DIR / "ingress.pem"
ACTION_KEY_PATH = SECRET_DIR / "action.pem"
WEBHOOK_SECRET_PATH = SECRET_DIR / "webhook.secret"
RECEIVER_TOKEN_PATH = SECRET_DIR / "receiver-read.token"
DEFAULT_LEDGER = Path(
    "/home/Yatsuiii/.local/state/custody-external-validity/b7.sqlite3"
)
USER_AGENT = "custody-external-validity-b7/1"
GUID_RE = re.compile(r"^[0-9a-f-]{20,80}$", re.IGNORECASE)
BODY_SCHEMA = "github-issue-comment-raw-delivery-v1"
ACTION_SCOPE = "github.issue.close"
SOURCE_REVISION = "github-rest-2026-03-10"


class RunFailure(RuntimeError):
    """A bounded failure safe to place in a redacted result artifact."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def parse_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise RunFailure("timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RunFailure("timestamp_invalid") from error
    if parsed.tzinfo is None:
        raise RunFailure("timestamp_timezone_missing")
    return parsed.astimezone(timezone.utc)


def file_digest(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as error:
        raise RunFailure(f"artifact_unreadable_{path.name}") from error


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunFailure(f"artifact_unreadable_{path.name}") from error
    if not isinstance(value, dict):
        raise RunFailure(f"artifact_not_object_{path.name}")
    return value


def read_secret(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RunFailure(f"secret_unavailable_{path.name}") from error
    if not value:
        raise RunFailure(f"secret_empty_{path.name}")
    return value


def private_key(path: Path) -> Any:
    try:
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError) as error:
        raise RunFailure(f"private_key_unavailable_{path.name}") from error


def app_jwt(app_id: int, key: Any) -> str:
    now = int(time.time())
    header = b64url(
        json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    claims = b64url(
        json.dumps(
            {"iat": now - 30, "exp": now + 540, "iss": app_id},
            separators=(",", ":"),
        ).encode()
    )
    signing = f"{header}.{claims}".encode("ascii")
    signature = key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    return signing.decode("ascii") + "." + b64url(signature)


class GitHubClient:
    """Small bounded REST client; response bodies never enter exceptions."""

    def __init__(self, scope: Mapping[str, Any]) -> None:
        api = scope["api"]
        limits = scope["limits"]
        self.host = str(api["host"])
        self.version = str(api["version"])
        self.max_reads = int(limits["max_github_reads"])
        self.max_patches = int(limits["max_issue_patch_requests"])
        self.reads = 0
        self.patches = 0

    def request(
        self,
        method: str,
        path: str,
        token: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> Any:
        method = method.upper()
        if method == "GET":
            self.reads += 1
            if self.reads > self.max_reads:
                raise RunFailure("github_read_ceiling")
        if method == "PATCH":
            self.patches += 1
            if self.patches > self.max_patches:
                raise RunFailure("issue_patch_ceiling")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": self.version,
            "User-Agent": USER_AGENT,
        }
        try:
            response = requests.request(
                method,
                self.host + path,
                headers=headers,
                json=body,
                timeout=20,
            )
        except requests.RequestException as error:
            raise RunFailure(f"github_transport_{method.lower()}") from error
        if not 200 <= response.status_code < 300:
            raise RunFailure(f"github_api_{method.lower()}_{response.status_code}")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise RunFailure(f"github_json_invalid_{method.lower()}") from error

    def configure_target(self, scope: Mapping[str, Any]) -> None:
        full_name = str(scope["repository"]["full_name"])
        owner, name = full_name.split("/", 1)
        self.repo_owner = owner
        self.repo_name = name
        self.issue_path = str(scope["api"]["issue_patch_path"])

    def app(self, token: str) -> dict[str, Any]:
        value = self.request("GET", "/app", token)
        if not isinstance(value, dict):
            raise RunFailure("app_readback_invalid")
        return value

    def mint_installation(self, app_jwt_value: str, installation_id: int) -> str:
        value = self.request(
            "POST", f"/app/installations/{installation_id}/access_tokens", app_jwt_value
        )
        token = value.get("token") if isinstance(value, dict) else None
        if not isinstance(token, str) or not token:
            raise RunFailure("installation_token_missing")
        return token

    def installation_repositories(self, token: str) -> list[dict[str, Any]]:
        value = self.request("GET", "/installation/repositories?per_page=100", token)
        repositories = value.get("repositories") if isinstance(value, dict) else None
        if not isinstance(repositories, list):
            raise RunFailure("installation_repositories_invalid")
        return [row for row in repositories if isinstance(row, dict)]

    def hook_deliveries(self, token: str) -> list[dict[str, Any]]:
        value = self.request("GET", "/app/hook/deliveries?per_page=100", token)
        if not isinstance(value, list):
            raise RunFailure("hook_delivery_list_invalid")
        return [row for row in value if isinstance(row, dict)]

    def hook_delivery(self, token: str, delivery_id: int) -> dict[str, Any]:
        value = self.request("GET", f"/app/hook/deliveries/{delivery_id}", token)
        if not isinstance(value, dict):
            raise RunFailure("hook_delivery_invalid")
        return value

    def comment(self, token: str, comment_id: int) -> dict[str, Any]:
        value = self.request(
            "GET",
            f"/repos/{self.repo_owner}/{self.repo_name}/issues/comments/{comment_id}",
            token,
        )
        if not isinstance(value, dict):
            raise RunFailure("comment_readback_invalid")
        return value

    def issue(self, token: str) -> dict[str, Any]:
        value = self.request("GET", self.issue_path, token)
        if not isinstance(value, dict):
            raise RunFailure("issue_readback_invalid")
        return value

    def patch_issue(self, token: str, body: dict[str, Any]) -> dict[str, Any]:
        value = self.request("PATCH", self.issue_path, token, body=body)
        if not isinstance(value, dict):
            raise RunFailure("issue_patch_readback_invalid")
        return value


class ReceiverClient:
    """Reads the receiver's raw bytes and re-verifies its HMAC."""

    def __init__(self, scope: Mapping[str, Any]) -> None:
        self.base = str(scope["receiver"]["url"])
        self.read_token = read_secret(RECEIVER_TOKEN_PATH)
        self.webhook_secret = read_secret(WEBHOOK_SECRET_PATH).encode("utf-8")

    def get(self, guid: str) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
        try:
            response = requests.get(
                self.base + "/api/delivery",
                params={"guid": guid, "content": "1"},
                headers={"x-receiver-read-token": self.read_token},
                timeout=20,
            )
        except requests.RequestException as error:
            raise RunFailure("receiver_transport") from error
        if response.status_code != 200:
            raise RunFailure(f"receiver_delivery_{response.status_code}")
        try:
            envelope = response.json()
        except ValueError as error:
            raise RunFailure("receiver_envelope_json_invalid") from error
        if not isinstance(envelope, dict) or envelope.get("schema") != BODY_SCHEMA:
            raise RunFailure("receiver_schema_mismatch")
        if envelope.get("delivery_guid") != guid:
            raise RunFailure("receiver_guid_mismatch")
        try:
            raw = base64.b64decode(envelope["body_b64"], validate=True)
        except (KeyError, TypeError, ValueError, binascii.Error) as error:
            raise RunFailure("receiver_body_invalid") from error
        if envelope.get("body_sha256") != sha256_bytes(raw):
            raise RunFailure("receiver_body_digest_mismatch")
        headers = envelope.get("headers")
        if not isinstance(headers, dict):
            raise RunFailure("receiver_headers_missing")
        normalized = {str(key).lower(): value for key, value in headers.items()}
        if normalized.get("x-github-delivery") != guid:
            raise RunFailure("receiver_header_guid_mismatch")
        if normalized.get("x-github-event") != "issue_comment":
            raise RunFailure("receiver_header_event_mismatch")
        supplied = normalized.get("x-hub-signature-256")
        if not isinstance(supplied, str) or not supplied.startswith("sha256="):
            raise RunFailure("receiver_signature_missing")
        expected = "sha256=" + hmac.new(
            self.webhook_secret, raw, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(supplied, expected):
            raise RunFailure("receiver_signature_invalid")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RunFailure("receiver_payload_invalid") from error
        if not isinstance(payload, dict):
            raise RunFailure("receiver_payload_not_object")
        return envelope, raw, payload


@dataclass(frozen=True)
class Command:
    command: str
    target_issue_id: int
    generation: int
    source_role: str
    parents: tuple[int, ...]
    relay_workflow_id: str
    control: str


@dataclass(frozen=True)
class Observation:
    guid: str
    delivery_id: int
    redelivery: bool
    comment_id: int
    actor_id: int
    created_at: datetime
    created_at_text: str
    comment_body: str
    comment_body_sha256: str
    delivery_body_sha256: str
    payload: dict[str, Any]


def parse_command(body: str, scope: Mapping[str, Any]) -> Command:
    grammar = scope["grammar"]
    lines = body.split("\n")
    if not lines or lines[0] != grammar["header"]:
        raise RunFailure("grammar_header")
    if len(lines) != 1 + len(grammar["field_order"]):
        raise RunFailure("grammar_line_count")
    values: dict[str, str] = {}
    for line, key in zip(lines[1:], grammar["field_order"], strict=True):
        prefix = key + "="
        if not line.startswith(prefix) or key in values:
            raise RunFailure("grammar_field_order")
        value = line[len(prefix) :]
        if not value or "\n" in value or "\r" in value:
            raise RunFailure("grammar_field_value")
        values[key] = value
    if values["command"] not in {"close", scope["generation_control"]["discovery_command"]}:
        raise RunFailure("grammar_command")
    try:
        target_id = int(values["target_issue_id"])
        generation = int(values["generation"])
    except ValueError as error:
        raise RunFailure("grammar_numeric_field") from error
    controls = scope["generation_control"]
    if generation not in {
        int(controls["initial_generation"]),
        int(controls["remediated_generation"]),
    }:
        raise RunFailure("grammar_generation")
    if target_id != int(scope["target_issue"]["id"]):
        raise RunFailure("grammar_target_mismatch")
    role = values["source_role"]
    if role not in {"root", "relay", "activation", "incident_discovery"}:
        raise RunFailure("grammar_source_role")
    raw_parents = values["parent_comment_ids"]
    if raw_parents == "none":
        parents: tuple[int, ...] = ()
    else:
        pieces = raw_parents.split(str(grammar["parent_separator"]))
        if not pieces or any(not item.isdigit() or int(item) <= 0 for item in pieces):
            raise RunFailure("grammar_parent_ids")
        parents = tuple(int(item) for item in pieces)
        if len(parents) != len(set(parents)):
            raise RunFailure("grammar_duplicate_parents")
    relay = values["relay_workflow_id"]
    if relay not in {"none", scope["relay_workflow"]["workflow_id"]}:
        raise RunFailure("grammar_relay_id")
    control = values["control"]
    if control not in {"none", "compromise_discovered"}:
        raise RunFailure("grammar_control")
    return Command(
        command=values["command"],
        target_issue_id=target_id,
        generation=generation,
        source_role=role,
        parents=parents,
        relay_workflow_id=relay,
        control=control,
    )


def validate_payload(
    scope: Mapping[str, Any], payload: Mapping[str, Any]
) -> tuple[int, int, str, str]:
    repository = payload.get("repository")
    issue = payload.get("issue")
    installation = payload.get("installation")
    sender = payload.get("sender")
    comment = payload.get("comment")
    if payload.get("action") != "created":
        raise RunFailure("payload_action_invalid")
    if not isinstance(repository, dict) or repository.get("id") != scope["repository"]["id"]:
        raise RunFailure("payload_repository_id")
    if repository.get("full_name") != scope["repository"]["full_name"]:
        raise RunFailure("payload_repository_name")
    if not isinstance(installation, dict) or installation.get("id") != scope["apps"]["ingress"]["installation_id"]:
        raise RunFailure("payload_installation_id")
    if not isinstance(issue, dict) or issue.get("id") != scope["target_issue"]["id"]:
        raise RunFailure("payload_issue_id")
    if issue.get("number") != scope["target_issue"]["number"] or "pull_request" in issue:
        raise RunFailure("payload_target_not_issue")
    if not isinstance(sender, dict) or not isinstance(sender.get("id"), int):
        raise RunFailure("payload_sender_invalid")
    if sender["id"] not in {
        scope["principals"]["authorized_owner_id"],
        scope["principals"]["red_team_id"],
    }:
        raise RunFailure("payload_sender_untrusted")
    if not isinstance(comment, dict) or comment.get("user", {}).get("id") != sender["id"]:
        raise RunFailure("payload_comment_actor_mismatch")
    comment_id = comment.get("id")
    created_at = comment.get("created_at")
    body = comment.get("body")
    if not isinstance(comment_id, int) or comment_id <= 0:
        raise RunFailure("payload_comment_id")
    if not isinstance(created_at, str) or not isinstance(body, str):
        raise RunFailure("payload_comment_fields")
    return comment_id, sender["id"], created_at, body


def repository_ids(repositories: Iterable[dict[str, Any]]) -> set[int]:
    return {
        int(row["id"])
        for row in repositories
        if isinstance(row.get("id"), int)
    }


class B7Ledger:
    """Durable B7 delivery and endpoint-attempt records."""

    _COLUMNS = frozenset(
        {
            "decision",
            "reason",
            "phase",
            "patch_count",
            "precondition_state",
            "close_status",
            "close_state",
            "reopen_status",
            "reopen_state",
            "finished_at",
            "latency_ms",
        }
    )

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        try:
            self.connection = sqlite3.connect(
                path,
                timeout=20,
                isolation_level=None,
                check_same_thread=False,
            )
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS b7_delivery (
                    delivery_guid TEXT PRIMARY KEY,
                    delivery_body_sha256 TEXT NOT NULL,
                    comment_id INTEGER NOT NULL,
                    comment_body_sha256 TEXT NOT NULL,
                    actor_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    source_role TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    record_id TEXT,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS b7_action (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    delivery_guid TEXT NOT NULL,
                    comment_id INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    patch_count INTEGER NOT NULL DEFAULT 0,
                    precondition_state TEXT,
                    close_status INTEGER,
                    close_state TEXT,
                    reopen_status INTEGER,
                    reopen_state TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    latency_ms INTEGER
                );
                """
            )
            self.connection.commit()
            os.chmod(path, 0o600)
        except sqlite3.Error as error:
            raise RunFailure("b7_ledger_initialize") from error

    def close(self) -> None:
        self.connection.close()

    def delivery(self, guid: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM b7_delivery WHERE delivery_guid = ?", (guid,)
        ).fetchone()

    def record_delivery(
        self,
        observation: Observation,
        *,
        decision: str,
        reason: str,
        source_role: str,
        generation: int,
        record_id: str | None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO b7_delivery(
                delivery_guid, delivery_body_sha256, comment_id,
                comment_body_sha256, actor_id, created_at, decision, reason,
                source_role, generation, record_id, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation.guid,
                observation.delivery_body_sha256,
                observation.comment_id,
                observation.comment_body_sha256,
                observation.actor_id,
                observation.created_at_text,
                decision,
                reason,
                source_role,
                generation,
                record_id,
                utc_now(),
            ),
        )
        self.connection.commit()

    def insert_action(self, values: Mapping[str, Any]) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO b7_action(
                delivery_guid, comment_id, decision, reason, phase,
                patch_count, precondition_state, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["delivery_guid"],
                values["comment_id"],
                values["decision"],
                values["reason"],
                values["phase"],
                values.get("patch_count", 0),
                values.get("precondition_state"),
                values["started_at"],
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def update_action(self, action_id: int, **values: Any) -> None:
        if not values:
            return
        if any(key not in self._COLUMNS for key in values):
            raise RunFailure("b7_action_column_invalid")
        columns = ", ".join(f"{key} = ?" for key in values)
        self.connection.execute(
            f"UPDATE b7_action SET {columns} WHERE action_id = ?",
            (*values.values(), action_id),
        )
        self.connection.commit()

    def action(self, action_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM b7_action WHERE action_id = ?", (action_id,)
        ).fetchone()

    def actions_for_guid(self, guid: str) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM b7_action WHERE delivery_guid = ? ORDER BY action_id",
                (guid,),
            )
        )

    def actions(self) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM b7_action ORDER BY action_id"))


@dataclass
class SourceAdapter:
    """Translate verified GitHub facts into bounded B7 source evidence."""

    scope: Mapping[str, Any]
    store: SqliteAuthorityStore
    owner_policy: PolicyKey
    red_policy: PolicyKey
    signer: ed25519.Ed25519PrivateKey
    issuer_id: str = "github-verified-delivery-adapter"
    issuer_key_id: str = "github-delivery-adapter-ephemeral-v1"

    def source_event(self, observation: Observation, command: Command) -> SourceAuthorityEvent | None:
        if command.source_role != "root" or command.command != "close":
            return None
        controls = self.scope["generation_control"]
        initial_generation = int(controls["initial_generation"])
        owner_id = int(self.scope["principals"]["authorized_owner_id"])
        red_id = int(self.scope["principals"]["red_team_id"])
        policy: PolicyKey
        granted: Capability
        generation: int
        if observation.actor_id == owner_id:
            policy = self.owner_policy
            granted = Capability.ACT
            generation = command.generation
            current = self.store.policy(policy)
            if current is None or current.generation != generation:
                return None
        elif observation.actor_id == red_id:
            if not self._inside_compromise_interval(observation.created_at):
                return None
            # Discovery advances the owner generation and closes the bounded
            # red-team source route.  A later red-team root therefore cannot
            # enter the authority graph merely because its timestamp is still
            # inside the original synthetic interval.
            owner_current = self.store.policy(self.owner_policy)
            if owner_current is None or owner_current.generation != initial_generation:
                return None
            policy = self.red_policy
            granted = Capability.INFORM
            generation = initial_generation
        else:
            return None

        record_id = f"gh-comment-{observation.comment_id}"
        source_object: dict[str, object] = {
            "record_id": record_id,
            "department": "github",
            "source": policy.source,
            "operation": "issue_comment",
            "revision": SOURCE_REVISION,
            "action_scope": ACTION_SCOPE,
            "repository_id": str(self.scope["repository"]["id"]),
            "issue_id": str(self.scope["target_issue"]["id"]),
            "comment_id": str(observation.comment_id),
            "actor_id": str(observation.actor_id),
            "delivery_guid": observation.guid,
            "body_sha256": observation.comment_body_sha256,
        }
        commitment = sha256_bytes(canonical_json_bytes(source_object))
        receipt_id = "gh-receipt-" + sha256_text(
            json.dumps(
                {
                    "record_id": record_id,
                    "commitment": commitment,
                    "delivery_guid": observation.guid,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        draft = AuthorityReceipt(
            receipt_version="1",
            receipt_id=receipt_id,
            issuer_id=self.issuer_id,
            issuer_key_id=self.issuer_key_id,
            policy_key=policy,
            granting_generation=generation,
            granted_cap=granted,
            action_scope=ACTION_SCOPE,
            source_revision=SOURCE_REVISION,
            upstream_record_id=record_id,
            upstream_object_commitment=commitment,
            issuer_signature="00" * 64,
        )
        receipt = AuthorityReceipt(
            receipt_version=draft.receipt_version,
            receipt_id=draft.receipt_id,
            issuer_id=draft.issuer_id,
            issuer_key_id=draft.issuer_key_id,
            policy_key=draft.policy_key,
            granting_generation=draft.granting_generation,
            granted_cap=draft.granted_cap,
            action_scope=draft.action_scope,
            source_revision=draft.source_revision,
            upstream_record_id=draft.upstream_record_id,
            upstream_object_commitment=draft.upstream_object_commitment,
            issuer_signature=self.signer.sign(draft.canonical_bytes()).hex(),
        )
        return SourceAuthorityEvent(source_object, receipt)

    def _inside_compromise_interval(self, value: datetime) -> bool:
        controls = self.scope["generation_control"]
        start = parse_time(str(controls["compromise_interval_start"]))
        end = parse_time(str(controls["compromise_interval_end"]))
        return start <= value < end


@dataclass
class B7NativeState:
    """Own all production B7 authority state for this treatment."""

    scope: Mapping[str, Any]
    store: SqliteAuthorityStore
    gate: AdmissionGate
    gateway: AuthorityGateway
    controller: RevocationController
    adapter: SourceAdapter
    owner_policy: PolicyKey
    red_policy: PolicyKey
    registered_policy: PolicyKey
    identity_policy: PolicyKey
    freeform_policy: PolicyKey
    current_generation: int
    records_by_comment: dict[int, str]
    roots_by_comment: dict[int, str]
    receipts_by_root: dict[str, AuthorityReceipt]
    actors_by_comment: dict[int, int]
    discovery_comment_id: int | None = None

    @classmethod
    def create(cls, scope: Mapping[str, Any], path: Path) -> "B7NativeState":
        store = SqliteAuthorityStore(path)
        owner_policy = PolicyKey(
            "github", "github-owner", "issue_comment", SOURCE_REVISION, ACTION_SCOPE
        )
        red_policy = PolicyKey(
            "github", "github-red", "issue_comment", SOURCE_REVISION, ACTION_SCOPE
        )
        registered_policy = PolicyKey(
            "github", "custody", "registered_relay", "R1", ACTION_SCOPE
        )
        identity_policy = PolicyKey(
            "github", "custody", "identity", "R1", ACTION_SCOPE
        )
        freeform_policy = PolicyKey(
            "github", "custody", "freeform", "R1", ACTION_SCOPE
        )
        issuer_private = ed25519.Ed25519PrivateKey.generate()
        public_bytes = issuer_private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        store.put_issuer_key(
            issuer_id="github-verified-delivery-adapter",
            issuer_key_id="github-delivery-adapter-ephemeral-v1",
            public_key=public_bytes,
        )
        store.put_policy(
            PolicySnapshot(
                owner_policy,
                "github-owner-v1",
                int(scope["generation_control"]["initial_generation"]),
                OperationRole.ORIGIN,
                {ACTION_SCOPE: Capability.ACT},
            )
        )
        store.put_policy(
            PolicySnapshot(
                red_policy,
                "github-red-controlled-v1",
                int(scope["generation_control"]["initial_generation"]),
                OperationRole.ORIGIN,
                {ACTION_SCOPE: Capability.INFORM},
            )
        )
        for key in (registered_policy, identity_policy, freeform_policy):
            store.put_policy(
                PolicySnapshot(
                    key,
                    "github-transform-v1",
                    1,
                    OperationRole.RELAY,
                    {ACTION_SCOPE: Capability.ACT},
                )
            )
        adapter = SourceAdapter(
            scope=scope,
            store=store,
            owner_policy=owner_policy,
            red_policy=red_policy,
            signer=issuer_private,
        )
        gate = AdmissionGate(
            store=store,
            source_policy_keys=(owner_policy, red_policy),
            identity_policy_key=identity_policy,
            registered_policy_keys=(registered_policy,),
            freeform_policy_key=freeform_policy,
        )
        return cls(
            scope=scope,
            store=store,
            gate=gate,
            gateway=AuthorityGateway(store),
            controller=RevocationController(store),
            adapter=adapter,
            owner_policy=owner_policy,
            red_policy=red_policy,
            registered_policy=registered_policy,
            identity_policy=identity_policy,
            freeform_policy=freeform_policy,
            current_generation=int(scope["generation_control"]["initial_generation"]),
            records_by_comment={},
            roots_by_comment={},
            receipts_by_root={},
            actors_by_comment={},
        )

    @staticmethod
    def record_id(comment_id: int) -> str:
        return f"gh-comment-{comment_id}"

    def admit(self, observation: Observation, command: Command) -> dict[str, Any]:
        record_id = self.record_id(observation.comment_id)
        self.actors_by_comment[observation.comment_id] = observation.actor_id
        if command.source_role == "root":
            event = self.adapter.source_event(observation, command)
            if event is None:
                return {
                    "admitted": False,
                    "reason": "SOURCE_POLICY_NOT_CURRENT",
                    "record_id": record_id,
                }
            result = self.gate.admit_source(
                event,
                AuthorityOutput(record_id, event.source_object_commitment),
            )
            if result.admitted:
                self.records_by_comment[observation.comment_id] = record_id
                self.roots_by_comment[observation.comment_id] = record_id
                assert result.envelope is not None
                assert result.envelope.authority_receipt is not None
                self.receipts_by_root[record_id] = result.envelope.authority_receipt
            return self._admission_dict(result)

        if command.source_role not in {"relay", "activation"}:
            return {
                "admitted": False,
                "reason": "UNSUPPORTED_SOURCE_ROLE",
                "record_id": record_id,
            }
        owner_id = int(self.scope["principals"]["authorized_owner_id"])
        if observation.actor_id != owner_id:
            return {
                "admitted": False,
                "reason": "UNAUTHORIZED_TRANSFORM_ACTOR",
                "record_id": record_id,
            }
        if not command.parents:
            return {
                "admitted": False,
                "reason": "MISSING_REQUIRED_PARENT",
                "record_id": record_id,
            }
        parent_ids = tuple(self.records_by_comment.get(item, self.record_id(item)) for item in command.parents)
        result = self.gate.admit_registered(
            TransformRef(self.registered_policy),
            parent_ids,
            AuthorityOutput.from_text(record_id=record_id, text=observation.comment_body),
        )
        if result.admitted:
            self.records_by_comment[observation.comment_id] = record_id
        return self._admission_dict(result)

    def discover(self, observation: Observation, command: Command) -> dict[str, Any]:
        owner_id = int(self.scope["principals"]["authorized_owner_id"])
        if observation.actor_id != owner_id:
            return {"admitted": False, "reason": "DISCOVERY_ACTOR_UNTRUSTED", "record_id": self.record_id(observation.comment_id)}
        if (
            self.discovery_comment_id is not None
            or command.generation != int(self.scope["generation_control"]["remediated_generation"])
            or command.control != "compromise_discovered"
            or command.relay_workflow_id != "none"
            or not command.parents
        ):
            return {"admitted": False, "reason": "DISCOVERY_SHAPE_INVALID", "record_id": self.record_id(observation.comment_id)}
        selected: list[ReceiptRootKey] = []
        for parent_comment_id in command.parents:
            record_id = self.roots_by_comment.get(parent_comment_id)
            if record_id is None or self.actors_by_comment.get(parent_comment_id) != int(self.scope["principals"]["red_team_id"]):
                return {"admitted": False, "reason": "DISCOVERY_PARENT_NOT_COMPROMISED", "record_id": self.record_id(observation.comment_id)}
            selected.append(
                ReceiptRootKey.from_receipt(
                    self.receipts_by_root[record_id], custody_root_record_id=record_id
                )
            )
        current = self.store.policy(self.owner_policy)
        if current is None or current.generation != int(self.scope["generation_control"]["initial_generation"]):
            return {"admitted": False, "reason": "DISCOVERY_POLICY_STATE_INVALID", "record_id": self.record_id(observation.comment_id)}
        self.store.put_policy(
            PolicySnapshot(
                self.owner_policy,
                "github-owner-v2",
                int(self.scope["generation_control"]["remediated_generation"]),
                OperationRole.ORIGIN,
                {ACTION_SCOPE: Capability.ACT},
            ),
            expected_generation=current.generation,
        )
        revocation = self.controller.revoke_receipt_roots(
            revocation_id=f"github-discovery-{observation.comment_id}", root_keys=tuple(selected)
        )
        self.current_generation = int(self.scope["generation_control"]["remediated_generation"])
        self.discovery_comment_id = observation.comment_id
        return {
            "admitted": True,
            "reason": "compromise_discovered",
            "record_id": self.record_id(observation.comment_id),
            "revoked_record_ids": list(revocation.affected_record_ids),
        }

    @staticmethod
    def _admission_dict(result: AdmissionResult) -> dict[str, Any]:
        return {
            "admitted": result.admitted,
            "reason": result.reason,
            "record_id": result.record_id,
        }

    def summary(self) -> dict[str, Any]:
        records = self.store.records()
        return {
            "authority_record_count": len(records),
            "authority_record_ids": [record.record_id for record in records],
            "authority_action_decision_count": len(self.store.action_decisions()),
            "root_revocation_count": len(self.store.root_revocations()),
            "current_generation": self.current_generation,
            "issuer_public_key_sha256": sha256_bytes(
                self.store.public_key_for(
                    issuer_id=self.adapter.issuer_id,
                    issuer_key_id=self.adapter.issuer_key_id,
                )
                or b""
            ),
        }


@dataclass
class GitHubDispatcher:
    github: GitHubClient
    ingress_token: str
    action_token: str
    scope: Mapping[str, Any]
    ledger: B7Ledger
    action_id: int

    def dispatch(self, action: AuthorityAction) -> object:
        del action
        started = time.monotonic()
        issue = self.github.issue(self.ingress_token)
        if issue.get("state") != "open":
            raise RunFailure("issue_precondition_not_open")
        self.ledger.update_action(
            self.action_id, phase="permit_ready", precondition_state="open"
        )
        try:
            closed = self.github.patch_issue(
                self.action_token, self.scope["api"]["close_body"]
            )
        except RunFailure:
            self.ledger.update_action(self.action_id, phase="close_uncertain")
            raise
        self.ledger.update_action(
            self.action_id,
            phase="close_patched",
            patch_count=1,
            close_status=200,
            close_state=closed.get("state"),
        )
        readback = self.github.issue(self.ingress_token)
        if readback.get("state") != "closed":
            self.ledger.update_action(self.action_id, phase="close_uncertain")
            raise RunFailure("close_readback_not_closed")
        self.ledger.update_action(self.action_id, phase="close_observed")
        try:
            reopened = self.github.patch_issue(
                self.action_token, self.scope["api"]["compensation_body"]
            )
        except RunFailure:
            self.ledger.update_action(self.action_id, phase="reopen_uncertain")
            raise
        self.ledger.update_action(
            self.action_id,
            phase="reopen_patched",
            patch_count=2,
            reopen_status=200,
            reopen_state=reopened.get("state"),
        )
        final = self.github.issue(self.ingress_token)
        if final.get("state") != "open":
            self.ledger.update_action(self.action_id, phase="reopen_uncertain")
            raise RunFailure("compensation_readback_not_open")
        self.ledger.update_action(
            self.action_id,
            phase="compensated",
            finished_at=utc_now(),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return {"state": "open", "compensated": True}


class Runner:
    def __init__(self) -> None:
        self.scope = load_json(SCOPE_PATH)
        self.order = load_json(ORDER_PATH)
        self.scope_digest = file_digest(SCOPE_PATH)
        self.order_digest = file_digest(ORDER_PATH)
        if str(self.scope["api"]["version"]) != SOURCE_REVISION.removeprefix(
            "github-rest-"
        ):
            raise RunFailure("api_version_mismatch")
        if file_digest(RELAY_PATH) != self.scope["relay_workflow"]["sha256"]:
            raise RunFailure("relay_artifact_digest_mismatch")
        self.guids = self._validate_order()
        self.run_id = "B7_20260827"
        self.started_at = utc_now()
        ledger_path = Path(os.environ.get("CUSTODY_B7_LEDGER", str(DEFAULT_LEDGER)))
        if ledger_path.exists():
            raise RunFailure("b7_namespace_not_empty")
        self.ledger = B7Ledger(ledger_path)
        self.authority = B7NativeState.create(self.scope, ledger_path)
        self.github = GitHubClient(self.scope)
        self.github.configure_target(self.scope)
        self.receiver = ReceiverClient(self.scope)
        self.ingress_key = private_key(INGRESS_KEY_PATH)
        self.action_key = private_key(ACTION_KEY_PATH)
        self.ingress_jwt = app_jwt(self.scope["apps"]["ingress"]["app_id"], self.ingress_key)
        self.action_jwt = app_jwt(self.scope["apps"]["action"]["app_id"], self.action_key)
        self.ingress_token = ""
        self.action_token = ""
        self.delivery_details: dict[str, dict[str, Any]] = {}
        self.redelivery_details: dict[str, dict[str, Any]] = {}
        self.records: list[dict[str, Any]] = []
        self.error: str | None = None
        self.final_issue: dict[str, Any] | None = None

    def _validate_order(self) -> list[str]:
        values = self.order.get("delivery_guids")
        if self.order.get("schema_version") != 1 or not isinstance(values, list):
            raise RunFailure("delivery_order_artifact_invalid")
        if not values or not all(isinstance(value, str) and GUID_RE.match(value) for value in values):
            raise RunFailure("delivery_order_guids_invalid")
        unique = list(dict.fromkeys(values))
        redelivery = self.order.get("redelivery_guid")
        if len(values) != len(unique) + 1 or unique.count(redelivery) != 1:
            raise RunFailure("delivery_order_duplicate_shape")
        if values.count(redelivery) != 2:
            raise RunFailure("delivery_order_redelivery_count")
        return values

    def verify_apps_and_installations(self) -> None:
        ingress_app = self.github.app(self.ingress_jwt)
        action_app = self.github.app(self.action_jwt)
        ingress_permissions = ingress_app.get("permissions")
        action_permissions = action_app.get("permissions")
        if not isinstance(ingress_permissions, dict) or ingress_permissions.get("issues") != "read":
            raise RunFailure("ingress_permission_readback")
        if "issue_comment" not in ingress_app.get("events", []):
            raise RunFailure("ingress_event_readback")
        if not isinstance(action_permissions, dict) or action_permissions.get("issues") != "write":
            raise RunFailure("action_permission_readback")
        if action_app.get("events") != []:
            raise RunFailure("action_event_readback")
        self.ingress_token = self.github.mint_installation(
            self.ingress_jwt, self.scope["apps"]["ingress"]["installation_id"]
        )
        self.action_token = self.github.mint_installation(
            self.action_jwt, self.scope["apps"]["action"]["installation_id"]
        )
        target_id = int(self.scope["repository"]["id"])
        if repository_ids(self.github.installation_repositories(self.ingress_token)) != {target_id}:
            raise RunFailure("ingress_repository_selection_readback")
        if repository_ids(self.github.installation_repositories(self.action_token)) != {target_id}:
            raise RunFailure("action_repository_selection_readback")

    def load_delivery_log(self) -> None:
        rows = self.github.hook_deliveries(self.ingress_jwt)
        by_guid: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            guid = row.get("guid")
            row_id = row.get("id")
            if isinstance(guid, str) and GUID_RE.match(guid) and isinstance(row_id, int):
                by_guid.setdefault(guid, []).append(row)
        expected_hook = int(self.scope["apps"]["ingress"]["hook_id"])
        for guid in dict.fromkeys(self.guids):
            candidates = by_guid.get(guid, [])
            initial = [row for row in candidates if row.get("redelivery") is not True]
            redelivery = [row for row in candidates if row.get("redelivery") is True]
            if len(initial) != 1:
                raise RunFailure("initial_delivery_log_missing_or_ambiguous")
            detail = self.github.hook_delivery(self.ingress_jwt, int(initial[0]["id"]))
            self._validate_delivery_detail(detail, guid, expected_hook)
            self.delivery_details[guid] = detail
            if guid == self.order["redelivery_guid"]:
                if len(redelivery) != 1:
                    raise RunFailure("redelivery_log_missing_or_ambiguous")
                redetail = self.github.hook_delivery(self.ingress_jwt, int(redelivery[0]["id"]))
                self._validate_delivery_detail(redetail, guid, expected_hook, redelivery=True)
                self.redelivery_details[guid] = redetail

    def _validate_delivery_detail(
        self,
        detail: Mapping[str, Any],
        guid: str,
        expected_hook: int,
        *,
        redelivery: bool = False,
    ) -> None:
        request = detail.get("request")
        headers = request.get("headers") if isinstance(request, dict) else None
        normalized = {str(k).lower(): str(v) for k, v in headers.items()} if isinstance(headers, dict) else {}
        if (
            detail.get("guid") != guid
            or detail.get("event") != "issue_comment"
            or detail.get("action") != "created"
            or detail.get("repository_id") != self.scope["repository"]["id"]
            or detail.get("installation_id") != self.scope["apps"]["ingress"]["installation_id"]
            or normalized.get("x-github-hook-id") != str(expected_hook)
            or detail.get("redelivery") is not redelivery
            or detail.get("status_code") != 200
        ):
            raise RunFailure("delivery_log_mismatch")

    def observation(self, guid: str, occurrence: int) -> Observation:
        detail = self.redelivery_details.get(guid) if occurrence else self.delivery_details[guid]
        envelope, _raw, payload = self.receiver.get(guid)
        comment_id, actor_id, created_text, body = validate_payload(self.scope, payload)
        request = detail.get("request")
        detail_payload = request.get("payload") if isinstance(request, dict) else None
        detail_comment = detail_payload.get("comment") if isinstance(detail_payload, dict) else None
        if not isinstance(detail_comment, dict) or detail_comment.get("id") != comment_id:
            raise RunFailure("delivery_detail_comment_mismatch")
        if detail_comment.get("user", {}).get("id") != actor_id:
            raise RunFailure("delivery_detail_actor_mismatch")
        if not isinstance(detail_comment.get("body"), str) or sha256_text(detail_comment["body"]) != sha256_text(body):
            raise RunFailure("delivery_detail_body_mismatch")
        api_comment = self.github.comment(self.ingress_token, comment_id)
        if api_comment.get("id") != comment_id or api_comment.get("user", {}).get("id") != actor_id:
            raise RunFailure("comment_readback_identity_mismatch")
        if api_comment.get("body") != body or api_comment.get("created_at") != created_text:
            raise RunFailure("comment_readback_content_mismatch")
        issue = self.github.issue(self.ingress_token)
        if issue.get("id") != self.scope["target_issue"]["id"] or issue.get("number") != self.scope["target_issue"]["number"] or "pull_request" in issue:
            raise RunFailure("issue_readback_identity_mismatch")
        parse_time(created_text)
        return Observation(
            guid=guid,
            delivery_id=int(detail["id"]),
            redelivery=bool(detail.get("redelivery")),
            comment_id=comment_id,
            actor_id=actor_id,
            created_at=parse_time(created_text),
            created_at_text=created_text,
            comment_body=body,
            comment_body_sha256=sha256_text(body),
            delivery_body_sha256=str(envelope["body_sha256"]),
            payload=payload,
        )

    def _action_record(
        self,
        observation: Observation,
        *,
        decision: str,
        reason: str,
        action_id: int,
        record_id: str,
        admission: Mapping[str, Any],
        execution: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "delivery_guid": observation.guid,
            "delivery_id": observation.delivery_id,
            "redelivery": observation.redelivery,
            "comment_id": observation.comment_id,
            "actor_id": observation.actor_id,
            "created_at": observation.created_at_text,
            "comment_body_sha256": observation.comment_body_sha256,
            "delivery_body_sha256": observation.delivery_body_sha256,
            "decision": decision,
            "reason": reason,
            "action_id": action_id,
            "record_id": record_id,
            "admission": dict(admission),
        }
        if execution is not None:
            result["execution"] = dict(execution)
        return result

    @staticmethod
    def _execution_observation(execution: AuthorityExecution) -> dict[str, Any]:
        return {
            "allowed": execution.decision.allowed,
            "reason": execution.decision.reason,
            "effective_cap": execution.decision.effective_cap.value,
            "dispatched": execution.dispatched,
            "evaluated_record_ids": list(execution.decision.evaluated_record_ids),
            "support_root_key_digests": list(execution.decision.support_root_key_digests),
        }

    def process(self) -> None:
        self.verify_apps_and_installations()
        self.load_delivery_log()
        if self.github.issue(self.ingress_token).get("state") != "open":
            raise RunFailure("initial_issue_not_open")
        occurrences: dict[str, int] = {}
        for guid in self.guids:
            occurrence = occurrences.get(guid, 0)
            occurrences[guid] = occurrence + 1
            observation = self.observation(guid, occurrence)
            existing = self.ledger.delivery(guid)
            if existing is not None:
                if (
                    existing["delivery_body_sha256"] != observation.delivery_body_sha256
                    or existing["comment_id"] != observation.comment_id
                    or existing["comment_body_sha256"] != observation.comment_body_sha256
                    or existing["actor_id"] != observation.actor_id
                ):
                    raise RunFailure("replay_payload_drift")
                if occurrence != 1:
                    raise RunFailure("unexpected_existing_delivery")
                actions = self.ledger.actions_for_guid(guid)
                if not actions:
                    raise RunFailure("redelivery_action_missing")
                row = actions[0]
                record_id = str(existing["record_id"] or self.authority.record_id(observation.comment_id))
                self.records.append(
                    self._action_record(
                        observation,
                        decision="replay_noop",
                        reason="duplicate_delivery_guid",
                        action_id=int(row["action_id"]),
                        record_id=record_id,
                        admission={"admitted": True, "reason": "prior_decision"},
                    )
                )
                action_id = self.ledger.insert_action(
                    {
                        "delivery_guid": guid,
                        "comment_id": observation.comment_id,
                        "decision": "replay_noop",
                        "reason": "duplicate_delivery_guid",
                        "phase": "compensated",
                        "started_at": utc_now(),
                    }
                )
                self.records[-1]["action_id"] = action_id
                continue

            command = parse_command(observation.comment_body, self.scope)
            if command.command == self.scope["generation_control"]["discovery_command"]:
                admission = self.authority.discover(observation, command)
                decision = "observe" if admission["admitted"] else "deny"
                reason = str(admission["reason"])
                action_id = self.ledger.insert_action(
                    {
                        "delivery_guid": guid,
                        "comment_id": observation.comment_id,
                        "decision": decision,
                        "reason": reason,
                        "phase": "compensated",
                        "started_at": utc_now(),
                    }
                )
                self.ledger.record_delivery(
                    observation,
                    decision=decision,
                    reason=reason,
                    source_role=command.source_role,
                    generation=command.generation,
                    record_id=self.authority.record_id(observation.comment_id),
                )
                self.records.append(
                    self._action_record(
                        observation,
                        decision=decision,
                        reason=reason,
                        action_id=action_id,
                        record_id=self.authority.record_id(observation.comment_id),
                        admission=admission,
                    )
                )
                continue

            admission = self.authority.admit(observation, command)
            record_id = str(admission["record_id"])
            if command.source_role != "activation":
                decision = "observe" if admission["admitted"] else "deny"
                reason = str(admission["reason"])
                action_id = self.ledger.insert_action(
                    {
                        "delivery_guid": guid,
                        "comment_id": observation.comment_id,
                        "decision": decision,
                        "reason": reason,
                        "phase": "compensated",
                        "started_at": utc_now(),
                    }
                )
                self.ledger.record_delivery(
                    observation,
                    decision=decision,
                    reason=reason,
                    source_role=command.source_role,
                    generation=command.generation,
                    record_id=record_id if admission["admitted"] else None,
                )
                self.records.append(
                    self._action_record(
                        observation,
                        decision=decision,
                        reason=reason,
                        action_id=action_id,
                        record_id=record_id,
                        admission=admission,
                    )
                )
                continue

            action_id = self.ledger.insert_action(
                {
                    "delivery_guid": guid,
                    "comment_id": observation.comment_id,
                    "decision": "pending",
                    "reason": "B7_EVALUATION_PENDING",
                    "phase": "decision_pending",
                    "started_at": utc_now(),
                }
            )
            request = AuthorityAction(
                request_id=f"b7-action-{observation.comment_id}",
                action_scope=ACTION_SCOPE,
                payload={
                    "repository_id": int(self.scope["repository"]["id"]),
                    "issue_id": int(self.scope["target_issue"]["id"]),
                    "desired_state": "closed",
                },
            )
            dispatcher = GitHubDispatcher(
                github=self.github,
                ingress_token=self.ingress_token,
                action_token=self.action_token,
                scope=self.scope,
                ledger=self.ledger,
                action_id=action_id,
            )
            execution = self.authority.gateway.execute(
                request, (record_id,), dispatcher
            )
            observation_execution = self._execution_observation(execution)
            decision = "allow" if execution.decision.allowed else "deny"
            reason = execution.decision.reason
            if not execution.dispatched:
                self.ledger.update_action(
                    action_id,
                    decision=decision,
                    reason=reason,
                    phase="compensated",
                    finished_at=utc_now(),
                )
            else:
                row = self.ledger.action(action_id)
                if row is None or row["phase"] != "compensated":
                    raise RunFailure("action_compensation_not_recorded")
                self.ledger.update_action(action_id, decision=decision, reason=reason)
            self.ledger.record_delivery(
                observation,
                decision=decision,
                reason=reason,
                source_role=command.source_role,
                generation=command.generation,
                record_id=record_id if admission["admitted"] else None,
            )
            self.records.append(
                self._action_record(
                    observation,
                    decision=decision,
                    reason=reason,
                    action_id=action_id,
                    record_id=record_id,
                    admission=admission,
                    execution=observation_execution,
                )
            )
        self.final_issue = self.github.issue(self.ingress_token)
        if self.final_issue.get("state") != "open":
            raise RunFailure("final_issue_not_open")

    def result(self, status: str, error: str | None = None) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        for row in self.ledger.actions():
            actions.append(
                {
                    "action_id": int(row["action_id"]),
                    "delivery_guid": row["delivery_guid"],
                    "comment_id": int(row["comment_id"]),
                    "decision": row["decision"],
                    "reason": row["reason"],
                    "phase": row["phase"],
                    "patch_count": int(row["patch_count"]),
                    "precondition_state": row["precondition_state"],
                    "close_status": row["close_status"],
                    "close_state": row["close_state"],
                    "reopen_status": row["reopen_status"],
                    "reopen_state": row["reopen_state"],
                    "latency_ms": row["latency_ms"],
                }
            )
        value: dict[str, Any] = {
            "format": "custody.external-validity.github-b7-result",
            "schema_version": 1,
            "run_id": self.run_id,
            "treatment": "B7",
            "status": status,
            "started_at": self.started_at,
            "finished_at": utc_now(),
            "scope_sha256": self.scope_digest,
            "delivery_order_sha256": self.order_digest,
            "delivery_order_count": len(self.guids),
            "unique_delivery_count": len(set(self.guids)),
            "records": self.records,
            "actions": actions,
            "budgets": {
                "github_reads": self.github.reads,
                "github_read_ceiling": self.github.max_reads,
                "issue_patch_requests": self.github.patches,
                "issue_patch_ceiling": self.github.max_patches,
                "model_calls": 0,
                "model_spend_usd": 0,
            },
            "scorer_blind": {
                "case_manifest_read": False,
                "expected_outcome_read": False,
                "case_label_read": False,
                "scorer_fields_observed": 0,
            },
            "production_b7": self.authority.summary(),
            "final_issue": (
                None
                if self.final_issue is None
                else {
                    "id": self.final_issue.get("id"),
                    "number": self.final_issue.get("number"),
                    "state": self.final_issue.get("state"),
                    "state_reason": self.final_issue.get("state_reason"),
                }
            ),
            "receiver": {
                "signature_reverified_constant_time": True,
                "schema": BODY_SCHEMA,
            },
        }
        if error:
            value["error"] = error
        return value


def main() -> int:
    runner: Runner | None = None
    status = "COMPLETED"
    error: str | None = None
    try:
        runner = Runner()
        runner.process()
    except RunFailure as failure:
        status = "BLOCKED"
        error = str(failure)
    except Exception:  # no implementation detail in result/log
        status = "INVALID"
        error = "unexpected_runner_exception"
    if runner is None:
        print(json.dumps({"status": status, "error": error}, sort_keys=True))
        return 1
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(runner.result(status, error), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    runner.ledger.close()
    runner.authority.store.close()
    print(json.dumps({"status": status, "result": str(RESULT_PATH), "error": error}, sort_keys=True))
    return 0 if status == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
