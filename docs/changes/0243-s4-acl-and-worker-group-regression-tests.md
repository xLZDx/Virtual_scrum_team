# Change 0243: Map S4 ACL and worker-group regressions

## What changed

- Added five Linux-focused selectors in `tests/qa/test_s4_worker_boundary_contracts.py` for signer socket access ACL rejection, signer-parent default ACL rejection, traversed-ancestor ACL rejection, fail-closed ACL inspection, and snapshot/output worker-group inheritance without `chown`.
- Mapped the five selectors in the functional category in `docs/qa/categories.json` and pinned its source provenance to code commit `cadd8014fcb9eb8b6f226cda726cad3328d78d66`.

## Why

Change 0242 addressed the security-review ACL finding and the synthetic report-bound CLI artifact ownership failure. These regressions make the filesystem ACL and no-`CAP_CHOWN` output contracts falsifiable before the report-bound CLI is retried.

## Decisions and ownership

- The selectors use synthetic ACL xattr responses and a synthetic local Git bundle; they do not inspect or claim a deployed signer service.
- Linux-specific selectors must execute in the pinned Ubuntu-24.04 WSL runtime. A Windows skip is `NOT_RUN`, not a pass.
- Test author and executor: `e2e-runner` (GPT-6 Luna, medium effort).
- Accountable task owner: operator. Coordinator: Codex. Canonical S4 QA infrastructure owner: UNKNOWN in repository records.

## Affected contracts and paths

- Signer-path ACL rejection in `tools/vst/sandbox.py`.
- Snapshot and report-output group inheritance in `tools/qa/wsl_snapshot.py` and `tools/qa/run.py`.
- Functional category selector mapping in `docs/qa/categories.json`.

## Verification state

- Code source HEAD: `cadd8014fcb9eb8b6f226cda726cad3328d78d66`.
- The test source and category mapping are committed before execution. No tests were run while authoring.
- Required next run: transfer a fresh clean snapshot at the test commit, then have `e2e-runner` execute the five new selectors plus the existing capability-drop and synthetic socket selectors in the bounded Ubuntu-24.04 WSL unit. Any platform skip, missing selector, or test error remains non-passing.
- The synthetic `tools.qa.run` report-bound retry remains separate and must use a fresh exact-head snapshot with a test-only manifest/signer. Trusted signer, signed report/receipt, authoritative gate consumption, aggregate regression, and full E2E denominator remain open.
