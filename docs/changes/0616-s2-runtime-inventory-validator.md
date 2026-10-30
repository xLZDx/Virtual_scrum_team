# S2-4.12b — fail-closed runtime inventory validator

Date: 2026-10-30
Task: S2-4 runtime owner-to-Runner qualification
Owner: Codex (implementation and coordination); GPT-PM (exact-head code/runtime adjudication)

## Acceptance delta

The authorized replacement inventory for candidate run `s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910` was read-only and returned exit 0, but omitted PID 1 start/namespace identity, the `vst-runner` account, the systemd version, and exact comparison of all 26 installed configuration fingerprints to the consumed baseline. The full JSON was not persisted verbatim. Applying configuration from this partial result would violate the bounded runtime authorization. No apply, preflight, durable claim, probe, or TestRun occurred.

The exact inventory and authorization record is `docs/sdlc/evidence/s2-runtime-owner-runner-qualification-9357ee74.json`; authorization request `9357ee74-c0ac-4ed4-9568-1b4a192bf874`, correlated reply `6d0a5e51-1809-5420-8c45-9ebc6beb9ec4`, bound to pre-change HEAD `1b5dd9d7a639b629465ac6fcf29e300ba80c18ca`. That authorization covered only one replacement read-only inventory invocation and is now used. It does not authorize a further inventory, apply, or runtime attempt.

## Change

Added `tools/qa/verify_s2_runtime_config_inventory.py` to reject incomplete or stale inventory before configuration apply. It pins the consumed configuration baseline from Git blobs, reconstructs all 26 expected destination fingerprints, and requires exact current source/helper/applier/bundle/layout identities; fresh capture time; D: source on read-only 9p with a whole `ro` option; Ubuntu 24.04 WSL2/systemd and PID 1 identity; both fixed runtime accounts; all nine units loaded/inactive; absence of Store, preflight, attestation and container sockets; no candidate identity collision; the exact consumed bootstrap identity; and the exact runtime symlink schema/target. PID identity arrays require actual integers, not booleans. Fingerprint input uses the remote applier contract (`PRESENT`/`regular`). The validator performs no target writes.

## Verification and review

The designated `functional-test-reviewer` ran only:

```text
python -m pytest -q tests/vst/test_s2_runtime_config_inventory.py
22 passed, 1 existing pytest-asyncio deprecation warning; exit 0
```

The test role added fail-closed cases for boolean PID 1 IDs, missing/wrong `kind`, and extra selector fields. The code reviewer confirmed the PID type, fingerprint-shape, and exact-selector fixes. The security reviewer confirmed the validator refuses an incomplete selector and that its refusal path is read-only; no remaining concrete finding was reported. Tests were not run by the primary agent.

Earlier source/test evidence for the worker-settling implementation remains in `docs/changes/0615-s2-4.12b-worker-identity-settle.md`; it is not runtime acceptance. GPT-PM exact-source approval and normal push for that earlier implementation are recorded at HEAD `1b5dd9d7a639b629465ac6fcf29e300ba80c18ca`; that approval does not cover this new validator.

## Current disposition and next action

This validator and its focused tests are implemented and reviewed; S2-4 runtime acceptance remains open. The candidate tuple is still unclaimed and unapplied, but both read-only inventory authorizations have been consumed. The next allowed sequence is: finish this task's exact-head GPT-PM code review, commit and normally push this validator task, obtain a new correlated GPT-PM runtime authorization bound to the resulting HEAD and pinned hashes, then have `e2e-runner` produce and persist one complete inventory, run this validator, and stop at the authorization's exact condition boundary. If the inventory is incomplete or the authorized conditions fail, record the exact result and do not retry without a new authorization.

The prior incomplete inventory evidence remains immutable in `docs/sdlc/evidence/s2-runtime-owner-runner-qualification-9357ee74.json`. No S2-5 or later sprint work is included.
