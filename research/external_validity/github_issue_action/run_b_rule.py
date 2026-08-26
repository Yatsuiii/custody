"""Execute the preregistered, scorer-blind deterministic GitHub baseline.

The runner consumes only RUNNER_SCOPE.json and DELIVERY_ORDER.json.  It never
loads CASE_MANIFEST.json: case labels and expected outcomes remain scorer-only
inputs.  The two SQLite tables are the delivery replay ledger and the durable
action/compensation ledger.
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
from typing import Any, Iterable

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


ROOT = Path(__file__).parent
SCOPE_PATH = ROOT / "RUNNER_SCOPE.json"
ORDER_PATH = ROOT / "DELIVERY_ORDER.json"
RELAY_PATH = ROOT / "RELAY_WORKFLOW.json"
RESULT_PATH = ROOT / "results" / "B_RULE_RESULT.json"
SECRET_DIR = Path("/home/Yatsuiii/.config/custody-execution-secrets")
INGRESS_KEY_PATH = SECRET_DIR / "ingress.pem"
ACTION_KEY_PATH = SECRET_DIR / "action.pem"
WEBHOOK_SECRET_PATH = SECRET_DIR / "webhook.secret"
RECEIVER_TOKEN_PATH = SECRET_DIR / "receiver-read.token"
DEFAULT_LEDGER = Path("/home/Yatsuiii/.local/state/custody-external-validity/b-rule.sqlite3")
USER_AGENT = "custody-external-validity-b-rule/1"
GUID_RE = re.compile(r"^[0-9a-f-]{20,80}$", re.IGNORECASE)
BODY_SCHEMA = "github-issue-comment-raw-delivery-v1"


class RunFailure(RuntimeError):
    """A bounded failure that is safe to put in a result artifact."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return sha256_bytes(path.read_bytes())


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
    header = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = b64url(
        json.dumps({"iat": now - 30, "exp": now + 540, "iss": app_id}, separators=(",", ":")).encode()
    )
    signing = f"{header}.{claims}".encode("ascii")
    signature = key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    return signing.decode("ascii") + "." + b64url(signature)


class GitHubClient:
    """Small bounded REST client; response bodies never enter error messages."""

    def __init__(self, scope: dict[str, Any]) -> None:
        self.host = str(scope["api"]["host"])
        self.version = str(scope["api"]["version"])
        self.max_reads = int(scope["limits"]["max_github_reads"])
        self.max_patches = int(scope["limits"]["max_issue_patch_requests"])
        self.reads = 0
        self.patches = 0

    def request(self, method: str, path: str, token: str, *, body: dict[str, Any] | None = None) -> Any:
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

    def app(self, token: str) -> dict[str, Any]:
        value = self.request("GET", "/app", token)
        if not isinstance(value, dict):
            raise RunFailure("app_readback_invalid")
        return value

    def mint_installation(self, app_jwt_value: str, installation_id: int) -> str:
        value = self.request("POST", f"/app/installations/{installation_id}/access_tokens", app_jwt_value)
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

    def configure_target(self, scope: dict[str, Any]) -> None:
        full_name = str(scope["repository"]["full_name"])
        owner, name = full_name.split("/", 1)
        self.repo_owner = owner
        self.repo_name = name
        self.issue_path = str(scope["api"]["issue_patch_path"])


class ReceiverClient:
    """Reads and re-verifies the receiver's exact signed raw body."""

    def __init__(self, scope: dict[str, Any]) -> None:
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
        raw_digest = sha256_bytes(raw)
        if envelope.get("body_sha256") != raw_digest:
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
        expected = "sha256=" + hmac.new(self.webhook_secret, raw, hashlib.sha256).hexdigest()
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


@dataclass
class AuthorityRecord:
    comment_id: int
    actor_id: int
    created_at: datetime
    generation: int
    source_role: str
    depth: int
    compromised: bool
    command: str


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


