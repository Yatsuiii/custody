"""The ADK-shaped shell around the core.

The core in `custody/` imports no SDK on purpose, so it stays testable without
one and cannot quietly bind to a vendor. But an ADK `Runner` will only accept an
object that *is* a `BaseMemoryService`, so something has to be one. This is that
something, and it holds no logic of its own: it subclasses the port ADK requires
and delegates every decision to `CustodyMemoryService`.

The downstream it wraps is any `BaseMemoryService`. `InMemoryMemoryService`
locally, `VertexAiMemoryBankService` against Memory Bank. Both satisfy the same
two abstract methods, so governing one governs the other and the account changes
nothing about this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from google.adk.events import Event
from google.adk.memory import BaseMemoryService
from google.adk.memory.base_memory_service import SearchMemoryResponse
from google.adk.sessions import Session

from custody.origin import ToolTrust
from custody.service import (
    CustodyMemoryService,
    InMemoryQuarantine,
    QuarantineStore,
    Split,
)


@dataclass
class CustodyMemoryBank(BaseMemoryService):
    """A memory service that governs another one by origin.

    Deliberately thin. Every rule lives in the core; if a reviewer wants to know
    what this system actually does, this is not the file to read.
    """

    downstream: BaseMemoryService
    quarantine: QuarantineStore = field(default_factory=InMemoryQuarantine)
    tools: ToolTrust = field(default_factory=ToolTrust)
    _guard: CustodyMemoryService = field(init=False)

    def __post_init__(self) -> None:
        self._guard = CustodyMemoryService(
            downstream=_SessionRebuilding(self.downstream),
            quarantine=self.quarantine,
            tools=self.tools,
        )

    async def add_session_to_memory(self, session: Session) -> None:
        await self._guard.add_session_to_memory(session)

    async def search_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> SearchMemoryResponse:
        return await self.downstream.search_memory(
            app_name=app_name, user_id=user_id, query=query
        )

    def splits(self) -> list[Split]:
        return self._guard.splits

    def recall_cost(self) -> tuple[int, int]:
        """Events withheld against events seen. The number G4 asks for."""
        return self._guard.recall_cost()


@dataclass
class _SessionRebuilding:
    """Hands the downstream a real `Session`, not a stand-in.

    The core is SDK-free and so passes a structural session carrying only the
    admitted events. A real memory service will reject that, and more subtly a
    pydantic model would silently drop unknown attributes. Rebuilding here keeps
    the core clean and the downstream honest.
    """

    inner: BaseMemoryService

    async def add_session_to_memory(self, session) -> None:
        await self.inner.add_session_to_memory(
            Session(
                id=session.id,
                app_name=session.app_name,
                user_id=session.user_id,
                events=[e for e in session.events if isinstance(e, Event)],
            )
        )

    async def search_memory(self, *, app_name: str, user_id: str, query: str):
        return await self.inner.search_memory(
            app_name=app_name, user_id=user_id, query=query
        )
