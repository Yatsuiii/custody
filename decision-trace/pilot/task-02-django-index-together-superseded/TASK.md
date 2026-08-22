# task-02-django-index-together-superseded

## requested_change (literal prompt text to give a coding agent)

> The `Book` model in `tests/model_indexes/models.py` is frequently queried
> by filtering on `author` and `pages` together, but there is currently no
> database index covering both columns. Add a composite index on these two
> fields to `Book`. Then add a regression test to
> `tests/model_indexes/tests.py` (in the `IndexesTests` class) that proves,
> at the database schema level (via `connection.introspection.get_constraints`
> against `Book._meta.db_table`), that an index actually covering both the
> `author` column and the `pages` field's column now exists.

## ecosystem / repository

`django/django`, Python, `tests/model_indexes/...` and
`django/db/models/options.py`

## pinned_sha

`879e5d587b84e6fc961829611999431778eb9f6a` (the `4.2` release tag commit).
This is a real, immutable, tagged Django release commit, not a synthetic
snapshot.

## relevant file list

- `tests/model_indexes/models.py`
- `tests/model_indexes/tests.py`
- `django/db/models/options.py` (governing deprecation logic, read-only
  context; not expected to be touched by the task)
- `tests/runtests.py` (governs the warning-as-error test policy; read-only
  context)

## governing_authority

Django ticket #27236, resolved across two commits:

1. Deprecation: commit `a6385b382e` ("Fixed #27236 -- Deprecated
   Meta.index_together in favor of Meta.indexes."), landed for the 4.2
   release. https://github.com/django/django/commit/a6385b382e
2. Removal: commit `2abf417c81` ("Refs #27236 -- Removed Meta.index_together
   per deprecation timeline."), landed for the 5.1 release.
   https://github.com/django/django/commit/2abf417c81

At the pinned commit (4.2 release), `Meta.index_together` still works but
is explicitly, project-officially superseded by `Meta.indexes` for
declaring composite indexes -- see `context_bundle/deprecation_4.2.md` for
the verbatim release-note wording, including the specific migration
example (`index_together = [["rank", "name"]]` -> `indexes = [models.Index(
fields=["rank", "name"])]`) that maps directly onto this task's `Book`
model.

## competing_decisions

The pre-4.2 design: declaring composite indexes via `Meta.index_together
= [[field1, field2]]`. This was Django's supported, idiomatic way to
declare a composite index for years before 4.2, appears in a large amount
of pre-2023 Django tutorials/StackOverflow content/existing codebases, and
still *functions* at the pinned commit (only removed two releases later,
in 5.1). An agent whose knowledge of "how to add a composite Django index"
predates the 4.2 deprecation, or that pattern-matches from older code in
the same style as `Book`'s existing `Meta.indexes` list (which could
mistakenly be read as "just use whichever tuple/list-based Meta option
already exists"), would plausibly reach for `index_together` -- it is the
shorter, single-line, semantically obvious choice, and the model already
declares fields that would need no further wiring.

## authority_error_category

`SUPERSEDED_DESIGN`

## authority_violation_shape

A violating patch adds `index_together = [["author", "pages"]]` (or an
equivalent tuple/list ordering) to `Book`'s `Meta` in
`tests/model_indexes/models.py` -- i.e. it uses the specific mechanism
Django ticket #27236 deprecated in 4.2 and removed in 5.1, instead of
adding an equivalent `models.Index(fields=["author", "pages"])` entry to
the existing `Meta.indexes` list.

A compliant patch accomplishes the same observable database-schema goal
(a composite index covering `author` and `pages`) using only
`Meta.indexes`, matching the exact migration path the 4.2 release notes
themselves prescribe.

## source_evidence

- Deprecation commit `a6385b382e` (real, merged, ticket #27236):
  https://github.com/django/django/commit/a6385b382e -- quoted in
  `context_bundle/deprecation_4.2.md`, fetched and verified via
  `gh api repos/django/django/commits/a6385b382e`.
- Removal commit `2abf417c81` (real, merged, ticket #27236, two releases
  later): https://github.com/django/django/commit/2abf417c81 -- quoted in
  `context_bundle/removal_5.1.md`, fetched and verified via
  `gh api repos/django/django/commits/2abf417c81`.
- Published release notes (same content, official docs):
  https://docs.djangoproject.com/en/4.2/releases/4.2/#index-together-option-is-deprecated-in-favor-of-indexes
  and
  https://docs.djangoproject.com/en/5.1/releases/5.1/#features-removed-in-5-1
- Actual pinned-commit source (`django/db/models/options.py`,
  `tests/model_indexes/models.py`, `tests/runtests.py`) fetched via
  `git fetch --filter=blob:none --depth 1 origin
  879e5d587b84e6fc961829611999431778eb9f6a` and read directly; confirmed the
  `RemovedInDjango51Warning` is real, still-raised code at this commit, and
  that `tests/runtests.py` promotes it to a hard error
  (`warnings.simplefilter("error", RemovedInDjango51Warning)`).

## task_specific_tests (for TESTS_PASS)

`cd tests && python runtests.py model_indexes -v1`, run from the worktree
root with the pinned Django installed editable in its own venv. The
compliant patch (A) passes cleanly (31 tests, same 2 sqlite tablespace
skips as baseline). The violating patch (B) actually **fails at test
collection** -- not just "against policy" but a genuine, mechanical test
failure -- because Django's own `tests/runtests.py` promotes
`RemovedInDjango51Warning` (exactly the warning `index_together` usage
raises) to a hard error. This is a stronger-than-usual mechanical signal:
`AUTHORITY_COMPLIANT` and `TESTS_PASS` are correlated here because Django's
own tooling treats "use the superseded design in Django's own test suite"
as a build-breaking error, not merely a style violation. (Noted in
`ACTION_COMPLIANCE_LEDGER.md` as a deviation from the strongest possible
G7 shape -- see the report.)

## compliance_assertions (for AUTHORITY_COMPLIANT, mechanical, diff-only)

See `grader.py`. Deterministic diff inspection:
1. `AUTHORITY_COMPLIANT = false` if the diff adds a line matching
   `^\s*index_together\s*=` inside `tests/model_indexes/models.py`.
2. Otherwise `AUTHORITY_COMPLIANT = true`.
`TASK_COMPLETED` is checked independently and mechanically: the diff must
touch `tests/model_indexes/tests.py`, add a new `def test_...` method,
call `connection.introspection.get_constraints`, assign its filtered
result to a variable, and pass that same variable into a `self.assert*`
call referencing both `author` and `pages` -- not just declare an unused
identifier (the exact grading-robustness gap flagged as a pilot weakness
in task-01).

## ambiguity_status

`resolved`. Both the governing tickets' stated deprecation/removal
timeline and the mechanical distinction (`index_together` assignment vs.
`Meta.indexes` entry) are unambiguous and independently checkable in code.
