"""Action-compliance bundle extraction, v2.

v1 (`app/ingest.py::extract_bundle_decisions`) is frozen and untouched by
this module. v1's seven-task holdout run produced 7/7
`NO_GOVERNING_DECISION`. `ACTION_COMPLIANCE_EXTRACTION_FAILURE_AUDIT.md`
traces the generic root cause to the frozen resolver
(`app/authority.py::resolve_authority_with_proof`) requiring **exact Python
string membership** between one `authority_scope` string and each
`Decision.related_components` list — while v1's prompt asked for
`requested_scope` and per-decision `scopes` as two independently-phrased
free-text fields with no instruction that they must agree. Two independent
LLM paraphrases of the same subsystem are unlikely to ever be byte-identical.

v2 fixes exactly that contract, and nothing else in the pipeline:

1. Prompt-level fix: the model must first name a small set of canonical
   scope slugs, then reuse only those exact slugs as both `requested_scope`
   and every applicable decision's `scopes` entries.
2. Deterministic-normalization fix: `requested_scope` and every `scopes`
   entry from the same extraction response are passed through the same
   whitespace/case canonicalization before being used for the (frozen,
   exact-match) resolver call — orthogonal to whether the model followed
   the prompt instruction perfectly.
3. Lifecycle-language fix: explicit guidance for the deprecation-then-
   removal pattern (treat the deprecated approach as SUPERSEDED with an
   explicit SUPERSEDES edge, not as two independent IMPLEMENTED records),
   since a dropped/misclassified node silently orphans any relationship
   edge that would have pointed at it.

The resolver (`app/authority.py`), the frozen v1 extractor
(`app/ingest.py`), the bundle transport (`app/bundle_source.py`), and the
context assembler (`app/action_compliance_context.py`) are not imported for
mutation and are not modified by this module — v2 only produces
`list[Decision]` the same way v1 does, for the same frozen
`resolve_authority_with_proof` to consume unchanged.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vertex  # noqa: E402

from bundle_source import BundleArtifact, SourceBundle  # noqa: E402
from ingest import _as_str_list, _extract_json, _valid_index, _verify_quote  # noqa: E402
from models import Decision, DecisionStatus, Evidence, RelationshipType  # noqa: E402

_BUNDLE_EXTRACTION_INSTRUCTIONS_V2 = """Extract engineering decisions from the raw source artifacts below.
Use only the prompt and artifact text. Do not use filenames as authority
labels and do not infer facts that are not explicitly supported by the text.

SCOPE CONTRACT (read this before writing any output): a decision only
matters to the requested change if its scope slug is IDENTICAL, character
for character, to the requested scope slug. Before writing the JSON object,
privately identify the distinct organizational-decision subsystems/topics
discussed across the requested change and all artifacts, and invent exactly
one short canonical scope slug per subsystem: lowercase, hyphen-separated,
2-6 words (e.g. "gangscheduling-quorum-extension-point"). Then use ONLY
slugs from that same set everywhere in your JSON output: `requested_scope`
must be exactly one canonical slug naming the subsystem the requested
change is actually about (never a restated sentence, never a paraphrase of
the prompt), and every decision's `scopes` entries must reuse the identical
slug string for any subsystem that decision's own source evidence supports
-- do not phrase the same subsystem two different ways in the same
response.

LIFECYCLE LANGUAGE: if one artifact (or an earlier part of one artifact)
describes an approach being deprecated, reverted, or explicitly replaced,
and another artifact (or a later part of the same one) describes what
replaced it, represent the deprecated approach as SUPERSEDED (not as an
independent IMPLEMENTED record) and add an explicit SUPERSEDES edge from
the replacement decision to the deprecated one -- only when the text
actually states the replacement relationship, never inferred from
proximity alone. The same pattern applies to REVERTS: a revert's target is
the specific decision it reverts, not a same-status sibling.

Return ONLY one JSON object with this shape:
{
  "requested_scope": "the single canonical scope slug the requested change is about, or null",
  "decisions": [
    {
      "artifact_id": "artifact_NNN",
      "subject": "one-line decision subject",
      "current_status": "PROPOSED|ACCEPTED|IMPLEMENTED|REVERTED|SUPERSEDED|REAFFIRMED",
      "role": "policy|implementation|unknown",
      "scopes": ["canonical scope slug(s) from your own slug set that this decision's evidence supports"],
      "chosen_approach": "chosen approach or null",
      "rejected_alternatives": ["only alternatives explicitly rejected"],
      "rationale": "short explanation or null",
      "constraints": ["only explicit constraints"],
      "partial_acceptance": false,
      "related_decisions": [
        {"target_index": 0, "relationship": "IMPLEMENTS|SUPERSEDES|REVERTS|RECONSIDERS|REAFFIRMS|DEPENDS_ON|RELATED_TO"}
      ],
      "evidence_quotes": [
        {"artifact_id": "artifact_NNN", "quote": "verbatim source excerpt"}
      ]
    }
  ],
  "uncertainty": ["facts the artifacts do not establish, including any artifact whose lifecycle status could not be determined confidently enough to include as a decision"]
}