def parse_command(body: str, scope: dict[str, Any]) -> Command:
    grammar = scope["grammar"]
    expected_header = grammar["header"]
    lines = body.split("\n")
    if not lines or lines[0] != expected_header or len(lines) != 1 + len(grammar["field_order"]):
        raise RunFailure("grammar_header_or_line_count")
    values: dict[str, str] = {}
    for line, key in zip(lines[1:], grammar["field_order"]):
        prefix = key + "="
        if not line.startswith(prefix) or key in values:
            raise RunFailure("grammar_field_order")
        value = line[len(prefix):]
        if not value or "\n" in value or "\r" in value:
            raise RunFailure("grammar_field_value")
        values[key] = value
    allowed_roles = {"root", "relay", "activation", "incident_discovery"}
    if values["command"] not in {"close", scope["generation_control"]["discovery_command"]}:
        raise RunFailure("grammar_command")
    try:
        target_id = int(values["target_issue_id"])
        generation = int(values["generation"])
    except ValueError as error:
        raise RunFailure("grammar_numeric_field") from error
    if target_id != int(scope["target_issue"]["id"]):
        raise RunFailure("grammar_target_mismatch")
    if generation not in {
        int(scope["generation_control"]["initial_generation"]),
        int(scope["generation_control"]["remediated_generation"]),
    }:
        raise RunFailure("grammar_generation")
    role = values["source_role"]
    if role not in allowed_roles:
        raise RunFailure("grammar_source_role")
    parent_value = values["parent_comment_ids"]
    if parent_value == "none":
        parents: tuple[int, ...] = ()
    else:
        parts = parent_value.split(str(grammar["parent_separator"]))
        if not parts or any(not part.isdigit() or int(part) <= 0 for part in parts):
            raise RunFailure("grammar_parent_ids")
        parsed = tuple(int(part) for part in parts)
        if len(set(parsed)) != len(parsed):
            raise RunFailure("grammar_duplicate_parents")
        parents = parsed
    relay = values["relay_workflow_id"]
    control = values["control"]
    if relay != "none" and relay != scope["relay_workflow"]["workflow_id"]:
        raise RunFailure("grammar_relay_id")
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


