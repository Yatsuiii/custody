"""Admission control for versioned MCP tool surfaces.

Agent Registry is a catalog, not a live attestation channel. A manually
registered server can change its ``tools/list`` response while the catalog still
describes its former surface. This module owns the one policy that closes that
gap: a department may bind only the exact tool definitions it approved.

The public boundary is deliberately small. Parse a live ``tools/list`` payload,
approve it once, then ask for an admission before binding any tool into an
agent. An admitted surface also yields the ``ToolTrust`` consumed by Custody's
memory gate, so a revision identifier follows any admitted tool output into the
derivation graph without exposing registry details to the origin module.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, Sequence

from custody.origin import ToolTrust


class ToolSurfaceError(ValueError):
    """A ``tools/list`` result that cannot name each tool exactly once."""


class Denial(str, Enum):
    MISSING = "missing"
    REVISION_MISMATCH = "revision_mismatch"
    #: The live surface digests under a different algorithm than the pin was
    #: approved under. This is an operational condition (a tooling change on
    #: Custody's own side), never a security event, so it must never be
    #: reported under the same name as an actual drifted tool surface: an
    #: operator reading REVISION_MISMATCH here would go hunting a compromise
    #: that did not happen.
    ALGORITHM_SUPERSEDED = "algorithm_superseded"
    #: The declared MCP surface matches, but the Cloud Run revision name or
    #: image digest the approval was bound to does not. Distinguishes a
    #: same-schema, different-running-code swap from an actual declared
    #: surface drift (REVISION_MISMATCH) or an unrelated tooling change
    #: (ALGORITHM_SUPERSEDED); only checked when the approval carries a
    #: ``RuntimeBinding`` in the first place.
    RUNTIME_DRIFT = "runtime_drift"
    #: Dispatch-time denials, distinct from the three admission-time reasons
    #: above: these fire inside ``AttestationAuthority.verify``, after a
    #: surface was already admitted, when the specific ``tools/call`` cannot
    #: be bound back to the ``tools/list`` read that authorized it.
    EXPIRED = "expired"
    REPLAYED = "replayed"
    SIGNATURE_INVALID = "signature_invalid"
    DIGEST_MISMATCH = "digest_mismatch"


class ToolCallDenied(PermissionError):
    """Raised before dispatch when an unapproved tool would be invoked."""


class RevisionAlgorithmMismatch(ValueError):
    """A revision-specific revocation was asked to compare across a digest
    algorithm boundary it cannot honestly answer.

    Records exist for the tool, but none of them was computed under the
    algorithm the caller is revoking. Silently returning no descendants
    would look identical to "this revision genuinely has none" and let a
    revision-specific revocation report success while removing nothing.
    """


@dataclass(frozen=True)
class ToolDefinition:
    """One deterministic MCP tool definition from a named server.

    ``runtime_name`` is the function name an ADK event reports. ``tool_id`` is
    server-qualified so two servers exposing ``search`` never share lineage.
    ``revision`` is the digest of its canonical definition, not a vendor's
    mutable version label.
    """

    server: str
    runtime_name: str
    definition: Mapping[str, object]

    @property
    def tool_id(self) -> str:
        return f"{self.server}/{self.runtime_name}"

    @property
    def revision(self) -> str:
        return _digest(self.definition)


@dataclass(frozen=True)
class ToolSurface:
    """A canonical snapshot of a single server's live ``tools/list`` result."""

    server: str
    tools: tuple[ToolDefinition, ...]

    @classmethod
    def from_tools_list(
        cls, *, server: str, payload: Mapping[str, object]
    ) -> "ToolSurface":
        """Parse the MCP response shape, ignoring response ordering only.

        JSON object key order and the order of tools in a discovery response are
        transport noise. Arrays inside an individual schema retain their order,
        because a general JSON array does not promise set semantics.

        ``_meta`` is dropped before a definition is stored, and before it is
        digested. The MCP spec reserves it for out-of-band, per-response
        annotation, not tool identity; R2's dispatch attestation token rides
        in exactly that field, minted fresh on every ``tools/list`` call, so
        including it in the digest would make a tool's revision change on
        every read regardless of whether its declared surface ever did.
        """
        result = payload.get("result", payload)
        if not isinstance(result, Mapping):
            raise ToolSurfaceError("tools/list result must be an object")
        raw_tools = result.get("tools")
        if not isinstance(raw_tools, Sequence) or isinstance(raw_tools, str):
            raise ToolSurfaceError("tools/list result must contain tools")

        definitions: list[ToolDefinition] = []
        names: set[str] = set()
        for raw in raw_tools:
            if not isinstance(raw, Mapping):
                raise ToolSurfaceError("each tool definition must be an object")
            name = raw.get("name")
            if not isinstance(name, str) or not name:
                raise ToolSurfaceError("each tool definition needs a name")
            if name in names:
                raise ToolSurfaceError(f"duplicate tool name: {name}")
            names.add(name)
            identity = {key: value for key, value in raw.items() if key != "_meta"}
            definitions.append(ToolDefinition(server, name, identity))
        return cls(
            server, tuple(sorted(definitions, key=lambda tool: tool.runtime_name))
        )


