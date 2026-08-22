# Deterministic grader correction

Applied after the one permitted intervention run. No model response, answer
key, case, threshold, prompt, or governing-accuracy rule changed.

The first report implementation counted `revert_miss_rate` and
`supersession_miss_rate` only when that label was the row's *primary failure*.
The preregistration defines those as applicability metrics: every incorrect
answer at a revert- or supersession-applicable checkpoint belongs in the
numerator, including an incorrect abstention. The implementation now follows
that definition.

The same audit fixed two classification details:

- proposal status is taken from the latest visible snapshot of a decision,
  rather than any earlier draft snapshot;
- false-authority counts any incorrect `GOVERNING` assertion, including a
  withdrawn/rejected record, rather than only assertions where the expected
  state was non-governing.

These changes affect error-taxonomy rates only. Baseline authority accuracy
remains DecisionTrace 47/61 and RAG 52/61; post-intervention authority accuracy
remains 61/61.