class Authority:
    """Implements exact actor/generation/parent authority without semantics."""

    def __init__(self, scope: dict[str, Any]) -> None:
        self.scope = scope
        self.owner_id = int(scope["principals"]["authorized_owner_id"])
        self.red_team_id = int(scope["principals"]["red_team_id"])
        self.initial_generation = int(scope["generation_control"]["initial_generation"])
        self.remediated_generation = int(scope["generation_control"]["remediated_generation"])
        self.current_generation = self.initial_generation
        self.discovery_comment_id: int | None = None
        self.records: dict[int, AuthorityRecord] = {}
        self.compromise_start = parse_time(scope["generation_control"]["compromise_interval_start"])
        self.compromise_end = parse_time(scope["generation_control"]["compromise_interval_end"])

    def _parent_records(self, command: Command, created: datetime) -> tuple[list[AuthorityRecord], int]:
        if not command.parents:
            raise RunFailure("parent_reference_missing")
        if len(command.parents) > int(self.scope["grammar"]["max_parent_depth"]):
            raise RunFailure("parent_depth_limit")
        parents: list[AuthorityRecord] = []
        for parent_id in command.parents:
            parent = self.records.get(parent_id)
            if parent is None:
                raise RunFailure("parent_reference_missing")
            if parent.created_at >= created:
                raise RunFailure("parent_temporal_order")
            if parent.generation != self.current_generation:
                raise RunFailure("parent_stale_generation")
            if parent.compromised:
                raise RunFailure("parent_compromised")
            parents.append(parent)
        depth = max(parent.depth for parent in parents) + 1
        if depth > int(self.scope["grammar"]["max_parent_depth"]):
            raise RunFailure("parent_depth_limit")
        return parents, depth

    def evaluate(self, observation: Observation) -> tuple[str, str, Command]:
        command = parse_command(observation.comment_body, self.scope)
        if command.command == self.scope["generation_control"]["discovery_command"]:
            if observation.actor_id != self.owner_id:
                raise RunFailure("discovery_actor_untrusted")
            if (
                command.source_role != "incident_discovery"
                or command.generation != self.remediated_generation
                or command.control != "compromise_discovered"
                or command.relay_workflow_id != "none"
                or self.discovery_comment_id is not None
            ):
                raise RunFailure("discovery_shape_invalid")
            if not command.parents:
                raise RunFailure("discovery_parent_missing")
            for parent_id in command.parents:
                parent = self.records.get(parent_id)
                if parent is None or not parent.compromised:
                    raise RunFailure("discovery_parent_not_compromised")
                if parent.created_at >= observation.created_at:
                    raise RunFailure("discovery_temporal_order")
            self.current_generation = self.remediated_generation
            self.discovery_comment_id = observation.comment_id
            self.records[observation.comment_id] = AuthorityRecord(
                observation.comment_id,
                observation.actor_id,
                observation.created_at,
                command.generation,
                command.source_role,
                max((self.records[parent].depth for parent in command.parents), default=-1) + 1,
                False,
                command.command,
            )
            return "observe", "compromise_discovered", command

        if command.command != "close":
            raise RunFailure("command_not_close")
        if command.source_role == "root":
            if command.parents or command.relay_workflow_id != "none" or command.control != "none":
                raise RunFailure("root_shape_invalid")
            if observation.actor_id == self.red_team_id:
                if command.generation != self.initial_generation:
                    raise RunFailure("red_team_generation_invalid")
                if not self.compromise_start <= observation.created_at < self.compromise_end:
                    raise RunFailure("red_team_outside_compromise_interval")
                if self.current_generation != self.initial_generation:
                    raise RunFailure("red_team_root_revoked")
                self.records[observation.comment_id] = AuthorityRecord(
                    observation.comment_id,
                    observation.actor_id,
                    observation.created_at,
                    command.generation,
                    command.source_role,
                    0,
                    True,
                    command.command,
                )
                return "observe", "controlled_compromised_root", command
            if observation.actor_id != self.owner_id:
                raise RunFailure("root_actor_untrusted")
            if command.generation != self.current_generation:
                raise RunFailure("root_stale_generation")
            self.records[observation.comment_id] = AuthorityRecord(
                observation.comment_id,
                observation.actor_id,
                observation.created_at,
                command.generation,
                command.source_role,
                0,
                False,
                command.command,
            )
            return "observe", "authorized_root", command

        if observation.actor_id != self.owner_id:
            raise RunFailure("source_actor_untrusted")
        if command.generation != self.current_generation:
            raise RunFailure("source_stale_generation")
        if command.source_role == "relay":
            if command.relay_workflow_id != self.scope["relay_workflow"]["workflow_id"] or command.control != "none":
                raise RunFailure("relay_shape_invalid")
            parents, depth = self._parent_records(command, observation.created_at)
            del parents
            self.records[observation.comment_id] = AuthorityRecord(
                observation.comment_id,
                observation.actor_id,
                observation.created_at,
                command.generation,
                command.source_role,
                depth,
                False,
                command.command,
            )
            return "observe", "authorized_relay", command
        if command.source_role == "activation":
            if command.control != "none":
                raise RunFailure("activation_control_invalid")
            if command.relay_workflow_id not in {
                "none",
                self.scope["relay_workflow"]["workflow_id"],
            }:
                raise RunFailure("activation_relay_invalid")
            _, depth = self._parent_records(command, observation.created_at)
            self.records[observation.comment_id] = AuthorityRecord(
                observation.comment_id,
                observation.actor_id,
                observation.created_at,
                command.generation,
                command.source_role,
                depth,
                False,
                command.command,
            )
            return "allow", "authorized_activation", command
        raise RunFailure("close_source_role_invalid")