@dataclass(frozen=True)
class RuntimeBinding:
    """The Cloud Run identity an approval was pinned to, alongside its
    declared MCP surface digest.

    A tool's declared ``tools/list`` schema can stay byte-identical while
    the code actually running behind it changes; the surface digest alone
    cannot see that. Binding the revision name and resolved image digest
    catches exactly that case, at the cost of being infrastructure-specific
    rather than MCP-protocol-general like the rest of this module.
    """

    revision_name: str
    image_digest: str


@dataclass(frozen=True)
class ApprovedTool:
    tool_id: str
    runtime_name: str
    revision: str
    #: ``None`` means this approval was never bound to a runtime identity,
    #: so ``admit`` skips the runtime check entirely for it (opt-in, not a
    #: silently mandatory gate every caller must satisfy).
    runtime_binding: RuntimeBinding | None = None


@dataclass(frozen=True)
class AdmissionDenial:
    tool_id: str
    expected_revision: str
    observed_revision: str | None
    reason: Denial


@dataclass(frozen=True)
class Admission:
    """The immutable binding decision for one department and live surface."""

    allowed: tuple[ApprovedTool, ...] = ()
    denied: tuple[AdmissionDenial, ...] = ()

    def allows(self, runtime_name: str) -> bool:
        return any(tool.runtime_name == runtime_name for tool in self.allowed)

    def require(self, runtime_name: str) -> None:
        """Fail closed before an agent can dispatch the named tool."""
        if not self.allows(runtime_name):
            raise ToolCallDenied(f"tool is not admitted: {runtime_name}")

    def trust(self) -> ToolTrust:
        """Translate one binding into Custody's origin-level trust contract."""
        return ToolTrust(
            trusted=frozenset(tool.runtime_name for tool in self.allowed),
            source_ids={tool.runtime_name: tool.tool_id for tool in self.allowed},
            revisions={tool.runtime_name: tool.revision for tool in self.allowed},
        )


@dataclass
class RevisionCatalog:
    """Approved revision pins, keyed by department and server-qualified tool.

    This is intentionally an in-memory spike implementation. The approved
    state has one owner and one operation, ``approve``. A production pivot must
    add a durable implementation behind this same interface before claiming a
    live Registry integration.
    """

    _approved: dict[tuple[str, str], ApprovedTool] = field(default_factory=dict)

    def approve(
        self,
        *,
        department: str,
        surface: ToolSurface,
        runtime_binding: RuntimeBinding | None = None,
    ) -> None:
        for tool in surface.tools:
            approved = ApprovedTool(
                tool.tool_id, tool.runtime_name, tool.revision, runtime_binding
            )
            self._approved[(department, tool.tool_id)] = approved

    def admit(
        self,
        *,
        department: str,
        surface: ToolSurface,
        observed_runtime: RuntimeBinding | None = None,
    ) -> Admission:
        """Compare a live surface with exactly the department's saved pins."""
        observed = {tool.tool_id: tool for tool in surface.tools}
        allowed: list[ApprovedTool] = []
        denied: list[AdmissionDenial] = []
        for (owner, tool_id), approved in sorted(self._approved.items()):
            if owner != department:
                continue
            live = observed.get(tool_id)
            if live is None:
                denied.append(
                    AdmissionDenial(tool_id, approved.revision, None, Denial.MISSING)
                )
            elif algorithm_of(live.revision) != algorithm_of(approved.revision):
                denied.append(
                    AdmissionDenial(
                        tool_id,
                        approved.revision,
                        live.revision,
                        Denial.ALGORITHM_SUPERSEDED,
                    )
                )
            elif live.revision != approved.revision:
                denied.append(
                    AdmissionDenial(
                        tool_id,
                        approved.revision,
                        live.revision,
                        Denial.REVISION_MISMATCH,
                    )
                )
            elif (
                approved.runtime_binding is not None
                and approved.runtime_binding != observed_runtime
            ):
                denied.append(
                    AdmissionDenial(
                        tool_id,
                        approved.revision,
                        live.revision,
                        Denial.RUNTIME_DRIFT,
                    )
                )
            else:
                allowed.append(approved)
        return Admission(tuple(allowed), tuple(denied))


#: Bumped whenever canonicalization changes. A stored revision carries this
#: tag so a later reader can tell "computed differently" from "changed".
DIGEST_ALGORITHM = "sha256/2"


