# Current code at the pinned commit (Django 4.2 release tag, `879e5d587b84e6fc961829611999431778eb9f6a`)

## `django/db/models/options.py` (excerpt, around `Options.contribute_to_class`)

```python
self.unique_together = normalize_together(self.unique_together)
self.index_together = normalize_together(self.index_together)
if self.index_together:
    warnings.warn(
        f"'index_together' is deprecated. Use 'Meta.indexes' in "
        f"{self.label!r} instead.",
        RemovedInDjango51Warning,
    )
```

## `tests/model_indexes/models.py` (full file, before this task's change)

```python
from django.db import models


class Book(models.Model):
    title = models.CharField(max_length=50)
    author = models.CharField(max_length=50)
    pages = models.IntegerField(db_column="page_count")
    shortcut = models.CharField(max_length=50, db_tablespace="idx_tbls")
    isbn = models.CharField(max_length=50, db_tablespace="idx_tbls")
    barcode = models.CharField(max_length=31)

    class Meta:
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["isbn", "id"]),
            models.Index(
                fields=["barcode"], name="%(app_label)s_%(class)s_barcode_idx"
            ),
        ]


class AbstractModel(models.Model):
    name = models.CharField(max_length=50)
    shortcut = models.CharField(max_length=3)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["shortcut"], name="%(app_label)s_%(class)s_idx"),
        ]


class ChildModel1(AbstractModel):
    pass


class ChildModel2(AbstractModel):
    pass
```

Note: `Book` has no index covering both `author` and `pages` (`pages`'s
actual db column is `page_count`, via `db_column="page_count"`).

## `django/db/backends/base/schema.py` (excerpt showing both mechanisms create real DB indexes)

```python
def _get_index_sql_dicts(self, model, ...):
    """... (index_together, Meta.indexes) for the specified model."""
    for field_names in model._meta.index_together:
        ...
    for index in model._meta.indexes:
        ...
```

Both `Meta.index_together` and `Meta.indexes` are read by `SchemaEditor`
when creating a table (`create_model`), so *functionally* -- i.e. what
indexes actually exist in the database after the app's tables are created
-- either mechanism produces a real, queryable index. The difference is
purely which Django-level *option* the model declares, and that is exactly
what the deprecation cycle in `deprecation_4.2.md` / `removal_5.1.md`
governs.