class Ledger:
    """Durable, bounded state with explicit replay and compensation phases."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS delivery_ledger (
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
                recorded_at TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS action_ledger (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                delivery_guid TEXT NOT NULL,
                comment_id INTEGER NOT NULL,
                desired_state TEXT NOT NULL,
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
            )
            """
        )
        self.connection.commit()
        os.chmod(path, 0o600)

    def close(self) -> None:
        self.connection.close()

    def delivery(self, guid: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM delivery_ledger WHERE delivery_guid = ?", (guid,)
        ).fetchone()

    def record_delivery_with_role(
        self,
        observation: Observation,
        decision: str,
        reason: str,
        source_role: str,
        generation: int,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO delivery_ledger(
                delivery_guid, delivery_body_sha256, comment_id, comment_body_sha256,
                actor_id, created_at, decision, reason, source_role, generation, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                utc_now(),
            ),
        )
        self.connection.commit()

    def insert_action(self, values: dict[str, Any]) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO action_ledger(
                delivery_guid, comment_id, desired_state, decision, reason, phase,
                patch_count, precondition_state, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["delivery_guid"],
                values["comment_id"],
                values["desired_state"],
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
        columns = ", ".join(f"{key} = ?" for key in values)
        self.connection.execute(
            f"UPDATE action_ledger SET {columns} WHERE action_id = ?",
            (*values.values(), action_id),
        )
        self.connection.commit()

    def pending_actions(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM action_ledger WHERE phase IN ('permit_ready','close_uncertain','close_patched','close_observed','reopen_uncertain','reopen_patched') ORDER BY action_id"
            )
        )

    def actions(self) -> list[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM action_ledger ORDER BY action_id"))

    def actions_for_guid(self, guid: str) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM action_ledger WHERE delivery_guid = ? ORDER BY action_id", (guid,)
            )
        )


def header_value(detail: dict[str, Any], name: str) -> str | None:
    request = detail.get("request")
    headers = request.get("headers") if isinstance(request, dict) else None
    if not isinstance(headers, dict):
        return None
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value) if value is not None else None
    return None


def payload_comment(payload: dict[str, Any]) -> dict[str, Any]:
    comment = payload.get("comment")
    if not isinstance(comment, dict):
        raise RunFailure("payload_comment_missing")
    return comment


def validate_payload(scope: dict[str, Any], payload: dict[str, Any]) -> tuple[int, int, str, str]:
    repository = payload.get("repository")
    issue = payload.get("issue")
    installation = payload.get("installation")
    sender = payload.get("sender")
    comment = payload_comment(payload)
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
    if comment.get("user", {}).get("id") != sender["id"]:
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
    return {int(row["id"]) for row in repositories if isinstance(row.get("id"), int)}


