# 0064 S2 phase state and backlog reconciliation

## What changed

- Replaced stale `docs/sdlc/STATE.md` verification status with current code/test heads, executed test counts, per-run WSL evidence, remaining `NOT_RUN` scenarios, and pending review/GPT-PM gates.
- Added active S2 status to `core/STATE.md` and marked the old pre-runtime S2 sentence as historical.
- Reconciled S2 backlog items VST-009 through VST-020 and VST-025/026 against committed implementation, test and runtime records.
- Updated VST schema Known limits and the WSL provisioning guide to describe per-run acceptance while retaining unverified Windows, prohibited process-kill, full E8 and production-deployment limitations.
- Corrected the stale S2 sprint name in the unified organization blueprint.
- Added the decision and process lesson, then regenerated `governance/DOCUMENT_REGISTRY.md`.

## Why

The central state and several acceptance summaries still described S2 before test execution and WSL provisioning, despite evidence in records 0056-0063. A reconciled source of truth is needed before exact-head specialist review. No acceptance was upgraded beyond its recorded evidence: E5 applies only to its exact per-run correlation; prohibited process-kill/kill-table scenarios, Windows Job Object nesting, and complete E8 crash/resume remain `NOT_RUN`.

## Scope and ownership

- Accountable task owner: operator.
- Executor: Codex.
- Technical owner for WSL host provisioning is not named in this repository.
- The untracked `docs/sdlc/evidence/s2-functional-test-run.md` was present before this update and was preserved, not staged or modified.

## Verification state

- Documentation was reconciled against repository records and evidence at prior HEAD `0f69d16ce2c67cb5c7114b61119ea62be785f1cb`.
- No tests, checks, builds, CI, migrations, or new host probes were run for this documentation-only update.
- Document registry generation is a local deterministic documentation operation; its write and result are recorded with this commit.
- Prior S2 runtime evidence and exact test commands/results remain in `docs/sdlc/evidence/` and change records 0056-0063.
