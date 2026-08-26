# Action-compliance bundle-ingestion audit

Date: 2026-08-23  
Scope: transport substitution only; no authority-semantic changes

## Existing live path

`app/ingest.py::ingest_repo()` has two source transports:

1. `discover_revert_pairs()` calls `gh_json()` to search merged GitHub PRs,
   fetches the candidate/referenced original, and returns PR metadata plus
   source text.
2. `discover_kep_alternatives()` calls `gh_json()` for code search and
   contents, decodes the fetched file, and returns a source section.

Both paths hand source text to `extract_decision_fields()`, which calls the
existing `vertex.generate()` Gemini client. The model extracts subject,
context, chosen approach, rejected alternatives, rationale, a verbatim
rationale quote, and constraints. `_verify_quote()` independently checks the
quote against the fetched source text; a failed quote becomes insufficient
evidence rather than a fabricated claim.

## Deterministic construction in the current path

The existing channel adapters, not the resolver, construct lifecycle fields:

- `_fetch_revert_candidate()` gets merged-at metadata, original/revert PR
  numbers, titles, URLs, and raw body from GitHub.
- `revert_pair_to_decisions()` creates an `IMPLEMENTED` original and a
  `REVERTED` record with a `REVERTS` edge to the original. IDs are derived from
  repository and PR numbers. The same repository/PR scope is assigned as a
  related component by the older loader path.
- `kep_to_decision()` creates an `ACCEPTED` record from the KEP alternative
  section. It does not invent a supersession edge.
- `introduced_at` comes from GitHub `mergedAt` for revert originals; KEP
  records have no inferred lifecycle timestamp.
- policy/implementation role is not a field on `Decision`; the resolver
  derives implementation role from explicit `IMPLEMENTS` edges.
- `SUPERSEDES`, `REVERTS`, `REAFFIRMS`, and other relationship edges are
  represented by `Decision.related_decisions` and consumed by `graph.py`.

`authority.py` then filters exact `related_components` scope, classifies
status/implementation eligibility, replays lifecycle edges through
`DecisionGraph`, and returns the frozen `AuthorityProof`. It does not fetch
sources or ask Gemini.

## Coupling and minimum substitution boundary

The live path couples transport and interpretation in the two channel
adapters. A bundle transport cannot safely call those channel constructors:
their hard-coded `IMPLEMENTED`/`REVERTED`/`ACCEPTED` assignments would be
benchmark-specific assumptions. The minimum fair boundary is therefore:

```text
SourceBundle -> generic source-artifact prompt -> existing Vertex/Gemini
quote-verification discipline -> Decision records -> frozen resolver
```

`app/bundle_source.py` now owns only `BundleArtifact` transport metadata and
the neutral local allowlist. `extract_bundle_decisions()` in `app/ingest.py`
uses the same `vertex.generate()` client and `_verify_quote()` primitive, but
asks the model to report status, scope, role, and explicit relationships from
the source text. IDs are generated from neutral artifact identity and record
position; model-provided IDs are ignored. Invalid or unsupported fields are
recorded as failures or uncertainty, never repaired from benchmark metadata.

## Input boundary

The bundle adapter accepts exactly `requested_change.txt` and
`artifacts/artifact_NNN.md`. It rejects all other paths. The machine-readable
allow/deny policy is `ACTION_COMPLIANCE_BUNDLE_INPUT_POLICY.json`. The
preparation script may read a fixture's `TASK.md` solely to extract the
literal requested-change block; the runtime adapter never sees that file.

## Deliberate limitations

- The generic extractor can fail to produce a status, scope, role, or edge.
  Such a failure remains in the generated result and can lead to an
  unresolved proof.
- The adapter does not inspect filenames for authority. Neutral artifact IDs
  are the only local identity exposed to extraction.
- No task slug, category, ledger field, grader, sanity patch, or expected
  decision ID is referenced by adapter/extractor code.
- The frozen resolver and all hash-frozen authority files are unchanged.
