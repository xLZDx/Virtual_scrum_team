# Change 0222 — Reconcile S2 WSL2 provisioning state

Date: 2026-10-25
Executor: Codex

## What changed

- Corrected the S2 plan's entry criterion, which still claimed sandbox provisioning had not been reached.
- Updated both S2 handover reports to state the accepted per-run Ubuntu-24.04 WSL2 evidence and keep the exact GPT-PM M03 gaps visible.
- Recorded the documentation decision and regenerated the document registry.
- Added the fresh exact-head S2 recovery-module evidence and updated the mapped E7 report/backlog rows.
- Added exact-commit WSL runner/probe and bounded Store lifecycle evidence at the same HEAD; updated acceptance evidence without upgrading skipped or deselected cases.
- Recorded a process-scope mistake: a repeated `wsl --list --verbose` exposed names/state/version of unrelated registered distributions, despite the existing project rule. No other distribution was accessed or modified.

## Why

The plan's stale sentence contradicted its provisioning guide and the accepted signed E5 evidence for run `280e2d0`. The change reconciles the record without upgrading a single run's inventory/attestation into persistent deployment or complete E5 acceptance.

## Affected contracts and paths

- Entry criterion 3 and E5 acceptance/report status.
- Paths: `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`, both S2 reports, `core/BACKLOG.md`, `core/STATE.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `governance/DOCUMENT_REGISTRY.md`, and `docs/sdlc/evidence/s2-exact-head-functional-e2e-2026-10-25.md`.

## Decisions and limits

- The recorded Ubuntu-24.04 WSL2 inventory and network-policy attestation for run `280e2d0` count as one run-scoped accepted preflight result (change 0063).
- This does not close GPT-PM finding M03: the worker environment/workspace binding is not established, OS memory/temporary-storage/process-count quotas are not demonstrated, and external direct-writer exclusion is not proven.
- It does not close E4 platform acceptance, full POSIX containment, Windows Job Object nesting, or E8 crash/resume. Those cases remain unverified or `NOT_RUN` under their existing constraints.
- The technical platform/service owner is not named in the repository. The operator is accountable for the delegated project; Codex executes repository work. Designated test-owner roles own future mapped acceptance test execution after the environment binding is supplied.
- The functional reviewer (GPT-6 Luna, medium effort) ran `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_operation_recovery.py` on exact repository HEAD `c2771b5968afcdd2b027f1c008fc8023fd0e0f12`: 4 passed, 0 failed, 0 skipped; one pytest-asyncio deprecation warning. Evidence records the E7/VST-017/018/019 mapping and scope limit.
- The E2E runner (GPT-6 Luna, medium effort) ran exact committed WSL staging from `git archive HEAD`, with matching Git blob hashes: runner/probe 86 passed, 11 skipped, 4 prohibited mutation cases deselected; bounded Store lifecycle 19 passed. Exact commands/environment and skip mapping are in the evidence file.
- The WSL enumeration incident is a process lesson, not a product acceptance blocker; future inspection stays on the named distro only.

## Verification state

- `report_conform.py` refreshed both S2 reports; `report_conform.py reports --check` exited 0; `tools/build_document_registry.py --check` exited 0; `git diff --check` exited 0.
- No product code or test files were changed by the coordinator or test agents; test outcomes above were executed by the designated test agents and are preserved in the exact-head evidence file.
