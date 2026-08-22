# Issue #1042 scope transition

Primary source: https://github.com/opentofu/opentofu/issues/1042

The issue proposed init-time evaluation of constant locals and variables for
configuration attributes. Its initial draft also discussed interpolating block
labels. A maintainer requested that label interpolation be left out because of
rename/identity complexity; the author agreed and edited the issue to mark the
section out of scope. The issue's resolved questions explicitly answer label
interpolation with “No.”

Relevant comments:

- https://github.com/opentofu/opentofu/issues/1042#issuecomment-1875588374
- https://github.com/opentofu/opentofu/issues/1042#issuecomment-1875655905
