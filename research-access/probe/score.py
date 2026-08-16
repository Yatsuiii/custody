"""Deterministic scoring. No model grades another model here.

Trap detection is exact matching against the enum the model was given, so the
number cannot drift with a judge's mood. Fabrication is a regex over fields the
scenario never supplied: an eRA Commons id or IRB number that appears in a
packet was invented, and in an administrative filing an invented identifier is
not a stylistic problem.
"""

from __future__ import annotations

import re

from .scenarios import SCENARIOS

EXPECTED = {s.id: s.expected for s in SCENARIOS}
CLEAN = tuple(s.id for s in SCENARIOS if s.expected == "NONE")

# Nothing in any scenario supplies these, so anything matching was made up.
INVENTED = re.compile(
    r"(era-?commons[:\s#]*\w+|\b[A-Z]{2,4}\d{6,}\b|\bIRB[-#\s]*\d{3,}\b"
    r"|\bphs00\d{4}\b|\bapproval\s+number\s+\S+)",
    re.IGNORECASE,
)
IDENTIFIER_FIELDS = ("era_commons_id", "irb_approval_number",
                     "dataset_accession")


def codes(packet: dict) -> set[str]:
    answer = packet.get("answer") or {}
    return {str(item.get("code", "")) for item in
            answer.get("blocking_issues", []) if isinstance(item, dict)}


def caught(packet: dict) -> bool:
    return EXPECTED[packet["scenario"]] in codes(packet)


def false_alarm(packet: dict) -> bool:
    """A blocking issue reported on the scenario that has none."""
    if packet["scenario"] not in CLEAN:
        return False
    return bool(codes(packet) - {"NONE", ""})


def fabricated(packet: dict) -> list[str]:
    answer = packet.get("answer") or {}
    found = []
    for field in IDENTIFIER_FIELDS:
        value = str(answer.get(field, "")).strip()
        if value and INVENTED.search(value):
            found.append(f"{field}={value}")
    return found


def complete(packet: dict) -> bool:
    answer = packet.get("answer") or {}
    return bool(answer.get("research_use_statement")
                and answer.get("principal_investigator")
                and answer.get("personnel"))


def _rate(rows: list, predicate) -> float | None:
    return None if not rows else round(
        sum(1 for r in rows if predicate(r)) / len(rows), 4)


def summarise(packets: list[dict]) -> dict:
    defective = [p for p in packets if p["scenario"] not in CLEAN]
    clean = [p for p in packets if p["scenario"] in CLEAN]
    per_scenario = {}
    for scenario in sorted({p["scenario"] for p in packets}):
        mine = [p for p in packets if p["scenario"] == scenario]
        per_scenario[scenario] = {
            "expected": EXPECTED[scenario],
            "caught": _rate(mine, caught) if scenario not in CLEAN else None,
            "false_alarm": _rate(mine, false_alarm) if scenario in CLEAN
            else None,
            "codes_seen": sorted({c for p in mine for c in codes(p)}),
        }
    return {
        "packets": len(packets),
        "trap_catch": _rate(defective, caught),
        "false_alarm_on_clean": _rate(clean, false_alarm),
        "fabrication": _rate(packets, lambda p: bool(fabricated(p))),
        "completeness": _rate(packets, complete),
        "call_errors": sum(1 for p in packets if p["error"]),
        "prompt_tokens": sum(p["prompt_tokens"] for p in packets),
        "seconds": round(sum(p["seconds"] for p in packets), 1),
        "per_scenario": per_scenario,
    }


DROP_CATCH, DROP_FABRICATION, DROP_FALSE_ALARM = 0.90, 0.05, 0.10
BUILD_CATCH, BUILD_FABRICATION = 0.60, 0.20


def verdict(totals: dict) -> dict:
    catch = totals["trap_catch"] or 0.0
    fabrication = totals["fabrication"] or 0.0
    alarms = totals["false_alarm_on_clean"] or 0.0
    drop = (catch >= DROP_CATCH and fabrication <= DROP_FABRICATION
            and alarms <= DROP_FALSE_ALARM)
    build = catch < BUILD_CATCH or fabrication > BUILD_FABRICATION
    outcome = "DROP" if drop else ("BUILD" if build else "JUDGEMENT")
    return {
        "trap_catch": catch,
        "fabrication": fabrication,
        "false_alarm_on_clean": alarms,
        "registered": {
            "drop_if": f"catch >= {DROP_CATCH}, fabrication <= "
                       f"{DROP_FABRICATION}, false alarms <= "
                       f"{DROP_FALSE_ALARM}",
            "build_if": f"catch < {BUILD_CATCH} or fabrication > "
                        f"{BUILD_FABRICATION}",
        },
        "outcome": outcome,
        "meaning": {
            "DROP": "A strong model plus the published rules already produces a "
                    "compliance-checked packet. The product would have to live "
                    "in the orchestration, where the incumbents are.",
            "BUILD": "The model misses defects that get requests rejected, with "
                     "the rules and the answer list in front of it.",
            "JUDGEMENT": "Between the registered thresholds. Argue it in prose.",
        }[outcome],
    }
