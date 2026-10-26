# Change 0344 — Add an isolated S4 worker identity category

## Summary

- Added `<sys/stat.h>` to `tools/qa/worker_exec.c` so the strict C build sees the standard declaration for `umask()`; compiler warnings remain errors.
- Added a singleton `identity` primary category for the existing AC-16 worker-identity selector.
- Bound the category to the unprivileged WSL runtime profile, and added registry, runner, artifact-path and matrix contract handling for it.
- Kept the selector out of the broad `functional` category and left the regression-category membership unchanged.

## Why

The authorized WSL helper provisioning reached the exact source compile and failed closed because `umask()` was implicitly declared. After that source defect was identified, the report-bound runner also rejected the stale category manifest: the sole AC-16 selector was grouped under `functional`, which would make a focused allowed run execute unrelated selectors. The fix gives that one selector an explicit report-bound lane without broadening the executable selector interface.

## Affected contracts and paths

- `tools/qa/worker_exec.c`: strict C declaration contract for `umask()`.
- `tools/qa/registry.py`, `tools/qa/build_registry.py`: exact singleton membership and generated primary-category contract.
- `tools/qa/run.py`: fixed category and artifact-path allowlists.
- `tools/qa/matrix.py`: exactly one required report for the WSL identity category.
- `docs/qa/categories.json` is intentionally not included in this coding commit; it must be regenerated from committed code in a separate evidence/documentation commit.

## Decisions and safety

- AC-16 remains the only selector in `identity`; no arbitrary selector CLI was added.
- `identity` is reportable only on `wsl-ubuntu-24.04-cpython-3.12.3`.
- The established regression membership remains `functional`, `integration`, `api`, and `e2e`.
- The 52 policy selectors remain `NOT_RUN`; this change does not authorize process-kill, mutation, crash, or sandbox-policy scenarios.
- No tests, checks, package build, registry generation, or helper installation were run in this coding step.

## Verification state

- Implementation: present in this commit.
- Manual diff review: performed by Codex after the implementation agent returned its scoped diff.
- Runtime/compiler proof: `NOT_RUN` on this committed head; designated test agents must perform the focused report-bound work after all sprint coding is complete.
- Registry manifest: pending regeneration against this commit.

## Attribution

- Accountable task owner: operator under the delegated sprint request.
- Executor: Codex coordinator with implementation-engineer assistance.
- No test or reviewer agent has run for this change.
