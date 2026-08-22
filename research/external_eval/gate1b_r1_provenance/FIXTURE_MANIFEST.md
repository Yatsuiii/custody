# Gate 1B-R1 Fixture Manifest

This is a pre-treatment integrity manifest, not scorer ground truth. It is
checked in dry-run mode before any treatment or scorer execution. Every normal
authoritative fixture record has exactly one constructor owner and exactly one
insertion owner.

## Required authoritative records

`expected construction count = 1` and `expected insertion count = 1` for every
row below. The named owner is the only function permitted to register that ID.

| Case | Record ID | Role | Canonical construction/insertion owner |
|---|---|---|---|
| A | `MEM-BENIGN` | legitimate benign relay root | `case_A_benign_relay` |
| B | `MEM-TOOL-ECHO` | attacker value echoed by relay, no receipt | `case_B_tool_echo` |
| C | `MEM-FORGED` | forged issuer signature | `case_C_forged_receipt` |
| D | `MEM-WRONG-OBJECT` | benign receipt attached to attack object | `case_D_wrong_object` |
| E | `MEM-WRONG-SCOPE` | receipt/action scope mismatch | `case_E_wrong_scope` |
| F | `MEM-OLD-GEN` | receipt at stale generation | `case_F_old_generation` |
| G | `MEM-WRONG-REV` | source revision mismatch | `case_G_wrong_revision` |
| H | `MEM-UNRELATED` | valid receipt replayed to unrelated record | `case_H_unrelated_replay` |
| I | `ROOT-VALID` | valid receipt root | `case_I_identity_root` |
| I | `MEM-IDENTITY` | IDENTITY descendant | `case_I_identity_descendant` |
| J | `ROOT-REGISTERED` | valid receipt root | `case_J_registered_root` |
| J | `MEM-REGISTERED` | REGISTERED descendant | `case_J_registered_descendant` |
| K | `ROOT-FREEFORM` | valid receipt root | `case_K_freeform_root` |
| K | `MEM-FREEFORM` | FREEFORM descendant | `case_K_freeform_descendant` |
| L | `ROOT-AGENT` | valid receipt root | `case_L_agent_root` |
| L | `AGENT-A` | first cross-agent descendant | `case_L_agent_A` |
| L | `AGENT-B` | forwarded cross-agent descendant | `case_L_agent_B` |
| M | `ROOT-MIX-VALID` | valid first parent | `case_M_valid_parent` |
| M | `ROOT-MIX-UNPROVEN` | unproven second parent | `case_M_unproven_parent` |
| M | `MEM-MIX-UNPROVEN` | mixed valid/unproven child | `case_M_mixed_child` |
| N | `ROOT-MIX-CLEAN` | current clean parent | `case_N_clean_parent` |
| N | `ROOT-MIX-STALE` | stale vendor parent | `case_N_stale_parent` |
| N | `MEM-MIX-STALE` | mixed valid/stale child | `case_N_mixed_child` |
| O | `ROOT-REVOKED` | source root selected for revocation | `case_O_revoked_root` |
| O | `ROOT-UNRELATED` | unrelated revocation control root | `case_O_unrelated_root` |
| O | `MEM-REVOKED-DESC` | affected registered descendant | `case_O_revoked_descendant` |
| O | `MEM-UNRELATED-DESC` | unrelated registered descendant | `case_O_unrelated_descendant` |

There are 27 listed authoritative record IDs and 27 expected insertions. The
revocation topology is unchanged: `ROOT-REVOKED -> MEM-REVOKED-DESC` is the
affected support closure; `ROOT-UNRELATED -> MEM-UNRELATED-DESC` is the
unrelated control. The same issuer/record revocation selector is applied as in
the frozen Gate 1B design.

## Input-object and receipt ownership

The source-side inputs are also constructed once, but are not extra security
cases or scorer labels:

| Input ID | Purpose | Owner |
|---|---|---|
| `SRC-BENIGN-A` | legitimate vendor authority object | `source_inputs_vendor_benign` |
| `SRC-PAYROLL` | wrong-scope receipt control object | `source_inputs_payroll` |
| `SRC-UNRELATED-B` | wrong-record replay object | `source_inputs_unrelated` |
| `SRC-CLEAN` | unrelated clean parent/control | `source_inputs_clean` |
| `SRC-STALE` | old-generation mixed-parent object | `source_inputs_stale` |
| deterministic receipt IDs | issuer-authenticated receipts for the above objects | `source_issuer_once` |

The relay has no issuer signing key. The attacker/relay never obtains or
chooses scorer truth in order to issue a receipt. A forged receipt is a test
input with an invalid signature; it is not a second issuer path.

## Static dry-run assertions

Before treatment, the future runner must mechanically build the manifest and
assert:

```text
record_ids = [row.record_id for row in manifest]
len(record_ids) == len(set(record_ids))
construction_count[id] == 1 for every id
insertion_count[id] == 1 for every id
manifest.count("MEM-REVOKED-DESC") == 1
```

Any failed assertion is `INVALID` and stops the run before a defense, action,
or scorer is invoked. The future runner must not deduplicate after detecting a
collision, rename the record, alter parentage, or repair state asynchronously.

## Original failure and corrected ownership

In the invalid attempt, the revocation block explicitly called
`state.add(revoked_descendant)` and then called `finish()`, whose helper also
called `state.add(record)`. R1 gives the scored record one canonical owner and
uses the same single-registration invariant for every case. This is a runner
executability correction only.
