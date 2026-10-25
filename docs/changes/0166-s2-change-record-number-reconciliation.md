# Change 0166: Reconcile shared change-record numbering

## What changed

- Renumbered the S2 preflight nonce exact-head evidence record from the colliding number 0164 to 0165.
- Updated S2 evidence, backlog, decision log, and test change-record references to use 0165.
- Preserved the prior commits and test evidence; no source or test behavior changed.

## Why

S2 and S4 work proceeded on parallel sprint branches. S4 already used repository-wide record number 0164 when the S2 test owner independently assigned the same number to its exact-head evidence. A unique current record set avoids ambiguous references when sprint history is later combined.

## Verification state

- Current S2 record filenames and references were reconciled by source inspection.
- No tests/checks were run for this documentation-only renumbering. The underlying exact-head result remains 4 passed / 22 deselected on code HEAD `6ee97cb` and test HEAD `deed6ab`.

## Ownership and next step

- Accountable task owner: operator (delegated S2 continuation).
- Executor: Codex.
- Next: continue the S2 code/security review and exact-head final gate sequence with record 0165 as the evidence identifier.
