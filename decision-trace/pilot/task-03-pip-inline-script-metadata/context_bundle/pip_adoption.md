# Pip adoption evidence

Primary sources:

- Issue #12891: https://github.com/pypa/pip/issues/12891
- Merged PR #13052: https://github.com/pypa/pip/pull/13052
- Merge commit: https://github.com/pypa/pip/commit/36987b0c31b97ffb9fb7949ded628e9a6b10c016

Issue #12891 requests installing requirements from PEP 723 inline script
metadata. PR #13052 is titled “Support installing requirements from inline
script metadata (PEP 723),” merged on 2025-11-27, and closes #12891. Its merge
commit adds a dedicated PEP 723 parser and focused functional tests.

Pinned task SHA `b35182d8f7245f046eed2975275c57b54ce3ba56` is the single parent recorded by
the signed merge commit, so it is a real pre-implementation code snapshot.
