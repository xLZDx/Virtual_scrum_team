# 0173 — Map gate signature rejection for AC-7

## What changed

Added the existing `tests/vst/test_e2_gate.py::test_forged_unsigned_receipt_rejected` selector to the API category's required IDs. The selector exercises the public gate evaluation API with an unsigned forged receipt and asserts that it is rejected. It has no competing primary-category assignment.

## Why

The accepted S4 AC-7 explicitly requires signature-failure coverage where applicable. The previous API mapping had stale evidence and runner failure coverage but no required selector that falsified signature rejection. Reusing the existing gate contract test adds that missing acceptance path without new test code or product changes.

## Verification state

The focused API plus seeded-failure run must be repeated after this manifest change. The exact command, committed code/manifest HEAD, and counts will be added in evidence record 0174.

## Remaining scope

This closes the identified AC-7 signature path for the API lane, not exhaustive coverage of every callable in the five S4.3.2 modules. The API category remains `PARTIAL`; network API remains `UNSUPPORTED`.
