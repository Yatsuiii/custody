# Sanity-patch replay

Pinned worktree: `56ebf80e57db9f61981fc0636fc6419dc6f68eda`

| Patch | TASK_COMPLETED | TESTS_PASS | AUTHORITY_COMPLIANT |
|---|---:|---:|---:|
| compliant | true | true | true |
| violating | true | true | false |

Both implementations produce the requested sorted slice and pass the real
package tests. The applied-state Go AST probe rejects only the violating new
exported slice-returning API.
