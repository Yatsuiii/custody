"""Real GitHub/KEP ingestion — BUILD_SCOPE.md §8, §9.

Generalizes the falsifier's two validated channels (revert-PR pairs,
KEP-style "Alternatives Considered" sections — the only channels that
survived the original substrate audit; generic issue-tracker mining is
deliberately still out of scope) from "3-4 hardcoded repos" to any repo,
and swaps the falsifier's regex-based `pick_quote()` for Gemini structured
extraction, per §9.

The one rule that matters more than the mechanism: extraction must never
invent a quote. Gemini is asked to return a verbatim excerpt, but its claim
of verbatim-ness isn't trusted — `_verify_quote()` checks the returned
quote is a real substring of the fetched source (after whitespace
normalization) before accepting it. If it isn't, the field is nulled to
"insufficient evidence" rather than kept. This is the same discipline as
`mine_decisions.pick_quote()`, just enforced after an LLM call instead of
a regex match.

Extraction is deliberately kept separate from lifecycle resolution:
`current_status` here only reflects what the source artifact directly
states (a merged original is IMPLEMENTED, a revert record is REVERTED) —
whether something is *currently* active is still exclusively
`resolve_active`'s job (graph.py, unchanged since Stage 1).
"""

from __future__ import annotations

import base64
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vertex  # noqa: E402
from gh_util import gh_json  # noqa: E402

from models import Decision, DecisionStatus, Evidence, RelationshipType  # noqa: E402
from bundle_source import BundleArtifact, SourceBundle  # noqa: E402

REVERT_REF = re.compile(
    r"revert(?:s|ed|ing)?\s*(?:of\s*)?(?:[\w.-]+/[\w.-]+)?#(\d+)", re.IGNORECASE
)

_EXTRACTION_INSTRUCTIONS = """Extract a structured engineering-decision \
record from the source text below. Respond with ONLY a JSON object, no \
other text:
{
  "subject": "one-line description of the decision",
  "context": "the problem being addressed, or null",
  "chosen_approach": "what was chosen/done, or null",
  "rejected_alternatives": ["alternative that was rejected", ...],
  "rationale": "why, in your own words, or null if not stated",
  "rationale_quote": "a VERBATIM excerpt copied exactly from the source text below that supports the rationale, or null if no such excerpt exists",
  "constraints": ["constraint mentioned in the source", ...]
}

Only include a rejected_alternatives entry or a constraint if the source \
text actually states it — do not infer or invent one. rationale_quote \
must be copied character-for-character from the source; if you cannot \
find a real excerpt that supports the rationale, set both rationale and \
rationale_quote to null rather than paraphrasing.

Source text:
"""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _verify_quote(quote: str | None, source: str) -> bool:
    if not quote:
        return False
    return _normalize(quote) in _normalize(source)


