# Change 0215: Fence S3 commits from repository hooks and STOP races

## What changed and why

At S3 code HEAD `1dab3b31ad4504a3a56a4a3c41df8d2f001cbda6`, the exact-head GPT-PM review returned `MAJOR — MODIFY`. It identified repository-controlled commit hooks and a race where a running Git commit could update candidate HEAD after the Store durably accepted STOP. This change adds command-scoped hook suppression and one shared in-process publication lock for the synthetic pilot.

## Affected contracts and paths

- S3 acceptance AC-7, AC-9, AC-10, AC-13, and AC-14: repository code cannot run through commit hooks; the durable STOP transition is ordered against the local adapter's mutation and commit.
- `tools/vst/pilot.py`
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`
- This record and generated `governance/DOCUMENT_REGISTRY.md`

## GPT-PM correlation and findings

- Request ID: `a1618f66-88dc-4630-a510-d76770523148`.
- Reply ID: `c89cf38c-0f64-4b62-8e23-b5ae77334cf6`.
- Input hash: `7c4930409c54d1eef786690b0fca6f912879699513cdb9f662da3dc444c94ae7`.
- The response was correlated, `MAJOR — MODIFY`; no approval was granted.
- M01: `git commit` could invoke candidate-controlled hooks because repository-local `core.hooksPath` remained effective. The invocation now sets `core.hooksPath` to a fresh empty temporary directory using command-scoped Git configuration; candidate configuration is not modified.
- M02: a running commit could mutate HEAD after `stop_attempt_fenced` advanced the epoch. `SyntheticStoryPilot` and its `HandWrittenWorkerAdapter` now share a lock. The adapter acquires it before the first worktree mutation, checks the fence while holding it, and holds it through commit and HEAD resolution. STOP holds the same lock around its durable Store transition, then releases it before cleanup diagnostics.

## Scope and limitations

The lock orders calls routed through one `SyntheticStoryPilot` instance in one process. It does not serialize multiple processes or multiple pilot instances sharing a Store and repository. No broader runtime or sandbox guarantee is claimed. Existing S3 functional/E2E runs are from earlier heads and do not verify this change.

## Verification and ownership

No tests, product checks, builds, migrations, or runtime probes were run for this source change. The documentation registry was generated with `C:\Python314\python.exe tools/build_document_registry.py` (exit 0; 201 Markdown lines). `git diff --cached --check` produced no diagnostics. The focused hostile-hook and deterministic STOP-race regressions are assigned to `functional-test-reviewer` and `e2e-runner` after coding is complete; relevant specialist reviews and a fresh exact-head GPT-PM gate remain pending. Operator is accountable for delegated S3 work; Codex is the executor. The technical owner of any cross-process deployment mechanism is not established in canonical records.
