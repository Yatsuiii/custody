# PEP 723 — governing standard

Primary source: https://peps.python.org/pep-0723/

- Status: `Final`.
- Replaces: `722`.
- A block starts with `# /// TYPE`, ends with `# ///`, and has comment-prefixed
  content between the delimiters.
- The standardized `script` type contains TOML. Its top-level `dependencies`
  field is a list of PEP 508 strings; `requires-python` and `[tool]` are also
  allowed.
- Multiple blocks of the same type are an error; unclosed blocks are ignored.

The task only needs dependency extraction, so it intentionally does not expose
or validate the other fields.
