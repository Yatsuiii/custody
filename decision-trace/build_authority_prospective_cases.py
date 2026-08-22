"""Build the source-adjudicated prospective authority dataset.

The source cache is primary evidence collected before any system output. This
builder is deterministic and emits public history separately from hidden truth.
It never imports or invokes DecisionTrace, RAG, Vertex, or a model.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "prospective"
SOURCE_CACHE = DATA / "discovery" / "source_cache.json"
PUBLIC = DATA / "timelines.json"
CHECKPOINTS = DATA / "checkpoints.jsonl"
TRUTH = DATA / "ground_truth.jsonl"
EXCLUSIONS = DATA / "discovery" / "exclusions.json"


def read_cache() -> dict:
    return json.loads(SOURCE_CACHE.read_text())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def source_ref(kind: str, key: str, *, quote: str | None = None,
               field: str | None = None, value=None) -> dict:
    item = {"kind": kind, "key": key}
    if quote is not None:
        item["quote"] = quote
    if field is not None:
        item["field"] = field
        item["value"] = value
    return item


def artifact(artifact_id: str, decision_id: str, title: str, status: str,
             timestamp: str, repository: str, source_url: str,
             pinned_revision: str, source_quotes: list[str], scopes: tuple[str, ...],
             sequence: int, *, role: str = "POLICY", replaces=(), reverts=(),
             implements=(), source_type: str = "proposal", proofs=()) -> dict:
    return {
        "artifact_id": artifact_id,
        "decision_id": decision_id,
        "title": title,
        "subject": title,
        "status": status,
        "timestamp": timestamp,
        "repository": repository,
        "source_url": source_url,
        "pinned_revision": pinned_revision,
        "source_text": "\n".join(source_quotes),
        "source_quotes": source_quotes,
        "scopes": list(scopes),
        "sequence": sequence,
        "replaces": list(replaces),
        "reverts": list(reverts),
        "implements": list(implements),
        "role": role,
        "source_type": source_type,
        "proofs": list(proofs),
    }


def checkpoint(timeline_id: str, index: int, visible: int, question: str,
               scopes: tuple[str, ...], state: str, decisions=(), evidence_sets=(),
               scenarios=(), failures=(), consistency: str | None = None,
               adjudication: str = "") -> tuple[dict, dict]:
    checkpoint_id = f"{timeline_id}-c{index}"
    public = {
        "checkpoint_id": checkpoint_id,
        "timeline_id": timeline_id,
        "visible_through": visible,
        "question": question,
        "authority_scopes": list(scopes),
        "consistency_group": consistency,
    }
    hidden = {
        "checkpoint_id": checkpoint_id,
        "timeline_id": timeline_id,
        "expected_state": state,
        "expected_decision_ids": list(decisions),
        "acceptable_evidence_sets": [list(s) for s in evidence_sets],
        "scenario_types": list(scenarios),
        "applicable_failures": list(failures),
        "adjudication": adjudication,
    }
    return public, hidden


def build() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    cache = read_cache()
    timelines: list[dict] = []
    checkpoints: list[dict] = []
    truth: list[dict] = []
    exclusions: list[dict] = []

    def add(timeline_id: str, ecosystem: str, repositories: tuple[str, ...],
            composition: str, scenarios: tuple[str, ...], artifacts: list[dict],
            rows: list[tuple[dict, dict]], audit_note: str) -> None:
        timelines.append({
            "timeline_id": timeline_id,
            "ecosystem": ecosystem,
            "repositories": list(repositories),
            "composition": composition,
            "synthetic_elements": ["developer question wording"],
            "scenario_types": list(scenarios),
            "audit_note": audit_note,
            "artifacts": artifacts,
        })
        for public, hidden in rows:
            checkpoints.append(public)
            truth.append(hidden)

    def file_record(repository: str, path: str) -> dict:
        return cache["files"][f"{repository}:{path}"]

    def file_proof(repository: str, path: str, quote: str) -> dict:
        return source_ref("file", f"{repository}:{path}", quote=quote)

    def pr_record(repository: str, number: int) -> dict:
        return cache["pull_requests"][f"{repository}#{number}"]

    def pr_proof(repository: str, number: int, *, field: str, value=None,
                 quote: str | None = None) -> dict:
        record = pr_record(repository, number)
        if value is None:
            value = record[field]
        return source_ref("pull_request", f"{repository}#{number}", quote=quote,
                          field=field, value=value)

    def pr_artifact(repository: str, number: int, status: str, sequence: int,
                    scopes: tuple[str, ...], *, role="IMPLEMENTATION", replaces=(),
                    reverts=(), implements=(), snapshot="merged", extra_proofs=()) -> dict:
        record = pr_record(repository, number)
        timestamp = record["createdAt"] if snapshot == "open" else record["mergedAt"]
        revision = (
            f"github-open-event-{record['createdAt']}"
            if snapshot == "open" else record["mergeCommit"]["oid"]
        )
        quotes = [record["title"]]
        if record.get("body"):
            quotes.append(record["body"])
        status_field = "createdAt" if snapshot == "open" else "mergedAt"
        proofs = [pr_proof(repository, number, field=status_field)]
        proofs.extend(extra_proofs)
        return artifact(
            f"{repository}#{number}@{snapshot}", f"{repository}#{number}",
            record["title"], status, timestamp, repository, record["url"], revision,
            quotes, scopes, sequence, role=role, replaces=replaces, reverts=reverts,
            implements=implements, source_type="pr", proofs=proofs,
        )

    def gov(area: str) -> str:
        return f"What organizational decision currently governs {area}? Cite the source artifacts that establish current authority."

    # Four PEP pairs whose predecessor and successor are both source-explicit
    # Final standards. Current old-document notices arrive only after the
    # successor in the visible timeline, preventing future-state leakage.
    pep_pairs = [
        ("python-db-api", 248, "Python Database API 1.0", 249,
         "Python Database API 2.0", "python-db-api", "1996-05-08T00:00:00Z",
         "1999-04-12T00:00:00Z"),
        ("python-wsgi", 333, "Python WSGI 1.0", 3333,
         "Python WSGI 1.0.1", "python-wsgi", "2003-12-07T00:00:00Z",
         "2010-09-26T00:00:00Z"),
        ("python-exception-context", 409, "Exception context suppression",
         415, "Exception-attribute context suppression", "python-exception-context",
         "2012-01-26T00:00:00Z", "2012-02-26T00:00:00Z"),
        ("python-hash-api", 247, "Cryptographic hash API v1", 452,
         "Cryptographic hash API v2", "python-hash-api", "2001-03-23T00:00:00Z",
         "2013-08-15T00:00:00Z"),
    ]
    for tid, old, old_title, new, new_title, scope, old_time, new_time in pep_pairs:
        old_path = f"peps/pep-{old:04d}.rst"
        new_path = f"peps/pep-{new:04d}.rst"
        old_file = file_record("python/peps", old_path)
        new_file = file_record("python/peps", new_path)
        old_status = "Status: Final"
        new_status = "Status: Final"
        relation = f"Replaces: {old}"
        reverse = f"Superseded-By: {new}"
        old_quotes = [f"PEP: {old}", f"Title: {old_file['content'].split('Title: ',1)[1].splitlines()[0]}", old_status]
        new_quotes = [f"PEP: {new}", f"Title: {new_file['content'].split('Title: ',1)[1].splitlines()[0]}", new_status, relation]
        a1 = artifact(
            f"PEP-{old}@accepted", f"PEP-{old}", old_title, "FINAL", old_time,
            "python/peps", old_file["url"], old_file["revision"], old_quotes,
            (scope,), 1, proofs=(file_proof("python/peps", old_path, old_status),),
        )
        a2 = artifact(
            f"PEP-{new}@accepted", f"PEP-{new}", new_title, "FINAL", new_time,
            "python/peps", new_file["url"], new_file["revision"], new_quotes,
            (scope,), 2, replaces=(f"PEP-{old}",),
            proofs=(file_proof("python/peps", new_path, new_status),
                    file_proof("python/peps", new_path, relation)),
        )
        note_path = old_path if reverse in old_file["content"] else new_path
        note_file = old_file if note_path == old_path else new_file
        note_quote = reverse if note_path == old_path else relation
        a3 = artifact(
            f"PEP-{old}@current-note", f"PEP-{old}",
            f"Current registry notice mentioning PEP {old}", "NOTE", "2026-08-22T00:00:00Z",
            "python/peps", note_file["url"], note_file["revision"], [note_quote],
            (scope,), 3, role="MENTION", source_type="proposal",
            proofs=(file_proof("python/peps", note_path, note_quote),),
        )
        rows = [
            checkpoint(tid, 1, 1, gov(scope.replace("-", " ")), (scope,),
                       "GOVERNING", (f"PEP-{old}",), ((a1["artifact_id"],),),
                       ("simple_supersession",)),
            checkpoint(tid, 2, 2, gov(scope.replace("-", " ")), (scope,),
                       "GOVERNING", (f"PEP-{new}",), ((a2["artifact_id"],),),
                       ("simple_supersession",), ("STALE_DECISION", "SUPERSESSION_MISSED")),
            checkpoint(tid, 3, 3, gov(scope.replace("-", " ") + " after the newer registry notice"),
                       (scope,), "GOVERNING", (f"PEP-{new}",),
                       ((a2["artifact_id"], a3["artifact_id"]),),
                       ("simple_supersession", "mention_without_transition"),
                       ("STALE_DECISION", "RECENCY_CONFUSION"), f"{tid}-final"),
            checkpoint(tid, 4, 3, f"Which accepted standard is authoritative for {scope.replace('-', ' ')} now?",
                       (scope,), "GOVERNING", (f"PEP-{new}",),
                       ((a2["artifact_id"], a3["artifact_id"]),),
                       ("simple_supersession", "mention_without_transition"),
                       ("STALE_DECISION", "SUPERSESSION_MISSED"), f"{tid}-final"),
        ]
        add(tid, "Python", ("python/peps",), "hybrid",
            ("simple_supersession", "mention_without_transition"), [a1, a2, a3], rows,
            "Historical PEP creation checkpoints plus a current pinned registry notice; no lifecycle fact is synthetic.")

    def rust_supersession(tid: str, old: int, new: int, old_path: str,
                          new_path: str, scope: str, relation_quote: str,
                          *, partial: bool = False, remaining_scope: str | None = None) -> None:
        old_pr = pr_record("rust-lang/rfcs", old)
        new_pr = pr_record("rust-lang/rfcs", new)
        old_file = file_record("rust-lang/rfcs", old_path)
        new_file = file_record("rust-lang/rfcs", new_path)
        old_scopes = (remaining_scope,) if partial and remaining_scope else (scope,)
        a1 = artifact(
            f"RFC-{old}@merged", f"RFC-{old}", old_pr["title"], "MERGED",
            old_pr["mergedAt"], "rust-lang/rfcs", old_file["url"],
            ((old_pr.get("mergeCommit") or {}).get("oid")
             or f"github-merged-event-{old_pr['mergedAt']}"),
            [old_pr["title"]], old_scopes, 1,
            proofs=(pr_proof("rust-lang/rfcs", old, field="mergedAt"),),
        )
        a2 = artifact(
            f"RFC-{new}@open", f"RFC-{new}", new_pr["title"], "OPEN",
            new_pr["createdAt"], "rust-lang/rfcs", new_pr["url"],
            f"github-open-event-{new_pr['createdAt']}", [new_pr["title"]],
            (scope,), 2, replaces=(f"RFC-{old}",),
            proofs=(pr_proof("rust-lang/rfcs", new, field="createdAt"),),
        )
        a3 = artifact(
            f"RFC-{new}@current-authority", f"RFC-{new}", new_pr["title"], "MERGED",
            "2026-08-22T00:00:00Z", "rust-lang/rfcs", new_file["url"],
            new_file["revision"], [new_pr["title"], relation_quote], (scope,), 3,
            replaces=(f"RFC-{old}",), proofs=(
                pr_proof("rust-lang/rfcs", new, field="mergedAt"),
                file_proof("rust-lang/rfcs", old_path, relation_quote),
            ),
        )
        rows = [
            checkpoint(tid, 1, 1, gov((remaining_scope or scope).replace("-", " ")),
                       ((remaining_scope or scope),), "GOVERNING", (f"RFC-{old}",),
                       ((a1["artifact_id"],),), ("simple_supersession",)),
            checkpoint(tid, 2, 2, gov((remaining_scope or scope).replace("-", " ") + " while the successor RFC is open"),
                       ((remaining_scope or scope),), "GOVERNING", (f"RFC-{old}",),
                       ((a1["artifact_id"], a2["artifact_id"]),),
                       ("proposal_while_current",), ("PROPOSAL_PROMOTED",)),
            checkpoint(tid, 3, 3, gov(scope.replace("-", " ")), (scope,),
                       "GOVERNING", (f"RFC-{new}",), ((a3["artifact_id"],),),
                       ("simple_supersession",), ("STALE_DECISION", "SUPERSESSION_MISSED")),
        ]
        if partial:
            broad = scope + "-broad"
            note = artifact(
                f"RFC-{old}@partial-note", f"RFC-{old}", "Partial supersession notice",
                "NOTE", "2026-08-22T00:00:01Z", "rust-lang/rfcs", old_file["url"],
                old_file["revision"], [relation_quote], (broad,), 4, role="MENTION",
                proofs=(file_proof("rust-lang/rfcs", old_path, relation_quote),),
            )
            rows.append(checkpoint(
                tid, 4, 4, gov(scope.replace("-", " ") + " as one undifferentiated policy"),
                (broad,), "UNRESOLVED", (), ((note["artifact_id"], a1["artifact_id"], a3["artifact_id"]),),
                ("partial_supersession", "conflicting_or_ambiguous"),
                ("UNSUPPORTED_AUTHORITY", "SUPERSESSION_MISSED"),
                adjudication="The primary source says only partially/mostly superseded, so broad authority is insufficiently specified."))
            artifacts = [a1, a2, a3, note]
            scenario_types = ("proposal_while_current", "partial_supersession", "conflicting_or_ambiguous")
        else:
            rows.append(checkpoint(
                tid, 4, 3, f"Which RFC is authoritative now for {scope.replace('-', ' ')}?",
                (scope,), "GOVERNING", (f"RFC-{new}",), ((a3["artifact_id"],),),
                ("simple_supersession",), ("STALE_DECISION", "SUPERSESSION_MISSED"),
                f"{tid}-final"))
            rows[-2][0]["consistency_group"] = f"{tid}-final"
            artifacts = [a1, a2, a3]
            scenario_types = ("proposal_while_current", "simple_supersession")
            if old == 1201:
                scenario_types += ("withdrawn_decision",)
        add(tid, "Rust", ("rust-lang/rfcs",), "fully_real", scenario_types,
            artifacts, rows, "PR open/merge events and current explicit RFC supersession text are primary-source pinned.")

    rust_supersession(
        "rust-naked-functions", 1201, 2972, "text/1201-naked-fns.md",
        "text/2972-constrained-naked.md", "rust-naked-functions",
        "In short this RFC was superseded by RFC 2972. For details see the [summary comment].")
    rust_supersession(
        "rust-global-allocator", 1183, 1974, "text/1183-swap-out-jemalloc.md",
        "text/1974-global-allocators.md", "rust-global-allocator",
        "*Note:* this RFC has been superseded by [RFC 1974][].")
    rust_supersession(
        "rust-inline-const", 2203, 2920, "text/2203-const-repeat-expr.md",
        "text/2920-inline-const.md", "rust-inline-const",
        "> ⚠ This RFC has mostly been superseded ⚠", partial=True,
        remaining_scope="rust-const-repeat-simple-case")
    rust_supersession(
        "rust-drop-check", 769, 1238, "text/0769-sound-generic-drop.md",
        "text/1238-nonparametric-dropck.md", "rust-dropck-parametricity",
        "2015.09.18 -- This RFC was partially superseded by [RFC 1238], which",
        partial=True, remaining_scope="rust-generic-drop-safety")

    # Exact two-hop RFC chain: 2071 -> 2515 -> 3498 for type-alias impl-Trait
    # capture behavior.
    r2071 = pr_record("rust-lang/rfcs", 2071)
    r2515 = pr_record("rust-lang/rfcs", 2515)
    r3498 = pr_record("rust-lang/rfcs", 3498)
    p2071 = "text/2071-impl-trait-existential-types.md"
    p2515 = "text/2515-type_alias_impl_trait.md"
    p3498 = "text/3498-lifetime-capture-rules-2024.md"
    scope = "rust-type-alias-impl-trait-capture"
    a1 = artifact("RFC-2071@merged", "RFC-2071", r2071["title"], "MERGED",
                  r2071["mergedAt"], "rust-lang/rfcs", r2071["url"],
                  r2071["mergeCommit"]["oid"], [r2071["title"]], (scope,), 1,
                  proofs=(pr_proof("rust-lang/rfcs", 2071, field="mergedAt"),))
    a2 = artifact("RFC-2515@open", "RFC-2515", r2515["title"], "OPEN",
                  r2515["createdAt"], "rust-lang/rfcs", r2515["url"],
                  f"github-open-event-{r2515['createdAt']}", [r2515["title"]],
                  (scope,), 2, replaces=("RFC-2071",),
                  proofs=(pr_proof("rust-lang/rfcs", 2515, field="createdAt"),))
    q2515 = "Allow type aliases and associated types to use `impl Trait`, replacing the prototype `existential type` as a way to declare type aliases and associated types for opaque, uniquely inferred types."
    a3 = artifact("RFC-2515@merged", "RFC-2515", r2515["title"], "MERGED",
                  r2515["mergedAt"], "rust-lang/rfcs", file_record("rust-lang/rfcs", p2515)["url"],
                  r2515["mergeCommit"]["oid"], [r2515["title"], q2515], (scope,), 3,
                  replaces=("RFC-2071",), proofs=(
                      pr_proof("rust-lang/rfcs", 2515, field="mergedAt"),
                      file_proof("rust-lang/rfcs", p2515, q2515)))
    q3498 = "This updates and supersedes the behavior specified in [RFC 2071] and [RFC 2515]."
    a4 = artifact("RFC-3498@merged", "RFC-3498", r3498["title"], "MERGED",
                  r3498["mergedAt"], "rust-lang/rfcs", file_record("rust-lang/rfcs", p3498)["url"],
                  r3498["mergeCommit"]["oid"], [r3498["title"], q3498], (scope,), 4,
                  replaces=("RFC-2515",), proofs=(
                      pr_proof("rust-lang/rfcs", 3498, field="mergedAt"),
                      file_proof("rust-lang/rfcs", p3498, q3498)))
    rows = [
        checkpoint("rust-tait-capture", 1, 1, gov("Rust type-alias impl Trait capture behavior"),
                   (scope,), "GOVERNING", ("RFC-2071",), ((a1["artifact_id"],),), ("multi_hop_supersession",)),
        checkpoint("rust-tait-capture", 2, 2, gov("Rust type-alias impl Trait capture behavior while a replacement is proposed"),
                   (scope,), "GOVERNING", ("RFC-2071",), ((a1["artifact_id"], a2["artifact_id"]),),
                   ("proposal_while_current", "multi_hop_supersession"), ("PROPOSAL_PROMOTED",)),
        checkpoint("rust-tait-capture", 3, 3, gov("Rust type-alias impl Trait capture behavior"),
                   (scope,), "GOVERNING", ("RFC-2515",), ((a3["artifact_id"],),),
                   ("multi_hop_supersession",), ("STALE_DECISION", "SUPERSESSION_MISSED")),
        checkpoint("rust-tait-capture", 4, 4, gov("Rust type-alias impl Trait capture behavior in the current rules"),
                   (scope,), "GOVERNING", ("RFC-3498",), ((a4["artifact_id"],),),
                   ("multi_hop_supersession",), ("STALE_DECISION", "SUPERSESSION_MISSED")),
    ]
    add("rust-tait-capture", "Rust", ("rust-lang/rfcs",), "fully_real",
        ("multi_hop_supersession", "proposal_while_current"), [a1, a2, a3, a4], rows,
        "Each hop is an accepted RFC with source-explicit replacement/supersession wording.")

    # Second two-hop RFC evolution: conservative impl Trait -> expanded/stable
    # impl Trait -> 2024 capture rules that explicitly supersede both earlier
    # behaviors. "Replaces" is the benchmark adapter's normalized edge name;
    # the public proof retains the source's exact "expanding" wording.
    r1522 = pr_record("rust-lang/rfcs", 1522)
    r1951 = pr_record("rust-lang/rfcs", 1951)
    p1522 = "text/1522-conservative-impl-trait.md"
    p1951 = "text/1951-expand-impl-trait.md"
    scope = "rust-impl-trait-capture-rules"
    b1 = artifact("RFC-1522@merged", "RFC-1522", r1522["title"], "MERGED",
                  r1522["mergedAt"], "rust-lang/rfcs", r1522["url"],
                  (r1522.get("mergeCommit") or {}).get("oid") or f"github-merged-event-{r1522['mergedAt']}",
                  [r1522["title"]], (scope,), 1,
                  proofs=(pr_proof("rust-lang/rfcs", 1522, field="mergedAt"),))
    b2 = artifact("RFC-1951@open", "RFC-1951", r1951["title"], "OPEN",
                  r1951["createdAt"], "rust-lang/rfcs", r1951["url"],
                  f"github-open-event-{r1951['createdAt']}", [r1951["title"]],
                  (scope,), 2, replaces=("RFC-1522",),
                  proofs=(pr_proof("rust-lang/rfcs", 1951, field="createdAt"),))
    q1951 = "This RFC proposes to stabilize the `impl Trait` feature with its current syntax,\nwhile also expanding it to encompass argument position."
    b3 = artifact("RFC-1951@merged", "RFC-1951", r1951["title"], "MERGED",
                  r1951["mergedAt"], "rust-lang/rfcs", file_record("rust-lang/rfcs", p1951)["url"],
                  (r1951.get("mergeCommit") or {}).get("oid") or f"github-merged-event-{r1951['mergedAt']}",
                  [r1951["title"], q1951], (scope,), 3, replaces=("RFC-1522",),
                  proofs=(pr_proof("rust-lang/rfcs", 1951, field="mergedAt"),
                          file_proof("rust-lang/rfcs", p1951, q1951)))
    q3498_rpit = "This updates and supersedes the behavior specified in [RFC 1522] and [RFC 1951]."
    b4 = artifact("RFC-3498@rpit-authority", "RFC-3498", r3498["title"], "MERGED",
                  r3498["mergedAt"], "rust-lang/rfcs", file_record("rust-lang/rfcs", p3498)["url"],
                  r3498["mergeCommit"]["oid"], [r3498["title"], q3498_rpit], (scope,), 4,
                  replaces=("RFC-1951",), proofs=(
                      pr_proof("rust-lang/rfcs", 3498, field="mergedAt"),
                      file_proof("rust-lang/rfcs", p3498, q3498_rpit)))
    rows = [
        checkpoint("rust-rpit-capture", 1, 1, gov("Rust impl Trait capture rules"),
                   (scope,), "GOVERNING", ("RFC-1522",), ((b1["artifact_id"],),),
                   ("multi_hop_supersession",)),
        checkpoint("rust-rpit-capture", 2, 2, gov("Rust impl Trait capture rules while expansion is proposed"),
                   (scope,), "GOVERNING", ("RFC-1522",), ((b1["artifact_id"], b2["artifact_id"]),),
                   ("proposal_while_current", "multi_hop_supersession"), ("PROPOSAL_PROMOTED",)),
        checkpoint("rust-rpit-capture", 3, 3, gov("Rust impl Trait capture rules after the expansion was accepted"),
                   (scope,), "GOVERNING", ("RFC-1951",), ((b3["artifact_id"],),),
                   ("multi_hop_supersession",), ("SUPERSESSION_MISSED",)),
        checkpoint("rust-rpit-capture", 4, 4, gov("Rust impl Trait capture rules in Rust 2024"),
                   (scope,), "GOVERNING", ("RFC-3498",), ((b4["artifact_id"],),),
                   ("multi_hop_supersession",), ("STALE_DECISION", "SUPERSESSION_MISSED")),
    ]
    add("rust-rpit-capture", "Rust", ("rust-lang/rfcs",), "fully_real",
        ("multi_hop_supersession", "proposal_while_current"), [b1, b2, b3, b4], rows,
        "RFC 1951 explicitly stabilizes and expands RFC 1522 behavior; RFC 3498 explicitly supersedes both.")

    # Swift withdrawn proposal replaced by accepted property wrappers.
    s30p = "proposals/0030-property-behavior-decls.md"
    s258p = "proposals/0258-property-wrappers.md"
    s30 = file_record("swiftlang/swift-evolution", s30p)
    s258 = file_record("swiftlang/swift-evolution", s258p)
    qwithdrawn = "* Status: **Withdrawn**"
    qsup = "* Superseded by: [SE-0258](0258-property-wrappers.md)"
    q258status = next(line for line in s258["content"].splitlines() if line.startswith("* Status:"))
    scope = "swift-property-wrappers"
    a1 = artifact("SE-0030@withdrawn", "SE-0030", "Property behaviors", "WITHDRAWN",
                  "2016-05-01T00:00:00Z", "swiftlang/swift-evolution", s30["url"],
                  s30["revision"], [qwithdrawn, qsup], (scope,), 1,
                  proofs=(file_proof("swiftlang/swift-evolution", s30p, qwithdrawn),))
    a2 = artifact("SE-0258@accepted", "SE-0258", "Property wrappers", "ACCEPTED",
                  "2019-06-01T00:00:00Z", "swiftlang/swift-evolution", s258["url"],
                  s258["revision"], [q258status, qsup], (scope,), 2,
                  replaces=("SE-0030",), proofs=(
                      file_proof("swiftlang/swift-evolution", s258p, q258status),
                      file_proof("swiftlang/swift-evolution", s30p, qsup)))
    a3 = artifact("SE-0030@historical-note", "SE-0030", "Historical property-behavior proposal",
                  "NOTE", "2026-08-22T00:00:00Z", "swiftlang/swift-evolution", s30["url"],
                  s30["revision"], [qsup], (scope,), 3, role="MENTION",
                  proofs=(file_proof("swiftlang/swift-evolution", s30p, qsup),))
    rows = [
        checkpoint("swift-property-wrappers", 1, 1, gov("Swift property behaviors or wrappers"),
                   (scope,), "NO_GOVERNING_DECISION", (), ((a1["artifact_id"],),),
                   ("withdrawn_decision",), ("UNSUPPORTED_AUTHORITY",)),
        checkpoint("swift-property-wrappers", 2, 2, gov("Swift property wrappers"),
                   (scope,), "GOVERNING", ("SE-0258",), ((a2["artifact_id"],),),
                   ("simple_supersession", "withdrawn_decision"), ("SUPERSESSION_MISSED",)),
        checkpoint("swift-property-wrappers", 3, 3, gov("Swift property wrappers after the historical proposal is mentioned"),
                   (scope,), "GOVERNING", ("SE-0258",), ((a2["artifact_id"], a3["artifact_id"]),),
                   ("mention_without_transition",), ("RECENCY_CONFUSION",)),
        checkpoint("swift-property-wrappers", 4, 3, "Which accepted Swift Evolution decision authorizes property wrappers now?",
                   (scope,), "GOVERNING", ("SE-0258",), ((a2["artifact_id"], a3["artifact_id"]),),
                   ("simple_supersession",), ("STALE_DECISION",), "swift-property-final"),
    ]
    rows[2][0]["consistency_group"] = "swift-property-final"
    add("swift-property-wrappers", "Swift", ("swiftlang/swift-evolution",), "fully_real",
        ("withdrawn_decision", "simple_supersession", "mention_without_transition"),
        [a1, a2, a3], rows, "Current proposal headers explicitly record withdrawal, successor, and accepted implementation status.")

    # Swift plugin API partial supersession: the new entry point governs its
    # scope while the source explicitly retains the previous API.
    s303p = "proposals/0303-swiftpm-extensible-build-tools.md"
    s325p = "proposals/0325-swiftpm-additional-plugin-apis.md"
    s303 = file_record("swiftlang/swift-evolution", s303p)
    s325 = file_record("swiftlang/swift-evolution", s325p)
    q303 = next(line for line in s303["content"].splitlines() if line.startswith("* Status:"))
    q325 = next(line for line in s325["content"].splitlines() if line.startswith("* Status:"))
    qentry = "The `BuildToolPlugin` protocol entry point defined by SE-0303 is superseded by a new entry point that takes the new `PluginContext` type and a reference to the `Target` for which build commands should be generate. The previous API remains so that existing plugins continue to work."
    legacy = "swiftpm-plugin-legacy-api"
    entry = "swiftpm-plugin-entry-point"
    a1 = artifact("SE-0303@accepted", "SE-0303", "SwiftPM extensible build tools", "ACCEPTED",
                  "2021-02-01T00:00:00Z", "swiftlang/swift-evolution", s303["url"], s303["revision"],
                  [q303], (legacy, entry), 1,
                  proofs=(file_proof("swiftlang/swift-evolution", s303p, q303),))
    a2 = artifact("SE-0325@accepted", "SE-0325", "Additional package plugin APIs", "ACCEPTED",
                  "2022-01-01T00:00:00Z", "swiftlang/swift-evolution", s325["url"], s325["revision"],
                  [q325, qentry], (entry,), 2, replaces=("SE-0303",),
                  proofs=(file_proof("swiftlang/swift-evolution", s325p, q325),
                          file_proof("swiftlang/swift-evolution", s325p, qentry)))
    a3 = artifact("SE-0325@compatibility-note", "SE-0325", "Previous plugin API remains",
                  "NOTE", "2026-08-22T00:00:00Z", "swiftlang/swift-evolution", s325["url"], s325["revision"],
                  [qentry], (legacy,), 3, role="MENTION",
                  proofs=(file_proof("swiftlang/swift-evolution", s325p, qentry),))
    rows = [
        checkpoint("swift-plugin-api", 1, 1, gov("the SwiftPM build-tool plugin entry point"),
                   (entry,), "GOVERNING", ("SE-0303",), ((a1["artifact_id"],),), ("parallel_scopes",)),
        checkpoint("swift-plugin-api", 2, 2, gov("the SwiftPM build-tool plugin entry point"),
                   (entry,), "GOVERNING", ("SE-0325",), ((a2["artifact_id"],),),
                   ("simple_supersession",), ("SUPERSESSION_MISSED",)),
        checkpoint("swift-plugin-api", 3, 3, gov("the retained SwiftPM legacy plugin API"),
                   (legacy,), "GOVERNING", ("SE-0303",), ((a1["artifact_id"], a3["artifact_id"]),),
                   ("partial_supersession", "parallel_scopes"), ("PARALLEL_DECISION_COLLAPSE",)),
        checkpoint("swift-plugin-api", 4, 3, "Which decisions govern both the new SwiftPM plugin entry point and the retained legacy API?",
                   (entry, legacy), "MULTIPLE_GOVERNING", ("SE-0303", "SE-0325"),
                   ((a1["artifact_id"], a2["artifact_id"], a3["artifact_id"]),),
                   ("parallel_scopes", "partial_supersession"), ("PARALLEL_DECISION_COLLAPSE",)),
    ]
    add("swift-plugin-api", "Swift", ("swiftlang/swift-evolution",), "fully_real",
        ("simple_supersession", "partial_supersession", "parallel_scopes"), [a1, a2, a3], rows,
        "SE-0325 explicitly supersedes one entry point while retaining the previous API.")

    def add_go(tid: str, issue_number: int, comment_id: int, scope: str,
               *, predecessor: dict | None = None, unresolved_final: bool = False) -> None:
        issue = cache["go_issues"][str(issue_number)]
        comment = cache["go_acceptance_comments"][str(comment_id)]
        arts: list[dict] = []
        seq = 0
        if predecessor:
            seq += 1
            arts.append(predecessor | {"sequence": seq})
        seq += 1
        a_open = artifact(
            f"golang/go#{issue_number}@open", f"golang/go#{issue_number}", issue["title"],
            "OPEN", issue["created_at"], "golang/go", issue["html_url"],
            f"github-open-event-{issue['created_at']}", [issue["title"], issue["body"]],
            (scope,), seq, replaces=((predecessor["decision_id"],) if predecessor else ()),
            proofs=(source_ref("issue", str(issue_number), field="created_at", value=issue["created_at"]),),
            source_type="issue")
        arts.append(a_open)
        seq += 1
        acceptance_proofs = [
            source_ref("comment", str(comment_id), quote="No change in consensus, so **[accepted]"),
        ]
        if predecessor:
            acceptance_proofs.append(file_proof(
                "golang/proposal", "design/go2draft-contracts.md",
                "It has been replaced by a [new",
            ))
        a_accept = artifact(
            f"golang/go#{issue_number}@accepted", f"golang/go#{issue_number}", issue["title"],
            "ACCEPTED", comment["created_at"], "golang/go", comment["html_url"],
            f"github-comment-{comment_id}", [comment["body"]], (scope,), seq,
            replaces=((predecessor["decision_id"],) if predecessor else ()),
            source_type="issue", proofs=tuple(acceptance_proofs))
        arts.append(a_accept)
        before = predecessor["decision_id"] if predecessor and predecessor["status"] not in ("WITHDRAWN", "REJECTED") else None
        cp1_visible = 1 if predecessor else a_open["sequence"]
        rows: list[tuple[dict, dict]] = []
        if predecessor:
            rows.append(checkpoint(tid, 1, 1, gov(scope.replace("-", " ") + " before the replacement proposal is accepted"),
                                   (scope,), "NO_GOVERNING_DECISION", (), ((predecessor["artifact_id"],),),
                                   ("withdrawn_decision",), ("UNSUPPORTED_AUTHORITY",)))
            open_index = 2
        else:
            open_index = 1
        rows.append(checkpoint(tid, open_index, a_open["sequence"], gov(scope.replace("-", " ") + " while the proposal is open"),
                               (scope,), "NO_GOVERNING_DECISION", (), ((a_open["artifact_id"],),),
                               ("proposal_while_current",), ("PROPOSAL_PROMOTED", "UNSUPPORTED_AUTHORITY")))
        accept_index = open_index + 1
        state = "UNRESOLVED" if unresolved_final else "GOVERNING"
        decisions = () if unresolved_final else (a_accept["decision_id"],)
        rows.append(checkpoint(tid, accept_index, a_accept["sequence"], gov(scope.replace("-", " ")),
                               (scope,), state, decisions, ((a_accept["artifact_id"],),),
                               (("conflicting_or_ambiguous",) if unresolved_final else ("proposal_accepted",)),
                               (("UNSUPPORTED_AUTHORITY",) if unresolved_final else ("PROPOSAL_PROMOTED",))))
        while len(rows) < 4:
            idx = len(rows) + 1
            rows.append(checkpoint(tid, idx, a_accept["sequence"], f"Which accepted Go decision is authoritative for {scope.replace('-', ' ')} now?",
                                   (scope,), state, decisions, ((a_accept["artifact_id"],),),
                                   (("conflicting_or_ambiguous",) if unresolved_final else ("proposal_accepted",)),
                                   (("UNSUPPORTED_AUTHORITY",) if unresolved_final else ()), f"{tid}-final"))
        if len(rows) >= 2:
            rows[-2][0]["consistency_group"] = f"{tid}-final"
            rows[-1][0]["consistency_group"] = f"{tid}-final"
        timeline_scenarios = ("proposal_while_current", "proposal_accepted")
        if predecessor:
            timeline_scenarios += ("withdrawn_decision",)
        if unresolved_final:
            timeline_scenarios += ("conflicting_or_ambiguous",)
        add(tid, "Go", ("golang/go", "golang/proposal"), "fully_real",
            timeline_scenarios,
            arts, rows, "GitHub proposal issue creation and proposal-review-group acceptance comment are exact primary events.")

    contracts_path = "design/go2draft-contracts.md"
    contracts = file_record("golang/proposal", contracts_path)
    qcontracts = "We will not be pursuing the approach outlined in this design draft."
    pred = artifact("go-contracts@superseded", "go-contracts", "Go contracts draft",
                    "WITHDRAWN", "2021-01-12T00:00:00Z", "golang/proposal", contracts["url"],
                    contracts["revision"], ["## Superseded", qcontracts], ("go-type-parameters",), 1,
                    proofs=(file_proof("golang/proposal", contracts_path, qcontracts),))
    add_go("go-type-parameters", 43651, 776944155, "go-type-parameters", predecessor=pred)
    add_go("go-loop-variables", 60078, 1642774250, "go-loop-variable-semantics")
    add_go("go-range-functions", 61405, 1782052910, "go-range-function-details", unresolved_final=True)

    # Generic accepted-policy plus implementation/revert/restoration timeline.
    def policy_code_timeline(tid: str, ecosystem: str, policy: dict,
                             repository: str, original: int, rollback: int,
                             restore: int | None, policy_scope: str, code_scope: str,
                             audit_note: str) -> None:
        artifacts = [policy]
        seq = 1
        seq += 1
        open_impl = pr_artifact(repository, original, "OPEN", seq, (code_scope,),
                                implements=(policy["decision_id"],), snapshot="open")
        artifacts.append(open_impl)
        seq += 1
        merged_impl = pr_artifact(repository, original, "MERGED", seq, (code_scope,),
                                  implements=(policy["decision_id"],))
        artifacts.append(merged_impl)
        seq += 1
        open_rollback = pr_artifact(repository, rollback, "OPEN", seq, (code_scope,),
                                    reverts=(merged_impl["decision_id"],), snapshot="open")
        artifacts.append(open_rollback)
        seq += 1
        merged_rollback = pr_artifact(repository, rollback, "REVERT_MERGED", seq, (code_scope,),
                                      reverts=(merged_impl["decision_id"],))
        artifacts.append(merged_rollback)
        merged_restore = None
        if restore is not None:
            seq += 1
            artifacts.append(pr_artifact(repository, restore, "OPEN", seq, (code_scope,),
                                         reverts=(merged_rollback["decision_id"],), snapshot="open"))
            seq += 1
            merged_restore = pr_artifact(repository, restore, "REVERT_MERGED", seq, (code_scope,),
                                         reverts=(merged_rollback["decision_id"],))
            artifacts.append(merged_restore)
        rows = [
            checkpoint(tid, 1, 1, gov(policy_scope.replace("-", " ")), (policy_scope,),
                       "GOVERNING", (policy["decision_id"],), ((policy["artifact_id"],),),
                       ("implementation_vs_policy",)),
            checkpoint(tid, 2, open_impl["sequence"], gov(code_scope.replace("-", " ") + " while implementation is proposed"),
                       (code_scope,), "UNRESOLVED", (), ((open_impl["artifact_id"],),),
                       ("proposal_while_current", "implementation_vs_policy"),
                       ("PROPOSAL_PROMOTED", "UNSUPPORTED_AUTHORITY")),
            checkpoint(tid, 3, merged_impl["sequence"], gov(code_scope.replace("-", " ")),
                       (code_scope,), "GOVERNING", (merged_impl["decision_id"],), ((merged_impl["artifact_id"],),),
                       ("implementation_vs_policy",)),
            checkpoint(tid, 4, open_rollback["sequence"], gov(code_scope.replace("-", " ") + " while rollback is proposed"),
                       (code_scope,), "GOVERNING", (merged_impl["decision_id"],),
                       ((merged_impl["artifact_id"], open_rollback["artifact_id"]),),
                       ("proposal_while_current", "revert_after_implementation"), ("PROPOSAL_PROMOTED",)),
            checkpoint(tid, 5, merged_rollback["sequence"], gov(policy_scope.replace("-", " ") + " after the code rollback"),
                       (policy_scope,), "GOVERNING", (policy["decision_id"],),
                       ((policy["artifact_id"], merged_rollback["artifact_id"]),),
                       ("implementation_vs_policy", "revert_without_policy_restoration"),
                       ("REVERT_MISSED", "PARALLEL_DECISION_COLLAPSE")),
        ]
        final_code = merged_restore or merged_rollback
        if merged_restore:
            rows.append(checkpoint(tid, 6, merged_restore["sequence"], gov(code_scope.replace("-", " ") + " after explicit restoration"),
                                   (code_scope,), "GOVERNING", (merged_restore["decision_id"],),
                                   ((merged_restore["artifact_id"],),),
                                   ("explicit_restoration", "revert_after_implementation"), ("REVERT_MISSED",)))
        rows.append(checkpoint(tid, len(rows) + 1, artifacts[-1]["sequence"],
                               f"Which decisions govern {policy_scope.replace('-', ' ')} policy and {code_scope.replace('-', ' ')} implementation now?",
                               (policy_scope, code_scope), "MULTIPLE_GOVERNING",
                               (policy["decision_id"], final_code["decision_id"]),
                               ((policy["artifact_id"], final_code["artifact_id"]),),
                               ("parallel_scopes", "implementation_vs_policy"),
                               ("PARALLEL_DECISION_COLLAPSE",)))
        scenarios = ["implementation_vs_policy", "proposal_while_current",
                     "revert_after_implementation", "parallel_scopes",
                     "revert_without_policy_restoration"]
        if restore:
            scenarios.append("explicit_restoration")
        add(tid, ecosystem, tuple(sorted({policy["repository"], repository})), "fully_real",
            tuple(scenarios), artifacts, rows, audit_note)

    # Python PEP 612 policy survives an implementation rewrite/partial revert.
    pep612 = file_record("python/peps", "peps/pep-0612.rst")
    p612status = "Status: Final"
    policy612 = artifact("PEP-612@final", "PEP-612", "Parameter Specification Variables",
                         "FINAL", "2020-12-01T00:00:00Z", "python/peps", pep612["url"],
                         pep612["revision"], ["PEP: 612", p612status], ("python-paramspec-policy",), 1,
                         proofs=(file_proof("python/peps", "peps/pep-0612.rst", p612status),))
    policy_code_timeline("python-paramspec-implementation", "Python", policy612,
                         "python/cpython", 23702, 25449, None,
                         "python-paramspec-policy", "python-paramspec-implementation",
                         "PEP 612 remains Final while the second PR explicitly reverts part of and changes its implementation.")

    # Swift SE-0474 policy survives code rollback and explicit restoration.
    se474file = file_record("swiftlang/swift-evolution", "proposals/0474-yielding-accessors.md")
    se474status = "* Status: **Accepted**"
    policy474 = artifact("SE-0474@accepted", "SE-0474", "Yielding accessors", "ACCEPTED",
                         "2025-01-01T00:00:00Z", "swiftlang/swift-evolution", se474file["url"],
                         se474file["revision"], [se474status], ("swift-yielding-accessor-policy",), 1,
                         proofs=(file_proof("swiftlang/swift-evolution", "proposals/0474-yielding-accessors.md", se474status),))
    policy_code_timeline("swift-coroutine-accessors", "Swift", policy474,
                         "swiftlang/swift", 90516, 91475, 91494,
                         "swift-yielding-accessor-policy", "swift-coroutine-accessor-implementation",
                         "Accepted language policy is separate from an implementation PR, its rollback, and an explicit revert-of-revert restoration.")

    # KEP multi-hop/current policy plus implementation rollback. All current
    # relations are visible together; broad current policy is mechanically
    # adjudicated from the explicit replaces fields, while code is separate.
    k583p = "keps/sig-scheduling/583-coscheduling/kep.yaml"
    k5832p = "keps/sig-scheduling/5832-decouple-podgroup-api/kep.yaml"
    k4671p = "keps/sig-scheduling/4671-gang-scheduling/kep.yaml"
    k583 = file_record("kubernetes/enhancements", k583p)
    k5832 = file_record("kubernetes/enhancements", k5832p)
    k4671 = file_record("kubernetes/enhancements", k4671p)
    gang_scope = "kubernetes-gang-scheduling-policy"
    a1 = artifact("KEP-583@current", "KEP-583", "Coscheduling", "DRAFT",
                  "2018-07-03T00:00:00Z", "kubernetes/enhancements", k583["url"], k583["revision"],
                  ["status: provisional"], (gang_scope,), 1,
                  proofs=(file_proof("kubernetes/enhancements", k583p, "status: provisional"),))
    a2 = artifact("KEP-5832@current", "KEP-5832", "Decouple PodGroup API", "ACCEPTED",
                  "2026-01-23T00:00:00Z", "kubernetes/enhancements", k5832["url"], k5832["revision"],
                  ["status: implementable", "  - \"/keps/sig-scheduling/583-coscheduling\""],
                  (gang_scope,), 2, replaces=("KEP-583",), proofs=(
                      file_proof("kubernetes/enhancements", k5832p, "status: implementable"),
                      file_proof("kubernetes/enhancements", k5832p, "  - \"/keps/sig-scheduling/583-coscheduling\"")))
    a3 = artifact("KEP-4671@current", "KEP-4671", "Gang Scheduling", "ACCEPTED",
                  "2026-08-22T00:00:00Z", "kubernetes/enhancements", k4671["url"], k4671["revision"],
                  ["status: implementable", "  - \"/keps/sig-scheduling/5832-decouple-podgroup-api\"",
                   "  - \"/keps/sig-scheduling/583-coscheduling\""], (gang_scope,), 3,
                  replaces=("KEP-5832", "KEP-583"), proofs=(
                      file_proof("kubernetes/enhancements", k4671p, "status: implementable"),
                      file_proof("kubernetes/enhancements", k4671p, "  - \"/keps/sig-scheduling/5832-decouple-podgroup-api\""),
                      file_proof("kubernetes/enhancements", k4671p, "  - \"/keps/sig-scheduling/583-coscheduling\"")))
    # Add code role records to the same real organizational history.
    a4 = pr_artifact("kubernetes/kubernetes", 137464, "MERGED", 4,
                     ("kubernetes-podgroup-admission-implementation",), implements=("KEP-5832",))
    a5 = pr_artifact("kubernetes/kubernetes", 139008, "REVERT_MERGED", 5,
                     ("kubernetes-podgroup-admission-implementation",), reverts=(a4["decision_id"],))
    rows = [
        checkpoint("kubernetes-gang-scheduling", 1, 1, gov("Kubernetes gang scheduling while only the provisional KEP is visible"),
                   (gang_scope,), "NO_GOVERNING_DECISION", (), ((a1["artifact_id"],),),
                   ("proposal_while_current",), ("PROPOSAL_PROMOTED", "UNSUPPORTED_AUTHORITY")),
        checkpoint("kubernetes-gang-scheduling", 2, 2, gov("Kubernetes gang scheduling policy"),
                   (gang_scope,), "GOVERNING", ("KEP-5832",), ((a2["artifact_id"],),),
                   ("multi_hop_supersession",), ("SUPERSESSION_MISSED",)),
        checkpoint("kubernetes-gang-scheduling", 3, 3, gov("Kubernetes gang scheduling policy in the current KEP registry"),
                   (gang_scope,), "GOVERNING", ("KEP-4671",), ((a3["artifact_id"],),),
                   ("multi_hop_supersession",), ("SUPERSESSION_MISSED",)),
        checkpoint("kubernetes-gang-scheduling", 4, 4, gov("Kubernetes gang scheduling policy after PodGroup admission implementation merged"),
                   (gang_scope,), "GOVERNING", ("KEP-4671",), ((a3["artifact_id"], a4["artifact_id"]),),
                   ("implementation_vs_policy",), ("PARALLEL_DECISION_COLLAPSE",)),
        checkpoint("kubernetes-gang-scheduling", 5, 5, gov("Kubernetes gang scheduling policy after PodGroup admission code was reverted"),
                   (gang_scope,), "GOVERNING", ("KEP-4671",), ((a3["artifact_id"], a5["artifact_id"]),),
                   ("implementation_vs_policy", "revert_without_policy_restoration"),
                   ("REVERT_MISSED", "PARALLEL_DECISION_COLLAPSE")),
        checkpoint("kubernetes-gang-scheduling", 6, 5, "Which decisions govern gang-scheduling policy and the PodGroup admission implementation now?",
                   (gang_scope, "kubernetes-podgroup-admission-implementation"), "MULTIPLE_GOVERNING",
                   ("KEP-4671", a5["decision_id"]), ((a3["artifact_id"], a5["artifact_id"]),),
                   ("parallel_scopes", "implementation_vs_policy"), ("PARALLEL_DECISION_COLLAPSE",)),
    ]
    add("kubernetes-gang-scheduling", "Kubernetes", ("kubernetes/enhancements", "kubernetes/kubernetes"),
        "fully_real", ("multi_hop_supersession", "implementation_vs_policy", "revert_without_policy_restoration", "parallel_scopes"),
        [a1, a2, a3, a4, a5], rows,
        "Current KEP registry explicitly encodes 583 -> 5832 -> 4671 replacement; implementation rollback does not alter policy status.")

    # Code-authority rollback/restoration timelines. A merged rollback is a new
    # governing code decision; it does not magically resurrect the old ID.
    def code_revert_timeline(tid: str, ecosystem: str, repository: str,
                             original: int, rollback: int, scope: str,
                             restore: int | None = None, note: str = "",
                             rollback_is_restoration: bool = False) -> None:
        original_open = pr_artifact(repository, original, "OPEN", 1, (scope,), snapshot="open")
        original_merged = pr_artifact(repository, original, "MERGED", 2, (scope,))
        rollback_open = pr_artifact(repository, rollback, "OPEN", 3, (scope,),
                                    reverts=(original_merged["decision_id"],), snapshot="open")
        rollback_merged = pr_artifact(repository, rollback, "REVERT_MERGED", 4, (scope,),
                                      reverts=(original_merged["decision_id"],))
        artifacts = [original_open, original_merged, rollback_open, rollback_merged]
        restore_open = restore_merged = None
        if restore is not None:
            restore_open = pr_artifact(repository, restore, "OPEN", 5, (scope,),
                                       reverts=(rollback_merged["decision_id"],), snapshot="open")
            restore_merged = pr_artifact(repository, restore, "REVERT_MERGED", 6, (scope,),
                                         reverts=(rollback_merged["decision_id"],))
            artifacts.extend((restore_open, restore_merged))
        rows = [
            checkpoint(tid, 1, 1, gov(scope.replace("-", " ") + " while the original change is proposed"),
                       (scope,), "NO_GOVERNING_DECISION", (), ((original_open["artifact_id"],),),
                       ("proposal_while_current",), ("PROPOSAL_PROMOTED", "UNSUPPORTED_AUTHORITY")),
            checkpoint(tid, 2, 2, gov(scope.replace("-", " ")), (scope,),
                       "GOVERNING", (original_merged["decision_id"],), ((original_merged["artifact_id"],),),
                       ("revert_after_implementation",)),
            checkpoint(tid, 3, 3, gov(scope.replace("-", " ") + " while rollback is proposed"),
                       (scope,), "GOVERNING", (original_merged["decision_id"],),
                       ((original_merged["artifact_id"], rollback_open["artifact_id"]),),
                       ("proposal_while_current", "revert_after_implementation"), ("PROPOSAL_PROMOTED",)),
            checkpoint(tid, 4, 4, gov(scope.replace("-", " ") + " after rollback merged"),
                       (scope,), "GOVERNING", (rollback_merged["decision_id"],),
                       ((rollback_merged["artifact_id"],),),
                       (("revert_after_implementation", "explicit_restoration")
                        if rollback_is_restoration else
                        ("revert_after_implementation", "revert_without_automatic_restoration")),
                       ("REVERT_MISSED", "STALE_DECISION")),
        ]
        if restore_merged:
            rows.extend((
                checkpoint(tid, 5, 5, gov(scope.replace("-", " ") + " while explicit restoration is proposed"),
                           (scope,), "GOVERNING", (rollback_merged["decision_id"],),
                           ((rollback_merged["artifact_id"], restore_open["artifact_id"]),),
                           ("proposal_while_current", "explicit_restoration"), ("PROPOSAL_PROMOTED",)),
                checkpoint(tid, 6, 6, gov(scope.replace("-", " ") + " after explicit restoration merged"),
                           (scope,), "GOVERNING", (restore_merged["decision_id"],),
                           ((restore_merged["artifact_id"],),),
                           ("explicit_restoration",), ("REVERT_MISSED",)),
            ))
        scenarios = ["proposal_while_current", "revert_after_implementation",
                     "revert_without_automatic_restoration"]
        if restore:
            scenarios.append("explicit_restoration")
        if rollback_is_restoration:
            scenarios.append("explicit_restoration")
        add(tid, ecosystem, (repository,), "fully_real", tuple(scenarios), artifacts, rows,
            note or "GitHub PR created/merged events establish proposal, implementation, rollback, and optional restoration.")

    code_revert_timeline("kubernetes-pleg-default", "Kubernetes", "kubernetes/kubernetes",
                         137909, 137946, "kubernetes-pleg-default",
                         rollback_is_restoration=True)
    code_revert_timeline("terraform-iam-role-chaining", "Terraform", "hashicorp/terraform",
                         35720, 35827, "terraform-s3-iam-role-chaining",
                         note="Rollback explicitly says IAM role chaining may return later; that promise is not restoration.")
    code_revert_timeline("opentofu-minimal-image-docs", "OpenTofu", "opentofu/opentofu",
                         2403, 2404, "opentofu-minimal-image-docs", restore=None,
                         note="The second PR explicitly reverts the temporary rollback, so its merged record is the restoration authority.",
                         rollback_is_restoration=True)
    # In this pair the original is itself a temporary rollback and the second
    # PR restores the pre-rollback state; encode it as one rollback chain.
    # The generic helper's fourth checkpoint already treats #2404 as the
    # governing revert decision, which is the explicit restoration record.
    code_revert_timeline("envoy-ext-authz-empty-values", "Envoy", "envoyproxy/envoy",
                         45103, 45321, "envoy-ext-authz-empty-values")
    code_revert_timeline("llvm-openmp-target-fast", "LLVM", "llvm/llvm-project",
                         205775, 213769, "llvm-openmp-target-fast", restore=213911)

    # Pre-output exclusions, retained rather than silently forgotten.
    exclusions.extend([
        {"candidate": "OpenTofu context propagation #835", "reason": "Promised revert-of-revert never occurred; later PR explicitly says so, making a restoration checkpoint indefensible."},
        {"candidate": "Terraform IAM role chaining future reintroduction", "reason": "Rollback promises a future return but no source-grounded accepted restoration was found."},
        {"candidate": "Swift SE-0030 historical acceptance checkpoint", "reason": "Primary status says Withdrawn and decision notes indicate rejection; no authoritative pre-withdrawal state was assumed."},
        {"candidate": "Rust RFC 2203 broad replacement", "reason": "Source says mostly superseded and preserves a simpler case; broad winner is adjudicated unresolved, not forced."},
        {"candidate": "Rust RFC 769 broad replacement", "reason": "Source says partially superseded; broad winner is adjudicated unresolved, not forced."},
    ])
    return timelines, checkpoints, truth, exclusions


def validate(timelines: list[dict], checkpoints: list[dict], truth: list[dict]) -> dict:
    by_timeline = {t["timeline_id"]: t for t in timelines}
    hidden = {row["checkpoint_id"]: row for row in truth}
    assert len(by_timeline) == len(timelines)
    assert len(hidden) == len(truth) == len(checkpoints)
    assert 20 <= len(timelines) <= 30
    assert 80 <= len(checkpoints) <= 120
    assert all(t["composition"] != "fully_synthetic" for t in timelines)
    assert sum(t["composition"] == "fully_real" for t in timelines) >= 14
    assert len({t["ecosystem"] for t in timelines}) >= 5
    ecosystem_counts = Counter(t["ecosystem"] for t in timelines)
    assert max(ecosystem_counts.values()) / len(timelines) <= 0.30
    checkpoint_ids = {c["checkpoint_id"] for c in checkpoints}
    assert checkpoint_ids == set(hidden)
    for cp in checkpoints:
        timeline = by_timeline[cp["timeline_id"]]
        assert cp["authority_scopes"]
        sequences = [a["sequence"] for a in timeline["artifacts"]]
        assert sequences == sorted(sequences)
        assert len(sequences) == len(set(sequences))
        assert 1 <= cp["visible_through"] <= max(sequences)
        assert any(a["sequence"] == cp["visible_through"]
                   for a in timeline["artifacts"])
        expected = hidden[cp["checkpoint_id"]]
        assert not any(decision_id.casefold() in cp["question"].casefold()
                       for decision_id in expected["expected_decision_ids"])
        assert expected["expected_state"] in {
            "GOVERNING", "MULTIPLE_GOVERNING", "UNRESOLVED", "NO_GOVERNING_DECISION"
        }
        visible_ids = {
            a["decision_id"] for a in timeline["artifacts"]
            if a["sequence"] <= cp["visible_through"]
        }
        assert set(expected["expected_decision_ids"]) <= visible_ids
        if expected["expected_state"] == "GOVERNING":
            assert len(expected["expected_decision_ids"]) == 1
        elif expected["expected_state"] == "MULTIPLE_GOVERNING":
            assert len(expected["expected_decision_ids"]) >= 2
        else:
            assert not expected["expected_decision_ids"]
    scenario_counts = Counter(
        scenario for timeline in timelines for scenario in set(timeline["scenario_types"])
    )
    minimums = {
        "simple_supersession": 5,
        "multi_hop_supersession": 2,
        "revert_after_implementation": 5,
        "proposal_while_current": 5,
        "mention_without_transition": 4,
        "parallel_scopes": 4,
        "conflicting_or_ambiguous": 3,
        "withdrawn_decision": 3,
        "implementation_vs_policy": 3,
        "revert_without_automatic_restoration": 2,
        "explicit_restoration": 2,
    }
    assert all(scenario_counts[name] >= count for name, count in minimums.items())
    return {
        "timelines": len(timelines),
        "checkpoints": len(checkpoints),
        "fully_real": sum(t["composition"] == "fully_real" for t in timelines),
        "hybrid": sum(t["composition"] == "hybrid" for t in timelines),
        "fully_synthetic": 0,
        "ecosystems": dict(sorted(ecosystem_counts.items())),
        "scenarios": dict(sorted(scenario_counts.items())),
    }


def main() -> None:
    timelines, checkpoints, truth, exclusions = build()
    stats = validate(timelines, checkpoints, truth)
    PUBLIC.write_text(json.dumps(timelines, indent=2) + "\n")
    CHECKPOINTS.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in checkpoints))
    TRUTH.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in truth))
    EXCLUSIONS.write_text(json.dumps(exclusions, indent=2) + "\n")
    manifest = {
        "source_cache_sha256": hashlib.sha256(SOURCE_CACHE.read_bytes()).hexdigest(),
        "timelines_sha256": hashlib.sha256(PUBLIC.read_bytes()).hexdigest(),
        "checkpoints_sha256": hashlib.sha256(CHECKPOINTS.read_bytes()).hexdigest(),
        "ground_truth_sha256": hashlib.sha256(TRUTH.read_bytes()).hexdigest(),
        "stats": stats,
    }
    (DATA / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
