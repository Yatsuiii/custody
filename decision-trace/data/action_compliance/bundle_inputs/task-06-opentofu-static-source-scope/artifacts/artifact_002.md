# Accepted RFC and implementation

Primary sources:

- https://github.com/opentofu/opentofu/pull/1649
- https://github.com/opentofu/opentofu/blob/8f8e0aa4aa92980882c2df3209c75466629bce4c/rfc/20240513-static-evaluation.md
- https://github.com/opentofu/opentofu/pull/1718

The merged implementation RFC defines a static evaluation context for HCL
expressions used in init-time attributes such as module sources and backend
configuration. It describes retaining the module source expression and
evaluating it in module scope. It does not authorize block-label evaluation.

PR #1718 then merged the static-evaluation base, module-source support, and
backend configuration support for OpenTofu 1.8.
