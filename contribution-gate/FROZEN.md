# Frozen 2026-08-16

Not abandoned, not resumed. Closed research, not part of the Custody
submission.

**The thesis.** An agent opening pull requests against open-source projects
would violate contribution policy — banned AI contributions, required
disclosure, required human handoff — so a gate enforcing those policies before
any write would be necessary.

**Why it stopped: DROP, and the falsifier was decisive.** Nine real policies
(Home Assistant, Zig, Bevy and Alacritty ban AI contributions; Linux, Django
and Kubernetes require disclosure; NumPy and GDAL require handoff), four
conditions, a fully mocked write surface so no third-party repository was ever
touched.

Refusal rate **1.000**. Gemini 3.7 refused every banned-policy instance
unprompted. With the `refuse` action removed entirely, it opened **zero** PRs
anyway. There is no failure to gate. The product's premise was a weakness the
model does not have.

The secondary finding is the more general one, and it recurred later: the fix
that *would* be needed belongs in the tool layer, and "it should be a library"
is not a submission.
