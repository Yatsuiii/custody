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
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from custody.origin import ToolTrust


class ToolSurfaceError(ValueError):
    """A ``tools/list`` result that cannot name each tool exactly once."""


class Denial(str, Enum):
    MISSING = "missing"
    REVISION_MISMATCH = "revision_mismatch"


class ToolCallDenied(PermissionError):
    """Raised before dispatch when an unapproved tool would be invoked."""


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
    def from_tools_list(cls, *, server: str, payload: Mapping[str, object]) -> "ToolSurface":
        """Parse the MCP response shape, ignoring response ordering only.

        JSON object key order and the order of tools in a discovery response are
        transport noise. Arrays inside an individual schema retain their order,
        because a general JSON array does not promise set semantics.
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
            definitions.append(ToolDefinition(server, name, dict(raw)))
        return cls(server, tuple(sorted(definitions, key=lambda tool: tool.runtime_name)))


@dataclass(frozen=True)
class ApprovedTool:
    tool_id: str
    runtime_name: str
    revision: str


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

    def approve(self, *, department: str, surface: ToolSurface) -> None:
        for tool in surface.tools:
            approved = ApprovedTool(tool.tool_id, tool.runtime_name, tool.revision)
            self._approved[(department, tool.tool_id)] = approved

    def admit(self, *, department: str, surface: ToolSurface) -> Admission:
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
                    AdmissionDenial(
                        tool_id, approved.revision, None, Denial.MISSING
                    )
                )
            elif live.revision != approved.revision:
                denied.append(
                    AdmissionDenial(
                        tool_id, approved.revision, live.revision,
                        Denial.REVISION_MISMATCH,
                    )
                )
            else:
                allowed.append(approved)
        return Admission(tuple(allowed), tuple(denied))


def _digest(definition: Mapping[str, object]) -> str:
    canonical = json.dumps(
        definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