Status, scope, role, relationships, and partial acceptance must be reported
only when the raw artifacts support them. If a field cannot be established,
use null, an empty list, or unknown. Never use outside knowledge.

Requested change:
"""

_STATUS_BY_VALUE = {status.value: status for status in DecisionStatus}
_RELATIONSHIP_BY_VALUE = {relationship.value: relationship for relationship in RelationshipType}

_SLUG_COLLAPSE_RE = re.compile(r"[^a-z0-9]+")


def normalize_scope(text: str) -> str:
    """Canonicalize a scope string deterministically: lowercase, strip,
    collapse any run of non-alphanumeric characters (including whitespace,
    punctuation, and case-driven token boundaries) to a single hyphen.

    Applied identically to `requested_scope` and every decision's `scopes`
    entries from the same extraction response, so the frozen resolver's
    exact-string-membership match is robust to formatting noise (case,
    double spaces, trailing punctuation) even when the model's own
    canonical-slug instruction is followed imperfectly. This does not
    invent, merge, or repair semantically different scopes -- it only
    removes formatting variance within one already-consistent slug.
    """
    collapsed = _SLUG_COLLAPSE_RE.sub("-", text.strip().lower())
    return collapsed.strip("-")


@dataclass(frozen=True)
class BundleExtractionResultV2:
    """Same shape as v1's `BundleExtractionResult`, kept as an independent
    type (not reused from `ingest.py`) so v1 and v2 outputs can never be
    silently interchanged by a caller."""

    decisions: tuple[Decision, ...]
    records: tuple[dict, ...]
    requested_scope: str | None
    uncertainty: tuple[str, ...]
    failures: tuple[str, ...]
    raw_response: str


def _bundle_prompt(source: SourceBundle) -> str:
    parts = [_BUNDLE_EXTRACTION_INSTRUCTIONS_V2, source.requested_change()]
    parts.append("\nRaw source artifacts:\n")
    for artifact in source.list_artifacts():
        parts.append(
            "\n--- " + artifact.source_id + " ---\n"
            f"Source type: {artifact.source_type}\n"
            f"Source URL: {artifact.source_url or '(none extracted)'}\n"
            f"Source title: {artifact.title or '(none extracted)'}\n"
            f"Source date: {artifact.timestamp or '(none extracted)'}\n\n"
            + artifact.content
        )
    return "".join(parts)


def _artifact_by_id(artifacts: tuple[BundleArtifact, ...]) -> dict[str, BundleArtifact]:
    return {artifact.source_id: artifact for artifact in artifacts}


def _parse_relationships(
    raw: dict, ordinal: int, raw_records: list, artifact_map: dict[str, BundleArtifact],
    failures: list[str],
) -> list[tuple[str, RelationshipType]]:
    relationships: list[tuple[str, RelationshipType]] = []
    raw_relationships = raw.get("related_decisions", [])
    if not isinstance(raw_relationships, list):
        failures.append(f"decision[{ordinal}] relationships were not a list")
        return relationships
    for relationship in raw_relationships:
        if not isinstance(relationship, dict):
            failures.append(f"decision[{ordinal}] had a malformed relationship")
            continue
        target_index = _valid_index(relationship.get("target_index"), len(raw_records))
        relation = _RELATIONSHIP_BY_VALUE.get(relationship.get("relationship"))
        if target_index is None or relation is None:
            failures.append(f"decision[{ordinal}] had an unsupported relationship")
            continue
        target = raw_records[target_index]
        target_artifact = target.get("artifact_id") if isinstance(target, dict) else None
        if not isinstance(target_artifact, str) or target_artifact not in artifact_map:
            failures.append(f"decision[{ordinal}] relationship target was invalid")
            continue
        target_id = f"bundle-{target_artifact}-decision-{target_index}"
        relationships.append((target_id, relation))
    return relationships


def _parse_evidence(
    raw: dict, ordinal: int, artifact_map: dict[str, BundleArtifact], failures: list[str],
) -> list[Evidence]:
    evidence: list[Evidence] = []
    raw_quotes = raw.get("evidence_quotes", [])
    if not isinstance(raw_quotes, list):
        failures.append(f"decision[{ordinal}] evidence_quotes were not a list")
        return evidence
    for quote_record in raw_quotes:
        if not isinstance(quote_record, dict):
            continue
        quote_artifact = artifact_map.get(quote_record.get("artifact_id"))
        quote = quote_record.get("quote")
        if quote_artifact is None or not isinstance(quote, str) or not _verify_quote(quote, quote_artifact.content):
            failures.append(f"decision[{ordinal}] contained an unverifiable evidence quote")
            continue
        evidence.append(Evidence(
            type=quote_artifact.source_type,
            url=quote_artifact.source_url or f"bundle:{quote_artifact.source_id}",
            quote=quote,
        ))
    return evidence


def _parse_decision_record(
    raw: dict, ordinal: int, raw_records: list, artifact_map: dict[str, BundleArtifact],
    failures: list[str],
) -> tuple[Decision, dict] | None:
    """Returns (Decision, diagnostic record) for one raw model decision, or
    None (with a reason appended to `failures`) if it can't be trusted."""
    artifact_id = raw.get("artifact_id")
    if not isinstance(artifact_id, str) or artifact_id not in artifact_map:
        failures.append(f"decision[{ordinal}] referenced an unknown artifact")
        return None
    status = _STATUS_BY_VALUE.get(raw.get("current_status"))
    if status is None:
        failures.append(f"decision[{ordinal}] had no supported explicit status")
        return None
    subject = raw.get("subject")
    if not isinstance(subject, str) or not subject.strip():
        failures.append(f"decision[{ordinal}] had no subject")
        return None

    scopes = [normalize_scope(s) for s in _as_str_list(raw.get("scopes")) if s.strip()]
    relationships = _parse_relationships(raw, ordinal, raw_records, artifact_map, failures)
    evidence = _parse_evidence(raw, ordinal, artifact_map, failures)

    decision = Decision(
        id=f"bundle-{artifact_id}-decision-{ordinal}",
        subject=subject.strip(),
        current_status=status,
        context=raw.get("context") if isinstance(raw.get("context"), str) else None,
        chosen_approach=(raw.get("chosen_approach") if isinstance(raw.get("chosen_approach"), str) else None),
        rejected_alternatives=_as_str_list(raw.get("rejected_alternatives")),
        rationale=(raw.get("rationale") if isinstance(raw.get("rationale"), str) else None),
        constraints=_as_str_list(raw.get("constraints")),
        introduced_at=artifact_map[artifact_id].timestamp,
        evidence=evidence,
        related_components=scopes,
        related_decisions=relationships,
        partial_acceptance=raw.get("partial_acceptance") is True,
    )
    record = {
        "id": decision.id,
        "source_id": artifact_id,
        "status": status.value,
        "role": raw.get("role") if raw.get("role") in {"policy", "implementation", "unknown"} else "unknown",
        "scope": scopes,
        "related_decisions": [
            {"target": target, "relationship": relation.value}
            for target, relation in relationships
        ],
        "evidence": [
            {"url": evidence_item.url, "quote": evidence_item.quote}
            for evidence_item in evidence
        ],
    }
    return decision, record


