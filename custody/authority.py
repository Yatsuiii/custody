"""Stable B7 authority values, without an authority issuer.

This module owns the wire shapes that later B7 slices will verify, persist,
and evaluate.  It deliberately cannot mint authority: source-side signing
belongs to a service that owns the upstream object, while Custody receives
only a :class:`SourceAuthorityEvent` and public verification state.

P0 is representation only.  Importing this module does not make an existing
``CustodyRecord`` authoritative and does not alter admission or action policy.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class AuthorityDataError(ValueError):
    """A B7 value is malformed, ambiguous, or outside the frozen schema."""


class Capability(str, Enum):
    """Closed B7 capability lattice, ordered from least to most authority."""

    NONE = "NONE"
    INFORM = "INFORM"
    ACT = "ACT"

    @property
    def rank(self) -> int:
        return {
            Capability.NONE: 0,
            Capability.INFORM: 1,
            Capability.ACT: 2,
        }[self]

    @classmethod
    def meet(cls, capabilities: Iterable["Capability"]) -> "Capability":
        """Return the all-required-input bound for a non-empty capability set."""

        values = tuple(capabilities)
        if not values:
            raise AuthorityDataError("capability meet requires at least one input")
        if any(not isinstance(value, Capability) for value in values):
            raise AuthorityDataError("capability meet accepts Capability values only")
        return min(values, key=lambda value: value.rank)


class TransformClass(str, Enum):
    ROOT = "ROOT"
    IDENTITY = "IDENTITY"
    REGISTERED = "REGISTERED"
    FREEFORM = "FREEFORM"


class OperationRole(str, Enum):
    ORIGIN = "ORIGIN"
    RELAY = "RELAY"


class AdmissionState(str, Enum):
    COMMITTED = "COMMITTED"
    INCOMPLETE = "INCOMPLETE"
    LEGACY = "LEGACY"


class DependencyKind(str, Enum):
    SOURCE_AUTHORITY = "SOURCE_AUTHORITY"
    TRANSFORM_POLICY = "TRANSFORM_POLICY"


class VerificationReason(str, Enum):
    VERIFIED = "RECEIPT_VERIFIED"
    MISSING_TRUST_ANCHOR = "MISSING_TRUST_ANCHOR"
    MALFORMED_TRUST_ANCHOR = "MALFORMED_TRUST_ANCHOR"
    SIGNATURE_INVALID = "RECEIPT_SIGNATURE_INVALID"
    POLICY_KEY_MISMATCH = "RECEIPT_POLICY_KEY_MISMATCH"
    SCOPE_MISMATCH = "RECEIPT_SCOPE_MISMATCH"
    REVISION_MISMATCH = "RECEIPT_REVISION_MISMATCH"
    UPSTREAM_RECORD_MISMATCH = "UPSTREAM_RECORD_MISMATCH"
    OBJECT_COMMITMENT_MISMATCH = "UPSTREAM_OBJECT_COMMITMENT_MISMATCH"
    ROOT_BINDING_MISMATCH = "UNRELATED_RECEIPT_REPLAY"
    SOURCE_CLAIM_MALFORMED = "SOURCE_CLAIM_MALFORMED"
    MISSING_CURRENT_POLICY = "MISSING_CURRENT_POLICY"
    POLICY_ROLE_MISMATCH = "POLICY_ROLE_MISMATCH"
    STALE_GENERATION = "STALE_AUTHORITY_GENERATION"
    CAP_MISSING = "MISSING_SCOPE_CAPABILITY"
    CAP_EXCEEDED = "GRANTED_CAP_EXCEEDS_POLICY"


_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_ED25519_SIGNATURE_HEX = re.compile(r"[0-9a-f]{128}")
_POLICY_SNAPSHOT_FIELDS = frozenset(
    {"policy_key", "version", "generation", "operation_role", "caps"}
)
_AUTHORITY_RECEIPT_FIELDS = frozenset(
    {
        "receipt_version",
        "receipt_id",
        "issuer_id",
        "issuer_key_id",
        "policy_key",
        "granting_generation",
        "granted_cap",
        "action_scope",
        "source_revision",
        "upstream_record_id",
        "upstream_object_commitment",
        "issuer_signature",
    }
)
_AUTHORITY_DEPENDENCY_FIELDS = frozenset(
    {
        "record_id",
        "kind",
        "policy_key",
        "granting_generation",
        "root_record_id",
        "root_key_digest",
        "action_scope",
        "receipt_id",
    }
)
_SOURCE_AUTHORITY_EVENT_FIELDS = frozenset({"source_object", "receipt"})
_ADMISSION_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "record_id",
        "payload_digest",
        "admission_state",
        "transform_class",
        "direct_parent_ids",
        "support_root_ids",
        "support_root_key_digests",
        "own_policy_key",
        "own_policy_version",
        "own_granting_generation",
        "bound_cap",
        "transform_cap",
        "authority_receipt",
        "source_object_claim",
        "admitted_at",
        "supersedes_record_id",
    }
)


def _plain_json(value: object, *, path: str = "$") -> object:
    """Copy a JSON value while rejecting Python-only or ambiguous values."""

    if value is None or isinstance(value, (str, bool)):
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise AuthorityDataError(f"non-finite number at {path}")
        return value
    if isinstance(value, Mapping):
        copied: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise AuthorityDataError(f"non-string object key at {path}")
            copied[key] = _plain_json(item, path=f"{path}.{key}")
        return copied
    if isinstance(value, (list, tuple)):
        return [
            _plain_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise AuthorityDataError(f"non-JSON value at {path}: {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """Encode the frozen P2 canonical JSON form, including its final newline."""

    plain = _plain_json(value)
    return (
        json.dumps(
            plain,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AuthorityDataError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise AuthorityDataError(f"non-finite JSON number: {value}")


def _load_json_object(payload: str | bytes | bytearray) -> Mapping[str, object]:
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except AuthorityDataError:
        raise
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as error:
        raise AuthorityDataError("invalid JSON") from error
    if not isinstance(value, Mapping):
        raise AuthorityDataError("B7 JSON value must be an object")
    return value


def _exact_fields(
    value: Mapping[str, object], expected: frozenset[str], *, kind: str
) -> None:
    if any(not isinstance(field, str) for field in value):
        raise AuthorityDataError(f"{kind} fields must be strings")
    actual = set(value)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    details: list[str] = []
    if missing:
        details.append(f"missing={missing}")
    if unknown:
        details.append(f"unknown={unknown}")
    raise AuthorityDataError(f"{kind} fields differ: {', '.join(details)}")


def _nonempty_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise AuthorityDataError(f"{field} must be a non-empty string")
    return value


def _optional_string(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, field=field)


def _nonnegative_integer(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise AuthorityDataError(f"{field} must be a non-negative integer")
    return value


def _sha256_hex(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256_HEX.fullmatch(value) is None:
        raise AuthorityDataError(f"{field} must be lowercase SHA-256 hex")
    return value


def _enum_value(enum_type: type[Enum], value: object, *, field: str) -> Enum:
    if not isinstance(value, str):
        raise AuthorityDataError(f"{field} must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise AuthorityDataError(f"unknown {field}: {value}") from error


def _string_array(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise AuthorityDataError(f"{field} must be a JSON array")
    result = tuple(_nonempty_string(item, field=field) for item in value)
    if len(result) != len(set(result)):
        raise AuthorityDataError(f"{field} must not contain duplicates")
    return result


def _validate_string_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise AuthorityDataError(f"{field} must be an immutable tuple")
    result = tuple(_nonempty_string(item, field=field) for item in value)
    if len(result) != len(set(result)):
        raise AuthorityDataError(f"{field} must not contain duplicates")
    return result


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in sorted(value.items())}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _immutable_json_object(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AuthorityDataError(f"{field} must be a JSON object")
    plain = _plain_json(value, path=field)
    assert isinstance(plain, Mapping)
    frozen = _freeze_json(plain)
    assert isinstance(frozen, Mapping)
    return frozen


@dataclass(frozen=True)
class PolicyKey:
    """Exact authority-policy identity; semantic similarity is irrelevant."""

    department: str
    source: str
    operation: str
    revision: str
    action_scope: str

    def __post_init__(self) -> None:
        for field, value in zip(
            ("department", "source", "operation", "revision", "action_scope"),
            self.as_list(),
            strict=True,
        ):
            _nonempty_string(value, field=f"policy_key.{field}")

    @classmethod
    def from_value(cls, value: object) -> "PolicyKey":
        if not isinstance(value, list) or len(value) != 5:
            raise AuthorityDataError("policy_key must be a five-string JSON array")
        fields = tuple(
            _nonempty_string(item, field="policy_key") for item in value
        )
        return cls(*fields)

    def as_list(self) -> list[str]:
        return [
            self.department,
            self.source,
            self.operation,
            self.revision,
            self.action_scope,
        ]

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_list())

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class PolicySnapshot:
    """One immutable generation of the policy attached to a PolicyKey."""

    policy_key: PolicyKey
    version: str
    generation: int
    operation_role: OperationRole
    caps: Mapping[str, Capability]

    def __post_init__(self) -> None:
        if not isinstance(self.policy_key, PolicyKey):
            raise AuthorityDataError("policy_snapshot.policy_key must be a PolicyKey")
        _nonempty_string(self.version, field="policy_snapshot.version")
        _nonnegative_integer(self.generation, field="policy_snapshot.generation")
        if not isinstance(self.operation_role, OperationRole):
            raise AuthorityDataError(
                "policy_snapshot.operation_role must be an OperationRole"
            )
        if not isinstance(self.caps, Mapping) or not self.caps:
            raise AuthorityDataError("policy_snapshot.caps must be a non-empty map")
        normalized: dict[str, Capability] = {}
        for scope, capability in self.caps.items():
            scope = _nonempty_string(scope, field="policy_snapshot.caps scope")
            if not isinstance(capability, Capability):
                raise AuthorityDataError(
                    "policy_snapshot.caps values must be Capability values"
                )
            normalized[scope] = capability
        object.__setattr__(self, "caps", MappingProxyType(dict(sorted(normalized.items()))))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "PolicySnapshot":
        _exact_fields(value, _POLICY_SNAPSHOT_FIELDS, kind="PolicySnapshot")
        raw_caps = value["caps"]
        if not isinstance(raw_caps, Mapping):
            raise AuthorityDataError("policy_snapshot.caps must be an object")
        caps: dict[str, Capability] = {}
        for scope, capability in raw_caps.items():
            scope = _nonempty_string(scope, field="policy_snapshot.caps scope")
            caps[scope] = _enum_value(
                Capability, capability, field="capability"
            )  # type: ignore[assignment]
        return cls(
            policy_key=PolicyKey.from_value(value["policy_key"]),
            version=_nonempty_string(value["version"], field="policy_snapshot.version"),
            generation=_nonnegative_integer(
                value["generation"], field="policy_snapshot.generation"
            ),
            operation_role=_enum_value(
                OperationRole, value["operation_role"], field="operation_role"
            ),  # type: ignore[arg-type]
            caps=caps,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "policy_key": self.policy_key.as_list(),
            "version": self.version,
            "generation": self.generation,
            "operation_role": self.operation_role.value,
            "caps": {scope: cap.value for scope, cap in self.caps.items()},
        }


@dataclass(frozen=True)
class AuthorityReceipt:
    """Exact Gate 1B-R3 P2 receipt wire representation."""

    receipt_version: str
    receipt_id: str
    issuer_id: str
    issuer_key_id: str
    policy_key: PolicyKey
    granting_generation: int
    granted_cap: Capability
    action_scope: str
    source_revision: str
    upstream_record_id: str
    upstream_object_commitment: str
    issuer_signature: str

    def __post_init__(self) -> None:
        if self.receipt_version != "1":
            raise AuthorityDataError("unsupported receipt_version")
        for field in (
            "receipt_id",
            "issuer_id",
            "issuer_key_id",
            "action_scope",
            "source_revision",
            "upstream_record_id",
        ):
            _nonempty_string(getattr(self, field), field=f"receipt.{field}")
        if not isinstance(self.policy_key, PolicyKey):
            raise AuthorityDataError("receipt.policy_key must be a PolicyKey")
        _nonnegative_integer(
            self.granting_generation, field="receipt.granting_generation"
        )
        if not isinstance(self.granted_cap, Capability):
            raise AuthorityDataError("receipt.granted_cap must be a Capability")
        _sha256_hex(
            self.upstream_object_commitment,
            field="receipt.upstream_object_commitment",
        )
        if (
            not isinstance(self.issuer_signature, str)
            or _ED25519_SIGNATURE_HEX.fullmatch(self.issuer_signature) is None
        ):
            raise AuthorityDataError(
                "receipt.issuer_signature must be lowercase 64-byte hex"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "AuthorityReceipt":
        _exact_fields(value, _AUTHORITY_RECEIPT_FIELDS, kind="AuthorityReceipt")
        return cls(
            receipt_version=_nonempty_string(
                value["receipt_version"], field="receipt.receipt_version"
            ),
            receipt_id=_nonempty_string(value["receipt_id"], field="receipt.receipt_id"),
            issuer_id=_nonempty_string(value["issuer_id"], field="receipt.issuer_id"),
            issuer_key_id=_nonempty_string(
                value["issuer_key_id"], field="receipt.issuer_key_id"
            ),
            policy_key=PolicyKey.from_value(value["policy_key"]),
            granting_generation=_nonnegative_integer(
                value["granting_generation"], field="receipt.granting_generation"
            ),
            granted_cap=_enum_value(
                Capability, value["granted_cap"], field="granted_cap"
            ),  # type: ignore[arg-type]
            action_scope=_nonempty_string(
                value["action_scope"], field="receipt.action_scope"
            ),
            source_revision=_nonempty_string(
                value["source_revision"], field="receipt.source_revision"
            ),
            upstream_record_id=_nonempty_string(
                value["upstream_record_id"], field="receipt.upstream_record_id"
            ),
            upstream_object_commitment=_sha256_hex(
                value["upstream_object_commitment"],
                field="receipt.upstream_object_commitment",
            ),
            issuer_signature=_nonempty_string(
                value["issuer_signature"], field="receipt.issuer_signature"
            ),
        )

    @classmethod
    def from_json(cls, payload: str | bytes | bytearray) -> "AuthorityReceipt":
        return cls.from_mapping(_load_json_object(payload))

    def unsigned_dict(self) -> dict[str, object]:
        result = self.as_dict()
        result.pop("issuer_signature")
        return result

    def canonical_bytes(self) -> bytes:
        """Bytes an external source signs and P1 will verify."""

        return canonical_json_bytes(self.unsigned_dict())

    @property
    def binding_digest(self) -> str:
        """Identity of one signed receipt, before its Custody root is assigned."""

        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def as_dict(self) -> dict[str, object]:
        return {
            "receipt_version": self.receipt_version,
            "receipt_id": self.receipt_id,
            "issuer_id": self.issuer_id,
            "issuer_key_id": self.issuer_key_id,
            "policy_key": self.policy_key.as_list(),
            "granting_generation": self.granting_generation,
            "granted_cap": self.granted_cap.value,
            "action_scope": self.action_scope,
            "source_revision": self.source_revision,
            "upstream_record_id": self.upstream_record_id,
            "upstream_object_commitment": self.upstream_object_commitment,
            "issuer_signature": self.issuer_signature,
        }


@dataclass(frozen=True)
class ReceiptRootKey:
    """Exact Gate 1C-R3 selector identity for one authenticated root."""

    issuer_id: str
    receipt_id: str
    upstream_record_id: str
    upstream_object_commitment: str
    policy_key: PolicyKey
    granting_generation: int
    custody_root_record_id: str

    def __post_init__(self) -> None:
        for field in (
            "issuer_id",
            "receipt_id",
            "upstream_record_id",
            "custody_root_record_id",
        ):
            _nonempty_string(getattr(self, field), field=f"root_key.{field}")
        _sha256_hex(
            self.upstream_object_commitment,
            field="root_key.upstream_object_commitment",
        )
        if not isinstance(self.policy_key, PolicyKey):
            raise AuthorityDataError("root_key.policy_key must be a PolicyKey")
        _nonnegative_integer(
            self.granting_generation, field="root_key.granting_generation"
        )

    @classmethod
    def from_receipt(
        cls, receipt: AuthorityReceipt, *, custody_root_record_id: str
    ) -> "ReceiptRootKey":
        if not isinstance(receipt, AuthorityReceipt):
            raise AuthorityDataError("root key requires an AuthorityReceipt")
        return cls(
            issuer_id=receipt.issuer_id,
            receipt_id=receipt.receipt_id,
            upstream_record_id=receipt.upstream_record_id,
            upstream_object_commitment=receipt.upstream_object_commitment,
            policy_key=receipt.policy_key,
            granting_generation=receipt.granting_generation,
            custody_root_record_id=custody_root_record_id,
        )

    @classmethod
    def from_value(cls, value: object) -> "ReceiptRootKey":
        if not isinstance(value, list) or len(value) != 7:
            raise AuthorityDataError("ReceiptRootKey must be a seven-element array")
        return cls(
            issuer_id=_nonempty_string(value[0], field="root_key.issuer_id"),
            receipt_id=_nonempty_string(value[1], field="root_key.receipt_id"),
            upstream_record_id=_nonempty_string(
                value[2], field="root_key.upstream_record_id"
            ),
            upstream_object_commitment=_sha256_hex(
                value[3], field="root_key.upstream_object_commitment"
            ),
            policy_key=PolicyKey.from_value(value[4]),
            granting_generation=_nonnegative_integer(
                value[5], field="root_key.granting_generation"
            ),
            custody_root_record_id=_nonempty_string(
                value[6], field="root_key.custody_root_record_id"
            ),
        )

    def as_list(self) -> list[object]:
        return [
            self.issuer_id,
            self.receipt_id,
            self.upstream_record_id,
            self.upstream_object_commitment,
            self.policy_key.as_list(),
            self.granting_generation,
            self.custody_root_record_id,
        ]

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_list())

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class AuthorityDependency:
    """One immutable source-authority or transform-policy dependency."""

    record_id: str
    kind: DependencyKind
    policy_key: PolicyKey
    granting_generation: int
    root_record_id: str
    root_key_digest: str | None
    action_scope: str
    receipt_id: str | None

    def __post_init__(self) -> None:
        _nonempty_string(self.record_id, field="dependency.record_id")
        if not isinstance(self.kind, DependencyKind):
            raise AuthorityDataError("dependency.kind must be a DependencyKind")
        if not isinstance(self.policy_key, PolicyKey):
            raise AuthorityDataError("dependency.policy_key must be a PolicyKey")
        _nonnegative_integer(
            self.granting_generation, field="dependency.granting_generation"
        )
        _nonempty_string(self.root_record_id, field="dependency.root_record_id")
        _nonempty_string(self.action_scope, field="dependency.action_scope")
        if self.kind is DependencyKind.SOURCE_AUTHORITY:
            _sha256_hex(self.root_key_digest, field="dependency.root_key_digest")
            _nonempty_string(self.receipt_id, field="dependency.receipt_id")
        elif self.root_key_digest is not None or self.receipt_id is not None:
            raise AuthorityDataError(
                "transform dependency cannot carry receipt-root identity"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "AuthorityDependency":
        _exact_fields(value, _AUTHORITY_DEPENDENCY_FIELDS, kind="AuthorityDependency")
        raw_digest = value["root_key_digest"]
        return cls(
            record_id=_nonempty_string(
                value["record_id"], field="dependency.record_id"
            ),
            kind=_enum_value(
                DependencyKind, value["kind"], field="dependency_kind"
            ),  # type: ignore[arg-type]
            policy_key=PolicyKey.from_value(value["policy_key"]),
            granting_generation=_nonnegative_integer(
                value["granting_generation"], field="dependency.granting_generation"
            ),
            root_record_id=_nonempty_string(
                value["root_record_id"], field="dependency.root_record_id"
            ),
            root_key_digest=(
                None
                if raw_digest is None
                else _sha256_hex(raw_digest, field="dependency.root_key_digest")
            ),
            action_scope=_nonempty_string(
                value["action_scope"], field="dependency.action_scope"
            ),
            receipt_id=_optional_string(
                value["receipt_id"], field="dependency.receipt_id"
            ),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "kind": self.kind.value,
            "policy_key": self.policy_key.as_list(),
            "granting_generation": self.granting_generation,
            "root_record_id": self.root_record_id,
            "root_key_digest": self.root_key_digest,
            "action_scope": self.action_scope,
            "receipt_id": self.receipt_id,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())

    @property
    def digest(self) -> str:
        identity = [
            self.record_id,
            self.kind.value,
            self.policy_key.as_list(),
            self.root_record_id,
            self.action_scope,
        ]
        return hashlib.sha256(canonical_json_bytes(identity)).hexdigest()


FORBIDDEN_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        "attacker",
        "attacker_controlled",
        "attack_label",
        "attack_type",
        "adversarial_goal",
        "benign",
        "case_label",
        "expected",
        "expected_action",
        "expected_allow",
        "expected_memory",
        "expected_result",
        "expected_verdict",
        "ground_truth",
        "malicious",
        "scorer",
        "scorer_only",
        "scorer_truth",
        "true_origin",
        "unauthorized_action",
    }
)
_FORBIDDEN_COLLAPSED = frozenset(
    re.sub(r"[^a-z0-9]", "", field.lower()) for field in FORBIDDEN_RUNTIME_FIELDS
)


def _reject_forbidden_runtime_fields(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            collapsed = re.sub(r"[^a-z0-9]", "", key.lower())
            if collapsed in _FORBIDDEN_COLLAPSED:
                raise AuthorityDataError(f"forbidden runtime field at {path}.{key}")
            _reject_forbidden_runtime_fields(item, path=f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            _reject_forbidden_runtime_fields(item, path=f"{path}[{index}]")


@dataclass(frozen=True)
class SourceAuthorityEvent:
    """Provider-owned source object plus unchanged externally issued receipt."""

    source_object: Mapping[str, object]
    receipt: AuthorityReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.receipt, AuthorityReceipt):
            raise AuthorityDataError("source event receipt must be an AuthorityReceipt")
        source_object = _immutable_json_object(
            self.source_object, field="source_event.source_object"
        )
        _reject_forbidden_runtime_fields(source_object)
        object.__setattr__(self, "source_object", source_object)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "SourceAuthorityEvent":
        _exact_fields(value, _SOURCE_AUTHORITY_EVENT_FIELDS, kind="SourceAuthorityEvent")
        raw_receipt = value["receipt"]
        if not isinstance(raw_receipt, Mapping):
            raise AuthorityDataError("source_event.receipt must be an object")
        raw_source = value["source_object"]
        if not isinstance(raw_source, Mapping):
            raise AuthorityDataError("source_event.source_object must be an object")
        return cls(
            source_object=raw_source,
            receipt=AuthorityReceipt.from_mapping(raw_receipt),
        )

    @classmethod
    def from_json(cls, payload: str | bytes | bytearray) -> "SourceAuthorityEvent":
        return cls.from_mapping(_load_json_object(payload))

    @property
    def canonical_source_bytes(self) -> bytes:
        return canonical_json_bytes(_thaw_json(self.source_object))

    @property
    def source_object_commitment(self) -> str:
        return hashlib.sha256(self.canonical_source_bytes).hexdigest()

    def as_dict(self) -> dict[str, object]:
        return {
            "source_object": _thaw_json(self.source_object),
            "receipt": self.receipt.as_dict(),
        }


@dataclass(frozen=True)
class ReceiptVerification:
    """Receipt verification result with no reusable authority token."""

    verified: bool
    reason: VerificationReason
    issuer_id: str | None = None
    receipt_id: str | None = None
    policy_key_digest: str | None = None
    granting_generation: int | None = None
    current_generation: int | None = None
    root_key_digest: str | None = None


class AuthorityVerifier:
    """Verify source-owned P2 evidence against current authoritative state.

    ``required_policy_key`` is route/deployment configuration, not a value
    selected from the untrusted event.  Keeping it mandatory prevents a valid
    payroll receipt, for example, from self-declaring that an export route
    should accept it.
    """

    _SOURCE_FIELDS = (
        "record_id",
        "department",
        "source",
        "operation",
        "revision",
        "action_scope",
    )

    def __init__(
        self,
        *,
        trust_store: "AuthorityTrustStore",
        state: "AuthorityStateReader",
    ) -> None:
        self._trust_store = trust_store
        self._state = state

    def verify(
        self,
        event: SourceAuthorityEvent,
        *,
        custody_root_record_id: str,
        required_policy_key: PolicyKey,
    ) -> ReceiptVerification:
        if not isinstance(event, SourceAuthorityEvent):
            raise AuthorityDataError("verifier requires a SourceAuthorityEvent")
        _nonempty_string(
            custody_root_record_id, field="verification.custody_root_record_id"
        )
        if not isinstance(required_policy_key, PolicyKey):
            raise AuthorityDataError(
                "verification.required_policy_key must be a PolicyKey"
            )

        receipt = event.receipt
        if receipt.policy_key != required_policy_key:
            return self._deny(VerificationReason.POLICY_KEY_MISMATCH, receipt)

        source = self._source_binding(event)
        if source is None:
            return self._deny(VerificationReason.SOURCE_CLAIM_MALFORMED, receipt)
        if receipt.upstream_record_id != source["record_id"]:
            return self._deny(VerificationReason.UPSTREAM_RECORD_MISMATCH, receipt)
        if receipt.upstream_object_commitment != event.source_object_commitment:
            return self._deny(
                VerificationReason.OBJECT_COMMITMENT_MISMATCH, receipt
            )
        if (
            receipt.action_scope != required_policy_key.action_scope
            or source["action_scope"] != required_policy_key.action_scope
        ):
            return self._deny(VerificationReason.SCOPE_MISMATCH, receipt)
        if (
            receipt.source_revision != required_policy_key.revision
            or source["revision"] != required_policy_key.revision
        ):
            return self._deny(VerificationReason.REVISION_MISMATCH, receipt)
        if (
            source["department"] != required_policy_key.department
            or source["source"] != required_policy_key.source
            or source["operation"] != required_policy_key.operation
        ):
            return self._deny(VerificationReason.POLICY_KEY_MISMATCH, receipt)

        public_key_bytes = self._trust_store.public_key_for(
            issuer_id=receipt.issuer_id,
            issuer_key_id=receipt.issuer_key_id,
        )
        if public_key_bytes is None:
            return self._deny(VerificationReason.MISSING_TRUST_ANCHOR, receipt)
        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        except (TypeError, ValueError):
            return self._deny(VerificationReason.MALFORMED_TRUST_ANCHOR, receipt)
        try:
            public_key.verify(
                bytes.fromhex(receipt.issuer_signature), receipt.canonical_bytes()
            )
        except (InvalidSignature, TypeError, ValueError):
            return self._deny(VerificationReason.SIGNATURE_INVALID, receipt)

        bound_root_id = self._state.root_record_id_for_receipt(receipt)
        if (
            bound_root_id is not None
            and bound_root_id != custody_root_record_id
        ):
            return self._deny(
                VerificationReason.ROOT_BINDING_MISMATCH, receipt
            )

        current = self._state.policy(required_policy_key)
        if current is None:
            return self._deny(VerificationReason.MISSING_CURRENT_POLICY, receipt)
        if current.operation_role is not OperationRole.ORIGIN:
            return self._deny(
                VerificationReason.POLICY_ROLE_MISMATCH, receipt, current=current
            )
        if current.generation != receipt.granting_generation:
            return self._deny(
                VerificationReason.STALE_GENERATION, receipt, current=current
            )
        current_cap = current.caps.get(required_policy_key.action_scope)
        if current_cap is None:
            return self._deny(
                VerificationReason.CAP_MISSING, receipt, current=current
            )
        if receipt.granted_cap.rank > current_cap.rank:
            return self._deny(
                VerificationReason.CAP_EXCEEDED, receipt, current=current
            )

        root_key = ReceiptRootKey.from_receipt(
            receipt, custody_root_record_id=custody_root_record_id
        )
        return ReceiptVerification(
            verified=True,
            reason=VerificationReason.VERIFIED,
            issuer_id=receipt.issuer_id,
            receipt_id=receipt.receipt_id,
            policy_key_digest=receipt.policy_key.digest,
            granting_generation=receipt.granting_generation,
            current_generation=current.generation,
            root_key_digest=root_key.digest,
        )

    @classmethod
    def _source_binding(
        cls, event: SourceAuthorityEvent
    ) -> dict[str, str] | None:
        result: dict[str, str] = {}
        for field in cls._SOURCE_FIELDS:
            value = event.source_object.get(field)
            if not isinstance(value, str) or not value:
                return None
            result[field] = value
        return result

    @staticmethod
    def _deny(
        reason: VerificationReason,
        receipt: AuthorityReceipt,
        *,
        current: PolicySnapshot | None = None,
    ) -> ReceiptVerification:
        return ReceiptVerification(
            verified=False,
            reason=reason,
            issuer_id=receipt.issuer_id,
            receipt_id=receipt.receipt_id,
            policy_key_digest=receipt.policy_key.digest,
            granting_generation=receipt.granting_generation,
            current_generation=current.generation if current is not None else None,
        )


@dataclass(frozen=True)
class AdmissionEnvelope:
    """Immutable B7 admission state; current authority is never cached here."""

    schema_version: str
    record_id: str
    payload_digest: str
    admission_state: AdmissionState
    transform_class: TransformClass
    direct_parent_ids: tuple[str, ...]
    support_root_ids: tuple[str, ...]
    support_root_key_digests: tuple[str, ...]
    own_policy_key: PolicyKey
    own_policy_version: str
    own_granting_generation: int
    bound_cap: Capability
    transform_cap: Capability
    authority_receipt: AuthorityReceipt | None
    source_object_claim: Mapping[str, object] | None
    admitted_at: str | None
    supersedes_record_id: str | None

    def __post_init__(self) -> None:
        if self.schema_version != "b7/p2-v1":
            raise AuthorityDataError("unsupported admission envelope schema")
        _nonempty_string(self.record_id, field="envelope.record_id")
        _sha256_hex(self.payload_digest, field="envelope.payload_digest")
        if not isinstance(self.admission_state, AdmissionState):
            raise AuthorityDataError("envelope.admission_state must be an AdmissionState")
        if not isinstance(self.transform_class, TransformClass):
            raise AuthorityDataError("envelope.transform_class must be a TransformClass")
        direct_parents = _validate_string_tuple(
            self.direct_parent_ids, field="envelope.direct_parent_ids"
        )
        support_roots = _validate_string_tuple(
            self.support_root_ids, field="envelope.support_root_ids"
        )
        if not isinstance(self.support_root_key_digests, tuple):
            raise AuthorityDataError(
                "envelope.support_root_key_digests must be an immutable tuple"
            )
        support_digests = tuple(
            _sha256_hex(item, field="envelope.support_root_key_digests")
            for item in self.support_root_key_digests
        )
        if len(support_digests) != len(set(support_digests)):
            raise AuthorityDataError(
                "envelope.support_root_key_digests must not contain duplicates"
            )
        if len(support_roots) != len(support_digests):
            raise AuthorityDataError(
                "envelope support root IDs and root-key digests must correspond"
            )
        if not isinstance(self.own_policy_key, PolicyKey):
            raise AuthorityDataError("envelope.own_policy_key must be a PolicyKey")
        _nonempty_string(
            self.own_policy_version, field="envelope.own_policy_version"
        )
        _nonnegative_integer(
            self.own_granting_generation,
            field="envelope.own_granting_generation",
        )
        if not isinstance(self.bound_cap, Capability):
            raise AuthorityDataError("envelope.bound_cap must be a Capability")
        if not isinstance(self.transform_cap, Capability):
            raise AuthorityDataError("envelope.transform_cap must be a Capability")
        _optional_string(self.admitted_at, field="envelope.admitted_at")
        _optional_string(
            self.supersedes_record_id, field="envelope.supersedes_record_id"
        )

        claim: Mapping[str, object] | None = None
        if self.source_object_claim is not None:
            claim = _immutable_json_object(
                self.source_object_claim, field="envelope.source_object_claim"
            )
            _reject_forbidden_runtime_fields(claim)
            object.__setattr__(self, "source_object_claim", claim)

        if self.transform_class is TransformClass.ROOT:
            if self.authority_receipt is None or claim is None:
                raise AuthorityDataError("ROOT envelope requires receipt and source claim")
            if direct_parents:
                raise AuthorityDataError("ROOT envelope cannot have direct parents")
            expected_root = ReceiptRootKey.from_receipt(
                self.authority_receipt, custody_root_record_id=self.record_id
            )
            if support_roots != (self.record_id,) or support_digests != (
                expected_root.digest,
            ):
                raise AuthorityDataError(
                    "ROOT envelope support must identify its exact receipt root"
                )
        else:
            if self.authority_receipt is not None or claim is not None:
                raise AuthorityDataError(
                    "derived envelope cannot carry a fresh source receipt or claim"
                )
        if self.transform_class is TransformClass.IDENTITY and len(direct_parents) != 1:
            raise AuthorityDataError("IDENTITY envelope requires exactly one parent")
        if self.transform_class is TransformClass.REGISTERED and not direct_parents:
            raise AuthorityDataError("REGISTERED envelope requires at least one parent")
        if (
            self.transform_class is TransformClass.FREEFORM
            and self.transform_cap.rank > Capability.INFORM.rank
        ):
            raise AuthorityDataError("FREEFORM transform_cap cannot exceed INFORM")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "AdmissionEnvelope":
        _exact_fields(value, _ADMISSION_ENVELOPE_FIELDS, kind="AdmissionEnvelope")
        raw_receipt = value["authority_receipt"]
        if raw_receipt is not None and not isinstance(raw_receipt, Mapping):
            raise AuthorityDataError("envelope.authority_receipt must be an object or null")
        raw_claim = value["source_object_claim"]
        if raw_claim is not None and not isinstance(raw_claim, Mapping):
            raise AuthorityDataError("envelope.source_object_claim must be an object or null")
        return cls(
            schema_version=_nonempty_string(
                value["schema_version"], field="envelope.schema_version"
            ),
            record_id=_nonempty_string(value["record_id"], field="envelope.record_id"),
            payload_digest=_sha256_hex(
                value["payload_digest"], field="envelope.payload_digest"
            ),
            admission_state=_enum_value(
                AdmissionState, value["admission_state"], field="admission_state"
            ),  # type: ignore[arg-type]
            transform_class=_enum_value(
                TransformClass, value["transform_class"], field="transform_class"
            ),  # type: ignore[arg-type]
            direct_parent_ids=_string_array(
                value["direct_parent_ids"], field="envelope.direct_parent_ids"
            ),
            support_root_ids=_string_array(
                value["support_root_ids"], field="envelope.support_root_ids"
            ),
            support_root_key_digests=_string_array(
                value["support_root_key_digests"],
                field="envelope.support_root_key_digests",
            ),
            own_policy_key=PolicyKey.from_value(value["own_policy_key"]),
            own_policy_version=_nonempty_string(
                value["own_policy_version"], field="envelope.own_policy_version"
            ),
            own_granting_generation=_nonnegative_integer(
                value["own_granting_generation"],
                field="envelope.own_granting_generation",
            ),
            bound_cap=_enum_value(
                Capability, value["bound_cap"], field="bound_cap"
            ),  # type: ignore[arg-type]
            transform_cap=_enum_value(
                Capability, value["transform_cap"], field="transform_cap"
            ),  # type: ignore[arg-type]
            authority_receipt=(
                None
                if raw_receipt is None
                else AuthorityReceipt.from_mapping(raw_receipt)
            ),
            source_object_claim=raw_claim,
            admitted_at=_optional_string(
                value["admitted_at"], field="envelope.admitted_at"
            ),
            supersedes_record_id=_optional_string(
                value["supersedes_record_id"],
                field="envelope.supersedes_record_id",
            ),
        )

    @classmethod
    def from_json(cls, payload: str | bytes | bytearray) -> "AdmissionEnvelope":
        return cls.from_mapping(_load_json_object(payload))

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "payload_digest": self.payload_digest,
            "admission_state": self.admission_state.value,
            "transform_class": self.transform_class.value,
            "direct_parent_ids": list(self.direct_parent_ids),
            "support_root_ids": list(self.support_root_ids),
            "support_root_key_digests": list(self.support_root_key_digests),
            "own_policy_key": self.own_policy_key.as_list(),
            "own_policy_version": self.own_policy_version,
            "own_granting_generation": self.own_granting_generation,
            "bound_cap": self.bound_cap.value,
            "transform_cap": self.transform_cap.value,
            "authority_receipt": (
                None
                if self.authority_receipt is None
                else self.authority_receipt.as_dict()
            ),
            "source_object_claim": (
                None
                if self.source_object_claim is None
                else _thaw_json(self.source_object_claim)
            ),
            "admitted_at": self.admitted_at,
            "supersedes_record_id": self.supersedes_record_id,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())


class AuthorityTrustStore(Protocol):
    """Read-only public-key boundary consumed by the future P1 verifier."""

    def public_key_for(self, *, issuer_id: str, issuer_key_id: str) -> bytes | None: ...


class AuthorityStateReader(Protocol):
    """Authoritative current-state reads required by later B7 slices."""

    def policy(self, key: PolicyKey) -> PolicySnapshot | None: ...

    def envelope(self, record_id: str) -> AdmissionEnvelope | None: ...

    def dependencies(self, record_id: str) -> tuple[AuthorityDependency, ...]: ...

    def is_root_revoked(self, root_key_digest: str) -> bool: ...

    def root_record_id_for_receipt(
        self, receipt: AuthorityReceipt
    ) -> str | None: ...


__all__ = [
    "AdmissionEnvelope",
    "AdmissionState",
    "AuthorityDataError",
    "AuthorityDependency",
    "AuthorityReceipt",
    "AuthorityStateReader",
    "AuthorityTrustStore",
    "AuthorityVerifier",
    "Capability",
    "DependencyKind",
    "FORBIDDEN_RUNTIME_FIELDS",
    "OperationRole",
    "PolicyKey",
    "PolicySnapshot",
    "ReceiptRootKey",
    "ReceiptVerification",
    "SourceAuthorityEvent",
    "TransformClass",
    "VerificationReason",
    "canonical_json_bytes",
]