def _digest(definition: Mapping[str, object]) -> str:
    canonical = json.dumps(
        definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return f"{DIGEST_ALGORITHM}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def algorithm_of(revision: str) -> str:
    """Which algorithm produced this revision string.

    Bare hex predates versioned revisions. It is deliberately reported as
    ``sha256/legacy`` rather than as any real version: revisions written
    before and after the ``_meta`` change are both bare hex and cannot be
    told apart, so neither may be treated as comparable to a current one.
    """
    head, separator, rest = revision.partition(":")
    return head if separator else "sha256/legacy"


def mac(
    secret: bytes,
    *,
    tool_id: str,
    revision: str,
    nonce: str,
    issued_at: float,
    expires_at: float,
) -> str:
    """The one signature both minting and verification compute.

    Shared here rather than duplicated so a verifier can never drift from
    what a minter signed. The secret itself is never carried in a
    ``SurfaceAttestation``; only this function's caller holds it.
    """
    canonical = "|".join((tool_id, revision, nonce, repr(issued_at), repr(expires_at)))
    return hmac.new(secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class SurfaceAttestation:
    """A server-signed claim: 'I returned this digest for this tool, just now.'

    Binds one ``tools/call`` dispatch back to the exact ``tools/list`` read
    that authorized it. Carries no secret, only what a minting server signed;
    a caller cannot forge or alter any field without invalidating the
    signature.
    """

    tool_id: str
    revision: str
    nonce: str
    issued_at: float
    expires_at: float
    signature: str


class NonceLedger(Protocol):
    """Where ``AttestationAuthority`` records which nonces have been spent.

    Structural, not inherited: a durable implementation (Firestore-backed)
    satisfies this by having the two methods, with no import of this module
    needed. Split into a read (``seen``) and a write (``mark``), not one
    atomic "claim" call, so ``verify`` can keep checking the presented
    digest before ever marking a nonce spent — a token that fails digest
    verification must not burn its nonce, or a forged nonce could burn a
    legitimate token before it is ever presented.
    """

    def seen(self, nonce: str) -> bool: ...

    def mark(self, nonce: str) -> None: ...


@dataclass
class InMemoryNonceLedger:
    """The default: process-local, exactly the prior behavior.

    Same single-owned-instance scope R1 and S1 already accept for their own
    ledgers; it does not by itself guarantee replay-safety across more than
    one live server instance or a restart. A durable ``NonceLedger`` closes
    that for deployments that need it.
    """

    _consumed: set[str] = field(default_factory=set)

    def seen(self, nonce: str) -> bool:
        return nonce in self._consumed

    def mark(self, nonce: str) -> None:
        self._consumed.add(nonce)


@dataclass
class AttestationAuthority:
    """Mints and verifies ``SurfaceAttestation`` tokens for one MCP server.

    Server-side only: holds the shared secret and the nonce ledger, so it
    must never be constructed by a client.
    """

    _secret: bytes
    _ttl_seconds: float = 45.0
    _ledger: NonceLedger = field(default_factory=InMemoryNonceLedger)

    def mint(self, *, tool: ApprovedTool) -> SurfaceAttestation:
        nonce = secrets.token_hex(16)
        issued_at = time.time()
        expires_at = issued_at + self._ttl_seconds
        signature = mac(
            self._secret,
            tool_id=tool.tool_id,
            revision=tool.revision,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return SurfaceAttestation(
            tool_id=tool.tool_id,
            revision=tool.revision,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
            signature=signature,
        )

    def verify(self, token: SurfaceAttestation, *, live_revision: str) -> Denial | None:
        """Fail closed: return the reason to deny dispatch, or ``None`` to allow.

        Order matters. A token that fails signature verification proves
        nothing, so its nonce is never marked consumed on that path alone; a
        forged nonce could otherwise be used to burn a legitimate token
        before it is ever presented.

        No algorithm-boundary check is needed here, unlike ``admit`` and
        ``descendants_for_revision``. Minting and verification both run in
        this process against this build's ``_digest``, so ``token.revision``
        and ``live_revision`` are always produced by the same algorithm.
        Across a redeploy that changed it, the prefixed strings simply
        differ and this already falls through to ``Denial.DIGEST_MISMATCH``,
        fail-closed and correct without needing to know why they differ.
        """
        expected = mac(
            self._secret,
            tool_id=token.tool_id,
            revision=token.revision,
            nonce=token.nonce,
            issued_at=token.issued_at,
            expires_at=token.expires_at,
        )
        if not hmac.compare_digest(expected, token.signature):
            return Denial.SIGNATURE_INVALID
        if time.time() >= token.expires_at:
            return Denial.EXPIRED
        if self._ledger.seen(token.nonce):
            return Denial.REPLAYED
        if token.revision != live_revision:
            return Denial.DIGEST_MISMATCH
        self._ledger.mark(token.nonce)
        return None
