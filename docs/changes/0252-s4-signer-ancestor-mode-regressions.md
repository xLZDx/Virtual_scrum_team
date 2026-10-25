# Change 0252: Map signer ancestor mode regressions

## What changed

- Added a functional selector proving a non-sticky world-writable intermediate directory is rejected by the signer path guard.
- Added a functional selector proving the standard sticky `/tmp` ancestor is accepted when the next path entry is runner-owned.
- Updated functional coverage prose and pinned source provenance to the ancestor-mode implementation commit `b96d78b682e7f8eb12d4dfddeb2ee20f8b26b42a`.

## Why

Security re-review at `c2eefda` found a conditional MINOR because ACLs were checked on traversed ancestors but mode permissions only on the immediate parent and socket. Change 0251 adds worker-writability checks to every lexical and resolved parent and allows sticky writable ancestors only when the next entry is runner-owned. These selectors cover both rejection and the expected safe `/tmp` case.

## Decisions and ownership

- Keep the signer path guard fail-closed for worker-controlled directory entries.
- Preserve the runner-owned `/tmp` child behavior protected by sticky-bit semantics; do not broadly reject all sticky temporary roots.
- Test author and executor: `e2e-runner` (GPT-6 Luna, medium effort). Accountable task owner: operator. Executor/coordinator: Codex.

## Affected contracts and paths

- Signer path validation in `tools/vst/sandbox.py`.
- Regression source and functional registry in `tests/qa/test_s4_worker_boundary_contracts.py` and `docs/qa/categories.json`.

## Verification state

- Code source HEAD: `b96d78b682e7f8eb12d4dfddeb2ee20f8b26b42a`.
- Test and category mapping are committed before execution. No tests were run while authoring.
- Required next step: fresh exact-head Ubuntu-24.04 WSL snapshot, then execute the two new selectors plus the eight existing ACL/group/capability/parser selectors.
- Prior c2eefda evidence (8 focused selectors and 26/26 functional CLI IDs) predates this mode guard. Trusted signer, authoritative task gate, aggregate regression, full E2E denominator and final GPT-PM remain open.
