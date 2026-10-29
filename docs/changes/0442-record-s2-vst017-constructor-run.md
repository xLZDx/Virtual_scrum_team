# Change 0442: record S2 bounded-Git constructor regression result

## What changed

- Added exact-head execution evidence for the VST-017 `Thread`-constructor failure regression.
- The single selector passed in the existing Ubuntu-24.04 WSL runner profile; evidence records exact source/test identity, command, invocation, result and limitations.

## Why

Change 0441 added the regression for the post-spawn `Thread` construction failure addressed by source change `f95ceb1`. The exact result must be linked to its test and source revision, while keeping synthetic proof distinct from real process containment.

## Affected paths

- `docs/sdlc/evidence/s2-vst017-constructor-failure-run-79155fd-20261027.md`
- `docs/changes/0442-record-s2-vst017-constructor-run.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and verification

- Exact source/test HEAD: `79155fdf9f1f4a7ba71358592ccd54c669a76291`.
- `e2e-runner`, GPT-6 Luna, medium effort; invocation `4360e5aed857492f933bb5ab4e8b5cf5`.
- Exactly one selector ran: `tests/vst/test_s2_runner_lifecycle.py::test_bounded_git_thread_constructor_failure_kills_reaps_and_closes`; 1 passed, 0 failed, 0 skipped; exit 0.
- The selector injects constructor `MemoryError` while using a fake process. It does not execute a real process-kill path.
- Restricted process-kill, crash/resume, mutation, timeout/restart, and policy selectors remain `NOT_RUN`. The test run made no repository changes.

## Ordered next steps and owners

1. Codex: preserve the result as synthetic-only evidence and reconcile S2 records after reviews.
2. Fresh S2 specialist reviewers: inspect the exact source/test head; report actionable code findings separately from unresolved system acceptance.
3. Codex: continue only permitted S2 evidence work and retain all prohibited cases as `NOT_RUN`.
4. GPT-PM: adjudicate the exact final S2 head only when required evidence is complete; no push/PR before fresh approval.

## Attribution

Change: 0442
Executor: Codex; run executed by `e2e-runner`