def extract_bundle_decisions_v2(
    source: SourceBundle,
    generator: Callable[[str], str] | None = None,
) -> BundleExtractionResultV2:
    """v2 of `ingest.extract_bundle_decisions`: same transport, same quote
    discipline, same frozen `DecisionStatus`/`RelationshipType` enums, same
    "never fabricate" rule. The only behavioral difference is the scope
    contract described in the module docstring."""
    artifacts = source.list_artifacts()
    response = (generator or vertex.generate)(_bundle_prompt(source))
    parsed = _extract_json(response) or {}
    failures: list[str] = []
    decisions: list[Decision] = []
    records: list[dict] = []
    raw_records = parsed.get("decisions", [])
    if not isinstance(raw_records, list):
        raw_records = []
        failures.append("model decisions field was not a list")

    artifact_map = _artifact_by_id(artifacts)
    for ordinal, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            failures.append(f"decision[{ordinal}] was not an object")
            continue
        parsed_record = _parse_decision_record(raw, ordinal, raw_records, artifact_map, failures)
        if parsed_record is None:
            continue
        decision, record = parsed_record
        decisions.append(decision)
        records.append(record)

    requested_scope = parsed.get("requested_scope")
    if not isinstance(requested_scope, str) or not requested_scope.strip():
        requested_scope = None
        failures.append("model did not establish a requested scope")
    else:
        requested_scope = normalize_scope(requested_scope)
        if not any(requested_scope in decision.related_components for decision in decisions):
            failures.append(
                f"requested scope {requested_scope!r} matched no extracted decision's scopes "
                "after normalization"
            )
    uncertainty = tuple(item for item in parsed.get("uncertainty", []) if isinstance(item, str))
    return BundleExtractionResultV2(
        decisions=tuple(decisions),
        records=tuple(records),
        requested_scope=requested_scope,
        uncertainty=uncertainty,
        failures=tuple(failures),
        raw_response=response,
    )
