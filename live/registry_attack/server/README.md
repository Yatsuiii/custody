# Stale Registry attack server

This image serves one stable Streamable HTTP MCP endpoint at `/mcp`. Its tool
surface is selected once, at process startup, by `CUSTODY_MCP_REVISION`.

- `v1`: `lookup_customer(customer_id)` is read-only, idempotent, and closed-world.
- `v2`: `lookup_customer(customer_id, forward_to=None)` can request forwarding;
  its safety annotations change to non-read-only, non-idempotent, and open-world.

Both revisions expose:

- `GET /health` for revision-bound readiness.
- `GET /evidence` for process-local dispatch counters.

Build and run v1 locally:

```sh
docker build -t custody-registry-attack .
docker run --rm -p 8080:8080 \
  -e CUSTODY_MCP_REVISION=v1 custody-registry-attack
```

The evidence ledger is deliberately process-local and stores no tool arguments.
For a live before/after assertion, deploy Cloud Run with exactly one instance and
confirm that the `instance_id` returned before and after the attempted dispatch
is unchanged. The `forward_to` path records a real handler dispatch and simulated
forwarding state; it does not send data to an external recipient.
