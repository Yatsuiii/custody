# Extractor v2 freeze record

Frozen before any holdout read, per session contract Phase 9.

Frozen files (hashes in `ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE_SHA256.txt`):
- `app/action_compliance_extraction_v2.py` — extraction prompt, schema,
  normalization, and record parsing (source of truth for the prompt text;
  not duplicated here to avoid drift between two copies).
- `scripts/run_action_compliance_bundle_ingestion_v2.py` — freezer/runner,
  identical to the v1 freezer except it imports v2.
- `app/tests/test_action_compliance_extraction_v2.py` — offline unit tests
  (no model calls), all passing at freeze time.

Model/config: same Vertex/Gemini client as v1 (`vertex.py`,
`GEN_MODEL = "gemini-3.7-flash"`, project/location unchanged), called via
`vertex.generate`, no temperature/sampling override — identical calling
convention to the frozen v1 extractor, so the only variable under test is
the prompt/schema/normalization change.

Confirmed unchanged (re-verified against `ACTION_COMPLIANCE_RUN_MANIFEST_SHA256.txt`
immediately before this freeze): `app/authority.py` (resolver),
`app/ingest.py` (v1 extractor), `app/bundle_source.py` (transport),
`app/action_compliance_context.py` (context assembler), and all seven
`data/action_compliance/bundle_inputs/*` bundles.

Development-gate result (from `data/action_compliance/dev_v2_runs/`, five
dev-corpus bundles per `EXTRACTION_DEV_CORPUS.md`): PASS. Full gate
definition and per-bundle results are in
`ACTION_COMPLIANCE_EXTRACTION_V2_REPORT.md` §§ dev metrics / gate.

No dev result was used to hand-tune this frozen prompt after the fact —
the dev run above was performed against this exact frozen file content
(hashes match the dev run's git-tree state; `git diff` on
`app/action_compliance_extraction_v2.py` between the dev run and this
freeze is empty by construction, since both happened in the same
uncommitted working-tree edit with no further changes in between).

After this point: no further prompt edits, no per-task fixes, no retries,
before or during the one-shot holdout run in
`data/action_compliance/holdout_v2_runs/`.
