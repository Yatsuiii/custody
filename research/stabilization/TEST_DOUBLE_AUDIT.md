# Test-double audit

The primary fake is in tests/test_firestore_store.py and is used only for
offline storage behavior. It is not an authority implementation.

## Historical divergence

Before the adapter repair, _FakeTransaction.get returned a DocumentSnapshot,
which allowed _FirestoreTransactionPort.get to call the raw transaction
method. The installed SDK returns an iterator. That divergence was P1 because
local tests could pass while the real adapter failed before a valid
production-equivalence case.

## Current contract

- _FakeTransaction.get returns iter((snapshot,)), matching the installed SDK.
- _FirestoreTransactionPort.get intentionally calls
  DocumentReference.get(transaction=transaction) and returns one snapshot.
- tests/test_firestore_adapter_contract.py inspects installed annotations and
  exercises a fake with the SDK-shaped iterator.
- tests/test_firestore_probe_harness.py verifies atomic artifacts,
  nonterminal-artifact rejection, process-failure classification, and
  operation-level exception preservation.

## Remaining limits

The offline fake queues writes and commits them atomically; it does not emulate
Firestore's server retry scheduler, network conflicts, or timestamp RPCs. That
is intentional test-double scope, not proof of those properties. The hardened
real-service contract probe is the separate evidence path. No known fake is
allowed to define the SDK API.

Result: the known P1 SDK-shape divergence is repaired locally and the real
service independently confirmed the adapter contract in stab01. The fake
remains an offline behavioral double, not a replacement for service evidence.
