# 0137 S4 confine registry source paths to tests

## What changed

- Require canonical forward-slash source paths for QA test node IDs.
- Reject traversal, alternate path spellings, and symlink components.
- Resolve the source beneath repository `tests/` before parsing its static pytest node.
- Update the S4 plan, backlog, decision/lesson logs, and document registry.

## Why

The S4 code review at candidate `452c8ea8da5545bdce0f584a6b51662b93a33abf` found that a raw `tests/` prefix was checked separately from AST source resolution, which constrained the resolved path only to the repository root. A tracked `tests/../...` path could therefore weaken the stated “tracked tests path” contract if Git and path normalization accepted it. The review classified this as MINOR; no current registry entry demonstrated the path.

## Affected contracts and paths

- `tools/qa/registry.py`: canonical path and resolved `tests/` boundary checks.
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`: source path contract and execution state.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: finding, decision, and follow-up state.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for the QA registry trust boundary is not separately named in repository ownership records.
- The code reviewer classified the finding MINOR and did not identify a current exploitable registry entry. The correction preserves valid canonical paths and rejects noncanonical input.

## Verification state

- Prior functional evidence: 9 passed on clean source HEAD `594eedd`; prior native E2E evidence: 7 passed on `452c8`. These runs predate this code change.
- The change is implemented but unverified. No tests or checks were run for it.
- A functional regression and exact-head functional/native reruns are required before accepting the corrected source boundary.
- Signer, report, signed receipt, exact-head gate, and broader sandbox acceptance remain `NOT_RUN`.

## Next steps

1. Commit this source correction and generated registry.
2. Have functional-test-reviewer add a traversal/alternate-path regression and run the focused registry module on a clean committed head.
3. Have e2e-runner transfer that exact head and rerun mapped native E2E selectors plus the read-only post-run probe.
4. Re-review the focused change and keep signer/report/gate as separate `NOT_RUN` gates.
