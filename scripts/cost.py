"""What a compromised tool costs you, with the derivation graph and without.

This is the utility argument, measured rather than asserted, because "governance
layer" is not a reason anyone buys anything.

The scenario is the one that actually happens: a tool your fleet trusted turns
out to be compromised, and you have to decide what in memory is now suspect.
Without a derivation graph that question **cannot be answered**, because nothing
records which memories descended from which tool. So the honest alternatives are
both bad:

  purge by user   every user whose sessions ever touched the tool loses all
                  their accumulated memory, including everything unrelated
  purge by app    the blunt option, everyone loses everything
  do nothing      the poisoned lineage stays and keeps being retrieved

Custody makes a fourth option exist: remove exactly the descendants.

The absolute percentages below depend on the fixture, and are honest about it.
What does not depend on the fixture is the granularity: without provenance the
smallest unit you can safely purge is a user, and with it the unit is a record.

    make cost
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.graph import CustodyGraph  # noqa: E402
from custody.origin import ToolTrust, take_custody  # noqa: E402

from scripts.demo import Content, Event, Part, Response  # noqa: E402

DEPARTMENTS = ("sales", "support", "finance", "engineering", "procurement")
TOOLS = (
    "crm_lookup",
    "ticket_search",
    "invoice_api",
    "repo_index",
    "vendor_portal",
    "calendar",
    "docs_search",
    "expense_api",
)
COMPROMISED = "vendor_portal"
SESSIONS_PER_DEPARTMENT = 40


@dataclass(frozen=True)
class Fleet:
    """A fleet's worth of memory, and who owns each record."""

    graph: CustodyGraph
    owner: dict[str, str]
    users_touching: frozenset[str]

    def total(self) -> int:
        return len(self.graph)


def build(seed: int = 7, reach: int = len(DEPARTMENTS)) -> Fleet:
    """Five departments, eight tools, a working week of sessions each.

    Every tool is vouched for, because the case being measured is a tool the
    fleet **trusted**. A tool nobody trusted would never have reached memory,
    which is the write-side control doing its job and not what this measures.
    """
    rng = random.Random(seed)
    trust = ToolTrust(frozenset(TOOLS))
    graph, owner = CustodyGraph(), {}
    touching: set[str] = set()
    #: Departments allowed to reach the compromised tool. A tool used by every
    #: department flatters the comparison, because a per-user purge then takes
    #: out the whole fleet; a rarely used one is the hard case.
    reaches = set(DEPARTMENTS[:reach])
    others = [t for t in TOOLS if t != COMPROMISED]

    for department in DEPARTMENTS:
        for index in range(SESSIONS_PER_DEPARTMENT):
            invocation = f"{department}-{index}"
            tool = rng.choice(TOOLS if department in reaches else others)
            events = [
                Event(
                    "user",
                    invocation,
                    Content([Part(text=f"{department} question {index}")]),
                ),
                Event(
                    "assistant",
                    invocation,
                    Content([Part(function_response=Response(tool, f"{tool} result"))]),
                ),
                Event(
                    "assistant",
                    invocation,
                    Content([Part(text=f"answer from {tool} for {department}")]),
                ),
            ]
            for admitted in take_custody(events, trust).admitted:
                graph.add(admitted.record)
                owner[admitted.record.id] = department
            if tool == COMPROMISED:
                touching.add(department)

    return Fleet(graph=graph, owner=owner, users_touching=frozenset(touching))


def measure(reach: int) -> tuple[int, int, int, int]:
    fleet = build(reach=reach)
    total = fleet.total()
    descendants = len(set(fleet.graph.descendants(COMPROMISED)))
    by_user = len(
        [rid for rid, dept in fleet.owner.items() if dept in fleet.users_touching]
    )
    return total, by_user, descendants, len(fleet.users_touching)


def main() -> int:
    fleet = build()
    total = fleet.total()
    descendants = set(fleet.graph.descendants(COMPROMISED))

    # Without provenance you cannot name the descendants, so the smallest safe
    # unit is every record belonging to a department that ever used the tool.
    by_user = {
        record_id
        for record_id, department in fleet.owner.items()
        if department in fleet.users_touching
    }

    print(
        f"\n  {len(DEPARTMENTS)} departments, {len(TOOLS)} tools, "
        f"{SESSIONS_PER_DEPARTMENT} sessions each."
    )
    print(f"  {total} memory records. {COMPROMISED!r} is found compromised.\n")

    rows = [
        ("purge the whole app", total),
        ("purge every department that used it", len(by_user)),
        ("remove exactly the descendants", len(descendants)),
    ]
    print("  response                                 destroyed   survives")
    print("  " + "-" * 60)
    for label, destroyed in rows:
        survives = total - destroyed
        print(
            f"  {label:<38} {destroyed:>9}   {survives:>8}"
            f"  ({100 * survives / total:.0f}%)"
        )

    saved = len(by_user) - len(descendants)
    print(
        f"\n  Custody preserves {saved} records the blunt response destroys, "
        f"{100 * saved / total:.0f}% of the fleet's memory."
    )
    print(
        f"  {len(fleet.users_touching)} of {len(DEPARTMENTS)} departments "
        f"touched the tool, so a per-user purge takes out "
        f"{100 * len(by_user) / total:.0f}% to remove "
        f"{100 * len(descendants) / total:.0f}%."
    )

    print("\n  Sensitivity, because the row above is the flattering case.")
    print("  How many departments can reach the compromised tool changes it:\n")
    print(
        "  departments reached   purge-by-user destroys   Custody destroys   Custody saves"
    )
    print("  " + "-" * 78)
    for reach in range(1, len(DEPARTMENTS) + 1):
        total_r, by_user_r, desc_r, touched = measure(reach)
        print(
            f"  {touched:>19}   {100 * by_user_r / total_r:>21.0f}%"
            f"   {100 * desc_r / total_r:>15.0f}%   {100 * (by_user_r - desc_r) / total_r:>12.0f}%"
        )
    print(
        "\n  Even at one department the blunt response destroys 20% of fleet\n"
        "  memory to remove a few percent. The advantage grows with how widely\n"
        "  the tool was used, which is also when a compromise matters most.\n"
    )

    print(
        "  The percentages move with the fixture. What does not is the\n"
        "  granularity: with no derivation recorded the smallest unit you can\n"
        "  safely purge is a user, and with it the unit is a record. That is\n"
        "  the difference between losing a department's working memory and\n"
        "  losing the poisoned lineage.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
