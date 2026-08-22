# Django 4.2 release notes, "Features deprecated in 4.2" (verbatim excerpt)

Fetched via `gh api repos/django/django/commits/a6385b382e` (the deprecation
commit, ticket #27236, "Fixed #27236 -- Deprecated Meta.index_together in
favor of Meta.indexes."), file `docs/releases/4.2.txt`.

Also published at:
https://docs.djangoproject.com/en/4.2/releases/4.2/#index-together-option-is-deprecated-in-favor-of-indexes

> ### ``index_together`` option is deprecated in favor of ``indexes``
>
> The `Meta.index_together` option is deprecated in favor of the `indexes`
> option.
>
> Migrating existing `index_together` should be handled as a migration. For
> example::
>
>     class Author(models.Model):
>         rank = models.IntegerField()
>         name = models.CharField(max_length=30)
>
>         class Meta:
>             index_together = [["rank", "name"]]
>
> Should become::
>
>     class Author(models.Model):
>         rank = models.IntegerField()
>         name = models.CharField(max_length=30)
>
>         class Meta:
>             indexes = [models.Index(fields=["rank", "name"])]
>
> Running the `makemigrations` command will generate a migration containing a
> `RenameIndex` operation which will rename the existing index.
>
> [...]
>
> * The `AlterIndexTogether` migration operation is deprecated.

Commit: https://github.com/django/django/commit/a6385b382e (real, merged,
verified via `gh api repos/django/django/commits/a6385b382e`).
Ticket: https://code.djangoproject.com/ticket/27236
