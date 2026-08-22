# E2 — Source Audit

## Primary paper, verified directly

- **Title (exact)**: "Securing LLM-Agent Long-Term Memory Against
  Poisoning: Non-Malleable, Origin-Bound Authority with Machine-Checked
  Guarantees"
- **Author**: Yedidel Louck (single author)
- **arXiv ID**: 2606.24322, v1 only, submitted Tue 23 Jun 2026 08:57:50
  UTC, 129 KB
- **Category**: cs.CR (Cryptography and Security)
- **Venue**: per the repository's own citation block, "Under review at
  IEEE Transactions on Dependable and Secure Computing" — not yet
  peer-reviewed/accepted anywhere, confirmed from the source, not assumed.
- Verified via a direct `WebFetch` of `arxiv.org/abs/2606.24322` (metadata)
  and `arxiv.org/pdf/2606.24322` (full text scan for links) — not a
  secondary summary or search-engine snippet.

## Released code, verified via ground truth (not AI-summarized page render)

The arXiv abstract page itself carries no code link. The full PDF text
does: a GitHub URL (`github.com/yedidel/mem-inv-bench`) and a HuggingFace
dataset mirror URL. Both were independently confirmed to actually exist,
not just parsed from the PDF summary (which could itself hallucinate a
URL):

- `gh api repos/yedidel/mem-inv-bench` returned a real GitHub API JSON
  object: `created_at: 2026-06-22T16:00:03Z`, `pushed_at:
  2026-06-23T07:35:57Z` — one day before / same day as the paper's arXiv
  submission (23 Jun 2026), a timeline consistent with a genuine
  paper-plus-artifact release, not a mismatched or backdated repo.
  `license: MIT`. `stargazers_count: 1`, `forks: 1` — small numbers
  consistent with a real, low-visibility research artifact rather than an
  established, heavily-used project (expected for a single-author,
  under-review paper), not evidence against authenticity.
- `gh api repos/yedidel/mem-inv-bench/commits` returned 5 real commits,
  all dated 22-23 Jun 2026, with a coherent history (initial harness
  commit → two small fixes/README updates → final README update),
  consistent with a one-time artifact release alongside the paper rather
  than an actively maintained project.
- **Pinned commit for this experiment**: `63f1359d677efbe1a65b982b2a54cabfec97f1e1`
  (the current `main` HEAD at time of audit, "Update README.md", 2026-06-23
  07:35:52 UTC).
- **License**: MIT (`LICENSE` file present, confirmed via `gh api`
  contents listing).
- The repository's own README explicitly states it corresponds to this
  exact paper title (quoted verbatim in `README.md`'s first heading block)
  and reproduces the paper's own citation BibTeX entry
  (`@misc{louck2026nonmalleable, ...}`), matching the author and title
  independently confirmed from arXiv. This is not a same-named unrelated
  repository — content correspondence confirmed directly.

## HuggingFace mirror — flagged, not fully verified

The dataset URL referenced both in the PDF and the README
(`https://huggingface.co/datasets/anonymos-2321135/MEM-INV-Bench`) uses a
namespace (`anonymos-2321135`) that reads as an unclaimed or
placeholder-style username (a misspelling of "anonymous" plus a numeric
suffix, typical of an anonymized-submission artifact link that was not
updated after de-anonymization). This was not independently fetched and
confirmed to load in this audit — it is a secondary mirror of data already
present in the GitHub repo's own `data/` and `results/` directories, which
were directly verified via `gh api`, so nothing in this experiment depends
on the HuggingFace link resolving. Flagged here rather than silently
treated as confirmed.

## What "released implementation" turns out to mean here — important nuance

The repository contains a real, runnable harness (`code/`), real formal
models (`formal/*.tla`), and real previously-logged results
(`results/*.json`). It does **not** contain literal reproductions of
competing systems' own code (not MemLineage's repository, not any
CaMeL/Fides code, not a `trust_score`-defense system pulled from another
paper). The comparator "defenses" (`trust_score`, `lineage`,
`capability_ifc`) are the paper author's own minimal, hand-built stand-ins
instantiating each defense *category* the paper's formal theorem
addresses — confirmed directly by reading `code/laundering.py` and
`code/agent_bench.py` (see `ATTACK_MATRIX.md` and `REPRODUCTION.md` for
the exact code evidence). This is a legitimate, standard way to
empirically witness a formal separation theorem, and the README itself is
explicit about this framing ("MEM-INV-Bench measures five defense
*classes*"). It is a materially different thing from "an official
released implementation of MemLineage that we could point Custody's
output at," and this distinction matters directly for the
`CUSTODY_ADAPTER_MAP.md` feasibility answers below.

## Four "published pipeline" attacks TMA-NM claims to reproduce — not independently verified in this pass

`code/headtohead.py` cites four external attack papers it claims to
reproduce as drop-in scenarios: MemMorph (2605.26154), MemoryGraft
(2512.16962), Trojan Hippo (2605.01970), and "Hijacking Agent Memory"
(2605.29960). An attempt to independently verify these four arXiv IDs via
the arXiv API was rate-limited (HTTP 429) during this session and not
retried, since it is secondary to E2's primary question (verifying TMA-NM
itself, which is independently and thoroughly confirmed above). **This is
an open, flagged gap**: if this experiment's findings are relied on
further, these four IDs should be checked before citing the head-to-head
numbers as validated against real external pipelines rather than the
paper author's own characterization of them.