class Runner:
    def __init__(self) -> None:
        self.scope = load_json(SCOPE_PATH)
        self.order = load_json(ORDER_PATH)
        self.scope_digest = file_digest(SCOPE_PATH)
        self.order_digest = file_digest(ORDER_PATH)
        relay_digest = file_digest(RELAY_PATH)
        if relay_digest != self.scope["relay_workflow"]["sha256"]:
            raise RunFailure("relay_artifact_digest_mismatch")
        self.guids = self._validate_order()
        self.run_id = "B_RULE_20260826"
        self.started_at = utc_now()
        ledger_path = Path(os.environ.get("CUSTODY_RULE_LEDGER", str(DEFAULT_LEDGER)))
        self.ledger = Ledger(ledger_path)
        self.github = GitHubClient(self.scope)
        self.github.configure_target(self.scope)
        self.receiver = ReceiverClient(self.scope)
        self.ingress_key = private_key(INGRESS_KEY_PATH)
        self.action_key = private_key(ACTION_KEY_PATH)
        self.ingress_jwt = app_jwt(self.scope["apps"]["ingress"]["app_id"], self.ingress_key)
        self.action_jwt = app_jwt(self.scope["apps"]["action"]["app_id"], self.action_key)
        self.ingress_token = ""
        self.action_token = ""
        self.authority = Authority(self.scope)
        self.delivery_details: dict[str, dict[str, Any]] = {}
        self.redelivery_details: dict[str, dict[str, Any]] = {}
        self.records: list[dict[str, Any]] = []
        self.blocker: str | None = None

    def _validate_order(self) -> list[str]:
        if self.order.get("treatment") != "B_RULE" or self.order.get("schema_version") != 1:
            raise RunFailure("delivery_order_artifact_invalid")
        values = self.order.get("delivery_guids")
        if not isinstance(values, list) or not values or not all(isinstance(value, str) and GUID_RE.match(value) for value in values):
            raise RunFailure("delivery_order_guids_invalid")
        unique = list(dict.fromkeys(values))
        if len(values) != len(unique) + 1:
            raise RunFailure("delivery_order_duplicate_shape")
        duplicates = [value for value in unique if values.count(value) > 1]
        if duplicates != [self.order.get("redelivery_guid")]:
            raise RunFailure("delivery_order_redelivery_mismatch")
        if values.count(self.order.get("redelivery_guid")) != 2:
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
        detail: dict[str, Any],
        guid: str,
        expected_hook: int,
        *,
        redelivery: bool = False,
    ) -> None:
        if detail.get("guid") != guid or detail.get("event") != "issue_comment" or detail.get("action") != "created":
            raise RunFailure("delivery_log_event_mismatch")
        if detail.get("repository_id") != self.scope["repository"]["id"]:
            raise RunFailure("delivery_log_repository_mismatch")
        if detail.get("installation_id") != self.scope["apps"]["ingress"]["installation_id"]:
            raise RunFailure("delivery_log_installation_mismatch")
        if header_value(detail, "x-github-hook-id") != str(expected_hook):
            raise RunFailure("delivery_log_hook_mismatch")
        if detail.get("redelivery") is not redelivery:
            raise RunFailure("delivery_log_redelivery_mismatch")
        if detail.get("status_code") != 200:
            raise RunFailure("delivery_log_status_mismatch")

    def observation(self, guid: str, occurrence: int) -> Observation:
        detail = self.redelivery_details.get(guid) if occurrence > 0 else self.delivery_details[guid]
        if detail is None:
            raise RunFailure("delivery_detail_missing")
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
        if not isinstance(api_comment.get("body"), str) or sha256_text(api_comment["body"]) != sha256_text(body):
            raise RunFailure("comment_readback_body_mismatch")
        if api_comment.get("created_at") != created_text:
            raise RunFailure("comment_readback_time_mismatch")
        # A separate issue readback binds the object to the exact target and rejects PR-shaped payloads.
        issue = self.github.issue(self.ingress_token)
        if issue.get("id") != self.scope["target_issue"]["id"] or issue.get("number") != self.scope["target_issue"]["number"]:
            raise RunFailure("issue_readback_identity_mismatch")
        if "pull_request" in issue:
            raise RunFailure("issue_readback_is_pull_request")
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

    def recover_pending_actions(self) -> None:
        pending = self.ledger.pending_actions()
        if not pending:
            return
        if len(pending) > 1:
            raise RunFailure("multiple_pending_actions")
        row = pending[0]
        issue = self.github.issue(self.ingress_token)
        state = issue.get("state")
        phase = row["phase"]
        action_id = int(row["action_id"])
        if phase in {"permit_ready", "close_uncertain"}:
            if state == "closed":
                self.ledger.update_action(action_id, phase="close_observed", close_state="closed")
            elif state == "open":
                self._close_and_verify(action_id, row, issue, recovery=True)
            else:
                raise RunFailure("recovery_precondition_unknown")
        elif phase in {"close_patched", "close_observed"}:
            if state != "closed":
                raise RunFailure("recovery_close_state_drift")
        elif phase in {"reopen_uncertain", "reopen_patched"}:
            if state == "open":
                self.ledger.update_action(action_id, phase="compensated", reopen_state="open", finished_at=utc_now())
            elif state == "closed":
                self._reopen_and_verify(action_id, row)
            else:
                raise RunFailure("recovery_reopen_state_unknown")
        row = self.ledger.connection.execute("SELECT * FROM action_ledger WHERE action_id = ?", (action_id,)).fetchone()
        if row is not None and row["phase"] != "compensated":
            self._reopen_and_verify(action_id, row)

    def _close_and_verify(
        self,
        action_id: int,
        row: sqlite3.Row,
        issue: dict[str, Any],
        *,
        recovery: bool = False,
    ) -> None:
        if issue.get("state") != "open":
            raise RunFailure("issue_precondition_not_open")
        close_body = self.scope["api"]["close_body"]
        try:
            response = self.github.patch_issue(self.action_token, close_body)
        except RunFailure:
            self.ledger.update_action(action_id, phase="close_uncertain")
            raise
        self.ledger.update_action(
            action_id,
            phase="close_patched",
            patch_count=int(row["patch_count"]) + 1,
            close_status=200,
            close_state=response.get("state"),
        )
        readback = self.github.issue(self.ingress_token)
        if readback.get("state") != "closed":
            self.ledger.update_action(action_id, phase="close_uncertain")
            raise RunFailure("close_readback_not_closed")
        self.ledger.update_action(action_id, phase="close_observed", close_state="closed")
        latest = self.ledger.connection.execute("SELECT * FROM action_ledger WHERE action_id = ?", (action_id,)).fetchone()
        if latest is None:
            raise RunFailure("action_ledger_missing")
        self._reopen_and_verify(action_id, latest)

    def _reopen_and_verify(self, action_id: int, row: sqlite3.Row) -> None:
        try:
            response = self.github.patch_issue(self.action_token, self.scope["api"]["compensation_body"])
        except RunFailure:
            self.ledger.update_action(action_id, phase="reopen_uncertain")
            raise
        self.ledger.update_action(
            action_id,
            phase="reopen_patched",
            patch_count=int(row["patch_count"]) + 1,
            reopen_status=200,
            reopen_state=response.get("state"),
        )
        readback = self.github.issue(self.ingress_token)
        if readback.get("state") != "open":
            self.ledger.update_action(action_id, phase="reopen_uncertain")
            raise RunFailure("compensation_readback_not_open")
        self.ledger.update_action(
            action_id,
            phase="compensated",
            reopen_state="open",
            finished_at=utc_now(),
        )

    def _classify(self, observation: Observation) -> tuple[str, str, Command]:
        try:
            return self.authority.evaluate(observation)
        except RunFailure as error:
            # Parse again so deterministic authority denials cannot hide a
            # malformed command or leak implementation-specific labels.
            command = parse_command(observation.comment_body, self.scope)
            return "deny", str(error), command

    def process(self) -> None:
        self.verify_apps_and_installations()
        self.load_delivery_log()
        self.recover_pending_actions()
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
                decision, reason, command = self._classify(observation)
                if existing["decision"] != decision or existing["reason"] != reason:
                    raise RunFailure("replay_decision_drift")
                prior_actions = self.ledger.actions_for_guid(guid)
                if occurrence == 0 and prior_actions:
                    self.records.append(
                        self._record(
                            observation,
                            existing["decision"],
                            existing["reason"],
                            int(prior_actions[0]["action_id"]),
                        )
                    )
                    continue
                if occurrence == 0 and existing["decision"] == "allow":
                    precondition = self.github.issue(self.ingress_token)
                    if precondition.get("state") != "open":
                        raise RunFailure("issue_precondition_not_open")
                    action_id = self.ledger.insert_action(
                        {
                            "delivery_guid": guid,
                            "comment_id": observation.comment_id,
                            "desired_state": "closed",
                            "decision": "allow",
                            "reason": existing["reason"],
                            "phase": "permit_ready",
                            "precondition_state": "open",
                            "started_at": utc_now(),
                        }
                    )
                    action_started = time.monotonic()
                    row = self.ledger.connection.execute(
                        "SELECT * FROM action_ledger WHERE action_id = ?", (action_id,)
                    ).fetchone()
                    if row is None:
                        raise RunFailure("action_ledger_missing")
                    self._close_and_verify(action_id, row, precondition)
                    self.ledger.update_action(
                        action_id,
                        latency_ms=int((time.monotonic() - action_started) * 1000),
                    )
                    self.records.append(self._record(observation, "allow", existing["reason"], action_id))
                    continue
                action_id = self.ledger.insert_action(
                    {
                        "delivery_guid": guid,
                        "comment_id": observation.comment_id,
                        "desired_state": "closed",
                        "decision": "replay_noop",
                        "reason": "duplicate_delivery_guid",
                        "phase": "compensated",
                        "started_at": utc_now(),
                    }
                )
                self.records.append(self._record(observation, "replay_noop", "duplicate_delivery_guid", action_id))
                continue
            decision, reason, command = self._classify(observation)
            generation = command.generation
            self.ledger.record_delivery_with_role(
                observation,
                decision,
                reason,
                command.source_role,
                generation,
            )
            if decision != "allow":
                action_id = self.ledger.insert_action(
                    {
                        "delivery_guid": guid,
                        "comment_id": observation.comment_id,
                        "desired_state": "closed",
                        "decision": decision,
                        "reason": reason,
                        "phase": "compensated",
                        "started_at": utc_now(),
                    }
                )
                self.records.append(self._record(observation, decision, reason, action_id))
                continue
            precondition = self.github.issue(self.ingress_token)
            if precondition.get("state") != "open":
                raise RunFailure("issue_precondition_not_open")
            action_id = self.ledger.insert_action(
                {
                    "delivery_guid": guid,
                    "comment_id": observation.comment_id,
                    "desired_state": "closed",
                    "decision": "allow",
                    "reason": reason,
                    "phase": "permit_ready",
                    "precondition_state": "open",
                    "started_at": utc_now(),
                }
            )
            action_started = time.monotonic()
            row = self.ledger.connection.execute(
                "SELECT * FROM action_ledger WHERE action_id = ?", (action_id,)
            ).fetchone()
            if row is None:
                raise RunFailure("action_ledger_missing")
            self._close_and_verify(action_id, row, precondition)
            latency = int((time.monotonic() - action_started) * 1000)
            self.ledger.update_action(action_id, latency_ms=latency)
            self.records.append(self._record(observation, "allow", reason, action_id, latency_ms=latency))

    def _record(
        self,
        observation: Observation,
        decision: str,
        reason: str,
        action_id: int,
        *,
        latency_ms: int | None = None,
    ) -> dict[str, Any]:
        return {
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
            "latency_ms": latency_ms,
        }

    def result(self, status: str, error: str | None = None) -> dict[str, Any]:
        actions = []
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
            "format": "custody.external-validity.github-b-rule-result",
            "schema_version": 1,
            "run_id": self.run_id,
            "treatment": "B_RULE",
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
            "receiver": {
                "signature_reverified_constant_time": True,
                "schema": BODY_SCHEMA,
            },
        }
        if error:
            value["error"] = error
        return value

    def write_result(self, status: str, error: str | None = None) -> None:
        RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULT_PATH.write_text(json.dumps(self.result(status, error), indent=2) + "\n", encoding="utf-8")


def main() -> int:
    runner: Runner | None = None
    try:
        runner = Runner()
        runner.process()
        runner.write_result("COMPLETED")
        return 0
    except RunFailure as error:
        if runner is not None:
            runner.write_result("BLOCKED", str(error))
        else:
            RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
            RESULT_PATH.write_text(
                json.dumps(
                    {
                        "format": "custody.external-validity.github-b-rule-result",
                        "schema_version": 1,
                        "treatment": "B_RULE",
                        "status": "BLOCKED",
                        "error": str(error),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        print(f"status=BLOCKED reason={error}")
        return 2
    finally:
        if runner is not None:
            runner.ledger.close()


if __name__ == "__main__":
    raise SystemExit(main())
