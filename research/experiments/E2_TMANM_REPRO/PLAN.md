# E2 — Plan

## Question

Does TMA-NM (arXiv:2606.24322), the strongest prior-art threat to novelty
identified in `research/RELATED_WORK_AUDIT.md`, have a real released
implementation that (1) exists at a verifiable primary-source location,
(2) corresponds to the cited paper, (3) is reproducible, (4) runs, (5)
implements laundering attacks relevant to Custody, and (6) could feasibly
be adapted to test current Custody — evidence collection and reproduction
only, no adapter built, no new benchmark, no architecture work.

## Why this precedes E4 (a new benchmark)

E0/E1 established Custody's derivation graph can faithfully represent a
*known* multi-parent ancestry. The next open question is whether Custody's
still-unfixed weakness — exact-content-hash/structural matching, not
laundering-resistant — is already directly testable by reusing someone
else's harness, rather than building a new one from scratch. Building a
benchmark before checking this would risk duplicating work that already
exists, or worse, building a weaker version of it.

## Method

1. Verify TMA-NM's primary-source metadata directly from arXiv (not a
   secondary summary).
2. Locate and verify any released code via the paper's own text (PDF, not
   just the abstract page, since arXiv abstract pages often omit in-body
   links).
3. Independently confirm any found repository exists via the GitHub API
   (`gh api`), not an AI-summarized page render, to rule out a hallucinated
   or unrelated same-named repo.
4. Clone outside the Custody source tree, pin the exact commit, do not
   modify.
5. Read `requirements.txt`/README for dependencies, runtime, credentials,
   cost, and hardware requirements before running anything.
6. Attempt the smallest reproduction command(s) that require no API key
   and no spend — record exact output.
7. Read (not run, since running costs money we are not authorized to
   spend) the source of every attack-scenario-generating script to
   classify the A-J attack taxonomy against actual code, and separately
   note the authors' own already-logged `results/*.json` as self-reported
   (not independently re-run) empirical evidence.
8. Build the adapter feasibility map for every attack found IMPLEMENTED,
   without writing any adapter code.
9. Render one verdict: EXTERNAL-HARNESS-READY / -PARTIAL / -BLOCKED /
   -ABSENT.

## Explicit non-goals for this experiment

No OPENROUTER_API_KEY will be obtained or used. No LLM API spend. No
adapter code written. No new Custody code. No new benchmark. No trust
epochs. No claim that Custody is or is not novel relative to TMA-NM beyond
what this repository's actual code demonstrates.
