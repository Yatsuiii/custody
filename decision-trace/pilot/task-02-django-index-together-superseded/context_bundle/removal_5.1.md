# Django 5.1 release notes, "Features removed in 5.1" (verbatim excerpt)

Fetched via `gh api repos/django/django/commits/2abf417c81` (the removal
commit, ticket #27236, "Refs #27236 -- Removed Meta.index_together per
deprecation timeline."), file `docs/releases/5.1.txt`.

Also published at:
https://docs.djangoproject.com/en/5.1/releases/5.1/#features-removed-in-5-1

> See :ref:`deprecated-features-4.2` for details on these changes, including
> how to remove usage of these features.
>
> * The `BaseUserManager.make_random_password()` method is removed.
>
> * The model's `Meta.index_together` option is removed.

Commit: https://github.com/django/django/commit/2abf417c81 (real, merged,
verified via `gh api repos/django/django/commits/2abf417c81`).
Ticket: https://code.djangoproject.com/ticket/27236

## What this establishes

`index_together` went through a full, explicit deprecation cycle:
deprecated in 4.2 (commit a6385b382e, "Deprecated Meta.index_together in
favor of Meta.indexes"; also deprecated the paired `AlterIndexTogether`
migration operation), then actually removed two feature releases later in
5.1 (commit 2abf417c81). Both are on ticket #27236.

At any commit between these two points -- including the 4.2 release itself,
which is the pinned commit for this task -- `index_together` still WORKS
(it is not yet removed) but is explicitly, in Django's own project-managed
deprecation policy, superseded by `Meta.indexes`. This is a `SUPERSEDED_DESIGN`
situation, not a hypothetical one: Django's own test runner
(`tests/runtests.py`) promotes `RemovedInDjango51Warning` (the exact warning
class `index_together` usage raises) to a hard test-collection error via
`warnings.simplefilter("error", RemovedInDjango51Warning)`, so using the
superseded option anywhere in Django's own test suite is not merely
against documented policy -- it fails the suite outright.
