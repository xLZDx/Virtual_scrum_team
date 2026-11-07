# Change 0526: validate dispatch barrier control field types

## Why

While reviewing the new S2 acknowledgement history reconstruction, Python's equality rules showed
that a JSON boolean can compare equal to an integer sequence value (`true == 1`). A malformed
control event must not be accepted as a valid event-sequence binding.

## What changed

- Added strict scalar and SHA-256 format validation for every dispatch pending/acknowledgement
  control record before comparing it with the accepted event and stored result.
- Regenerated `governance/DOCUMENT_REGISTRY.md` for this change record.

## Verification and acceptance

- This is part of the untested working-tree implementation for the S2 Store acknowledgement
  barrier. The test-authoring role is adding malformed-history cases; no tests/checks were run for
  this correction.
- No runtime or privileged action was performed. M03 and overall S2 remain open pending focused
  tests, fresh specialist reviews, and exact-head GPT-PM adjudication.
