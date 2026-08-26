# packaging adoption evidence

Primary sources:

- https://github.com/pypa/packaging/pull/293
- https://github.com/pypa/packaging/commit/28a2e2bb88a8d3fdc4035783597e22a53eff4445

PR #293 implemented PEP 600. During review, maintainers required emitted legacy
names to remain alongside their matching perennial tags. The merged
implementation contains `_LEGACY_MANYLINUX_MAP` and emits each alias directly
after the corresponding `manylinux_<major>_<minor>` tag.

This implementation evidence agrees with the accepted PEP's explicit alias
section; it is not being used as a substitute for policy authority.
