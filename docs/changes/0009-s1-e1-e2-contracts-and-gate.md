# Change record 0009: S1 E1 contracts and E2 gate

## What changed
- New package `tools/vst/`: `__init__.py`, `contracts.py` (strict validators for TaskManifest, four receipt types and GateDecision, closed enums, `derive_result`, canonical bytes and receipt hash), `signing.py` (HMAC-SHA256 sign and verify), `gate.py` (pure default-deny `evaluate`).
- New `tools/vst/schemas/README.md`: human-readable schema and the exact `derive_result` rules.
- Receipts carry a `slot` field (added to the common fields) so the gate can match them to manifest slots and chain attempts.

## Why
Sprint S1 epics E1 and E2 (baseline decisions BD-2 to BD-5, risks R-1, R-2, R-4): typed signed receipts, a total verdict function whose required slots come from the manifest, and failures that are never erased.

## Affected contracts and paths
Only the new paths above. No existing file was modified. Python standard library only; no I/O, no network, no provider calls.

## Verification state
Code written only. No tests, linters or imports were run, by design (build phase). Tests are written and run by the separate test agents next. Not independently reviewed.