def _extract_json(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _as_str_list(value: object) -> list[str]:
    """Coerces a field the model was asked to return as a JSON array into
    an actual list[str], defaulting to empty on any other shape (a bare
    string, a number, null). Without this, a malformed response where
    Gemini returns `"rejected_alternatives": "none"` instead of `[]` would
    pass a raw string into `Decision.rejected_alternatives`, and
    `retrieval.render_card`'s `'; '.join(...)` would silently iterate over
    its characters instead of failing or defaulting cleanly."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def extract_decision_fields(source_text: str) -> dict:
    """Calls Gemini for structured extraction, then programmatically
    verifies the returned rationale_quote is a real substring of
    source_text. Returns a dict of Decision-shaped fields; never trusts
    the model's self-reported verbatim-ness."""
    raw = vertex.generate(_EXTRACTION_INSTRUCTIONS + source_text)
    parsed = _extract_json(raw) or {}

    rationale_quote = parsed.get("rationale_quote")
    if not _verify_quote(rationale_quote, source_text):
        # Either no quote was found, or the model's "verbatim" excerpt
        # wasn't actually in the source — treat as insufficient evidence
        # rather than trust an unverified claim.
        rationale_quote = None
        parsed["rationale"] = None

    subject = parsed.get("subject")
    return {
        "subject": subject if isinstance(subject, str) and subject else "(untitled)",
        "context": parsed.get("context"),
        "chosen_approach": parsed.get("chosen_approach"),
        "rejected_alternatives": _as_str_list(parsed.get("rejected_alternatives")),
        "rationale": parsed.get("rationale"),
        "rationale_quote": rationale_quote,
        "constraints": _as_str_list(parsed.get("constraints")),
    }


def _fetch_revert_candidate(repo: str, revert_num: int) -> dict | None:
    """Fetches and validates a single revert-PR candidate by number.
    Returns None if it isn't a merged revert with a resolvable original."""
    try:
        revert_pr = gh_json(
            "pr", "view", str(revert_num), "--repo", repo,
            "--json", "number,title,body,mergedAt,url",
        )
    except Exception:
        return None
    if not revert_pr.get("mergedAt"):
        return None
    m = REVERT_REF.search(f"{revert_pr['title']} {revert_pr['body'] or ''}")
    if not m:
        return None
    original_num = int(m.group(1))
    try:
        original_pr = gh_json(
            "pr", "view", str(original_num), "--repo", repo,
            "--json", "number,title,body,mergedAt,url",
        )
    except Exception:
        return None
    return {
        "repo": repo, "source": "revert_pair",
        "original_num": original_num, "original_pr": original_pr,
        "revert_num": revert_num, "revert_pr": revert_pr,
        "source_text": f"PR #{revert_num}: {revert_pr['title']}\n\n{revert_pr.get('body') or ''}",
    }


def fetch_specific_revert_pair(repo: str, revert_num: int) -> dict | None:
    """For targeted testing/cross-validation against a known pair, instead
    of relying on search ranking to surface it."""
    return _fetch_revert_candidate(repo, revert_num)


def discover_revert_pairs(repo: str, target: int) -> list[dict]:
    """Returns raw candidate records (not yet extracted): each has the
    repo, original/revert PR numbers+URLs, and the revert PR's raw body
    text (the source extraction runs against)."""
    search = gh_json(
        "api", "-X", "GET", "search/issues",
        "-f", f"q=repo:{repo} is:pr is:merged revert in:title",
        "-f", "per_page=50",
    )
    items = search.get("items", []) if isinstance(search, dict) else []
    found: list[dict] = []
    for item in items:
        if len(found) >= target:
            break
        candidate = _fetch_revert_candidate(repo, item["number"])
        if candidate:
            found.append(candidate)
    return found


def discover_kep_alternatives(repo: str, target: int) -> list[dict]:
    results = gh_json(
        "search", "code", "Alternatives Considered",
        "--repo", repo, "--extension", "md", "--limit", "40",
        "--json", "path",
    )
    found: list[dict] = []
    for item in results:
        if len(found) >= target:
            break
        path = item["path"]
        try:
            content = gh_json("api", f"repos/{repo}/contents/{path}")
        except Exception:
            continue
        if not isinstance(content, dict) or "content" not in content:
            continue
        try:
            text = base64.b64decode(content["content"]).decode("utf-8", errors="ignore")
        except Exception:
            continue
        section = re.search(
            r"##\s*Alternatives(?: Considered)?\s*\n(.*?)(?:\n##\s|\Z)",
            text, re.IGNORECASE | re.DOTALL,
        )
        if not section:
            continue
        found.append({
            "repo": repo, "source": "kep_alternatives", "path": path,
            "url": f"https://github.com/{repo}/blob/master/{path}",
            "source_text": section.group(1).strip(),
        })
    return found


def revert_pair_to_decisions(candidate: dict) -> list[Decision]:
    fields = extract_decision_fields(candidate["source_text"])
    repo = candidate["repo"]
    original_id = f"{repo}-pr-{candidate['original_num']}"
    revert_id = f"{repo}-pr-{candidate['revert_num']}"

    original = Decision(
        id=original_id,
        subject=candidate["original_pr"]["title"],
        current_status=DecisionStatus.IMPLEMENTED,
        chosen_approach=candidate["original_pr"]["title"],
        introduced_at=candidate["original_pr"].get("mergedAt"),
        evidence=[Evidence(
            type="pr", url=candidate["original_pr"]["url"],
            quote=candidate["original_pr"]["title"],
        )],
    )
    revert = Decision(
        id=revert_id,
        subject=fields["subject"],
        current_status=DecisionStatus.REVERTED,
        context=fields["context"],
        rejected_alternatives=fields["rejected_alternatives"],
        rationale=fields["rationale"],
        constraints=fields["constraints"],
        evidence=(
            [Evidence(
                type="revert_pr", url=candidate["revert_pr"]["url"],
                quote=fields["rationale_quote"],
            )] if fields["rationale_quote"] else []
        ),
        related_decisions=[(original_id, RelationshipType.REVERTS)],
    )
    return [original, revert]


def kep_to_decision(candidate: dict) -> Decision:
    fields = extract_decision_fields(candidate["source_text"])
    return Decision(
        id=f"kep-{candidate['path'].replace('/README.md', '').replace('/', '-')}",
        subject=fields["subject"],
        current_status=DecisionStatus.ACCEPTED,
        context=fields["context"],
        chosen_approach=fields["chosen_approach"],
        rejected_alternatives=fields["rejected_alternatives"],
        rationale=fields["rationale"],
        constraints=fields["constraints"],
        evidence=(
            [Evidence(
                type="proposal", url=candidate["url"], quote=fields["rationale_quote"],
            )] if fields["rationale_quote"] else []
        ),
    )


def ingest_repo(
    repo: str, revert_target: int = 3, kep_target: int = 3,
) -> list[Decision]:
    decisions: list[Decision] = []
    for candidate in discover_revert_pairs(repo, revert_target):
        decisions.extend(revert_pair_to_decisions(candidate))
    for candidate in discover_kep_alternatives(repo, kep_target):
        decisions.append(kep_to_decision(candidate))
    return decisions


# Bundle extraction deliberately uses the same Gemini boundary and quote
# verification as live ingestion, but its transport is a SourceBundle rather
# than gh_json.  No benchmark metadata is accepted by this interface.
_BUNDLE_EXTRACTION_INSTRUCTIONS = """Extract engineering decisions from the raw source artifacts below.
Use only the prompt and artifact text. Do not use filenames as authority
labels and do not infer facts that are not explicitly supported by the text.
Return ONLY one JSON object with this shape:
{
  "requested_scope": "the exact code/subsystem scope requested, or null",
  "decisions": [
    {
      "artifact_id": "artifact_NNN",
      "subject": "one-line decision subject",
      "current_status": "PROPOSED|ACCEPTED|IMPLEMENTED|REVERTED|SUPERSEDED|REAFFIRMED",
      "role": "policy|implementation|unknown",
      "scopes": ["literal scope strings explicitly supported by the source"],
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
  "uncertainty": ["facts the artifacts do not establish"]
}

Status, scope, role, relationships, and partial acceptance must be reported
only when the raw artifacts support them. If a field cannot be established,
use null, an empty list, or unknown. Never use outside knowledge.

Requested change:
"""

_STATUS_BY_VALUE = {status.value: status for status in DecisionStatus}
_RELATIONSHIP_BY_VALUE = {relationship.value: relationship for relationship in RelationshipType}


@dataclass(frozen=True)
class BundleExtractionResult:
    """Source-derived decisions plus explicit extraction diagnostics."""

    decisions: tuple[Decision, ...]
    records: tuple[dict, ...]
    requested_scope: str | None
    uncertainty: tuple[str, ...]
    failures: tuple[str, ...]
    raw_response: str


def _bundle_prompt(source: SourceBundle) -> str:
    parts = [_BUNDLE_EXTRACTION_INSTRUCTIONS, source.requested_change()]
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


def _valid_index(value: object, size: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value < size else None


def extract_bundle_decisions(
    source: SourceBundle,
    generator: Callable[[str], str] | None = None,
) -> BundleExtractionResult:
    """Extract typed records from a neutral bundle using source text only.

    ``generator`` is injectable solely for offline parser/fairness tests. The
    default is the same Vertex/Gemini generator used by live ingestion.
    Invalid model claims are dropped or recorded as uncertainty; no fallback
    status, scope, edge, or benchmark expectation is invented here.
    """
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
        artifact_id = raw.get("artifact_id")
        if not isinstance(artifact_id, str) or artifact_id not in artifact_map:
            failures.append(f"decision[{ordinal}] referenced an unknown artifact")
            continue
        status = _STATUS_BY_VALUE.get(raw.get("current_status"))
        if status is None:
            failures.append(f"decision[{ordinal}] had no supported explicit status")
            continue
        subject = raw.get("subject")
        if not isinstance(subject, str) or not subject.strip():
            failures.append(f"decision[{ordinal}] had no subject")
            continue

        scopes = _as_str_list(raw.get("scopes"))
        rejected = _as_str_list(raw.get("rejected_alternatives"))
        constraints = _as_str_list(raw.get("constraints"))
        relationships: list[tuple[str, RelationshipType]] = []
        raw_relationships = raw.get("related_decisions", [])
        if not isinstance(raw_relationships, list):
            raw_relationships = []
            failures.append(f"decision[{ordinal}] relationships were not a list")
        for relationship in raw_relationships:
            if not isinstance(relationship, dict):
                failures.append(f"decision[{ordinal}] had a malformed relationship")
                continue
            target_index = _valid_index(relationship.get("target_index"), len(raw_records))
            relation = _RELATIONSHIP_BY_VALUE.get(relationship.get("relationship"))
            if target_index is None or relation is None:
                failures.append(f"decision[{ordinal}] had an unsupported relationship")
                continue
            # IDs are generated from neutral artifact identity and position,
            # never accepted from the model or benchmark metadata.
            target = raw_records[target_index]
            target_artifact = target.get("artifact_id") if isinstance(target, dict) else None
            if not isinstance(target_artifact, str) or target_artifact not in artifact_map:
                failures.append(f"decision[{ordinal}] relationship target was invalid")
                continue
            target_id = f"bundle-{target_artifact}-decision-{target_index}"
            relationships.append((target_id, relation))

        evidence: list[Evidence] = []
        raw_quotes = raw.get("evidence_quotes", [])
        if not isinstance(raw_quotes, list):
            raw_quotes = []
            failures.append(f"decision[{ordinal}] evidence_quotes were not a list")
        for quote_record in raw_quotes:
            if not isinstance(quote_record, dict):
                continue
            quote_artifact_id = quote_record.get("artifact_id")
            quote = quote_record.get("quote")
            quote_artifact = artifact_map.get(quote_artifact_id)
            if quote_artifact is None or not isinstance(quote, str) or not _verify_quote(quote, quote_artifact.content):
                failures.append(f"decision[{ordinal}] contained an unverifiable evidence quote")
                continue
            evidence.append(Evidence(
                type=quote_artifact.source_type,
                url=quote_artifact.source_url or f"bundle:{quote_artifact.source_id}",
                quote=quote,
            ))

        decision_id = f"bundle-{artifact_id}-decision-{ordinal}"
        decision = Decision(
            id=decision_id,
            subject=subject.strip(),
            current_status=status,
            context=raw.get("context") if isinstance(raw.get("context"), str) else None,
            chosen_approach=(raw.get("chosen_approach") if isinstance(raw.get("chosen_approach"), str) else None),
            rejected_alternatives=rejected,
            rationale=(raw.get("rationale") if isinstance(raw.get("rationale"), str) else None),
            constraints=constraints,
            introduced_at=artifact_map[artifact_id].timestamp,
            evidence=evidence,
            related_components=scopes,
            related_decisions=relationships,
            partial_acceptance=raw.get("partial_acceptance") is True,
        )
        decisions.append(decision)
        records.append({
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
        })

    requested_scope = parsed.get("requested_scope")
    if not isinstance(requested_scope, str) or not requested_scope.strip():
        requested_scope = None
        failures.append("model did not establish a requested scope")
    uncertainty = tuple(item for item in parsed.get("uncertainty", []) if isinstance(item, str))
    return BundleExtractionResult(
        decisions=tuple(decisions),
        records=tuple(records),
        requested_scope=requested_scope,
        uncertainty=uncertainty,
        failures=tuple(failures),
        raw_response=response,
    )
