# Change 0434: refresh S2 known limits from exact-head runtime evidence

## What changed

- Replaced the stale S2 E5-only reference to the `280e2d0` run with the signed per-run WSL evidence at exact source/test head `f0bbac8`, while retaining the run-specific scope and deployment limitations.
- Linked the Known limits section to the exact-head POSIX runtime and E5 evidence and clarified that passing local fixtures do not establish Windows Job Object nesting, full process-tree containment, persistent deployment, or full E8 crash/resume acceptance.
- Updated S2 backlog items VST-017 and VST-020 to record the `f0bbac8` safe runner-lifecycle evidence and the exact local-Git timeout/restart selector that remains `NOT_RUN` under policy.

## Why

The S2 plan's DoD requires the Known limits section to remove closed items and state remaining limits. Existing text pointed to an older E5 run and described the updated Git fixtures as awaiting a designated-agent regression, despite exact-head safe WSL evidence already recording the safe lifecycle remainder. The update reconciles those records without broadening platform or policy acceptance.

## Affected paths

- `tools/vst/schemas/README.md`
- `core/BACKLOG.md`
- `docs/changes/0434-refresh-s2-known-limits-from-f0bbac8-runtime-evidence.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and review

- Starting repository HEAD: `cc3fbb67b43fba39c13ffef976ddeacff286438c`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- The initial worktree had only the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; it was preserved and not staged or modified.
- Evidence reconciled: `docs/sdlc/evidence/s2-e5-runmanifest-wsl-f0bbac8-20261026.md` and `docs/sdlc/evidence/s2-permitted-posix-runtime-evidence-f0bbac8-20261026.md`. The latter records the exact command and excluded selector list, including `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`.
- A current-turn `doc-updater` review (GPT-6 Luna, low effort) found no actionable documentation or evidence-consistency findings.
- Work in this change is documentation-only. No source/test code, restricted scenario, test, build, CI, migration, or system runtime action was performed.

## Verification and acceptance

- The 56-case safe runner-lifecycle remainder is recorded as passing at source/test head `f0bbac8`; the timeout/restart selector was expressly excluded and remains `NOT_RUN` under policy.
- E5 remains a PASS only for its signed per-run probe. The evidence does not prove persistent deployment, general egress enforcement, Windows Job Object nesting, full POSIX process-tree containment, or E8 crash/resume acceptance.
- No tests or acceptance checks were run in this documentation update. `tools/build_document_registry.py` regenerated `governance/DOCUMENT_REGISTRY.md` from the staged Markdown inventory after review.

## Ordered next steps and owners

1. Codex: keep S2 Phase 8 open and continue only independent, policy-permitted S2 evidence work; do not start S3 until S2 is closed.
2. Operator: provide the specific authorization or policy disposition needed before any restricted process-kill, mutation, or crash/resume scenario can be considered.
3. GPT-PM: adjudicate a fresh exact-head S2 gate only after required evidence and authorized scenarios are reconciled.

## Attribution

Change: 0434
Executor: Codex
