# Change 0440: guard all bounded Git post-spawn setup

## What changed

- Moved capture-state allocation before child creation and placed reader construction/start, waiting, and output handling inside the cleanup guard.
- Cleanup now kills/reaps the child and closes pipes even if reader-object construction fails after `Popen`.
- Updated S2 runner documentation and VST-017 status to record that the constructor-failure regression is pending.

## Why

A fresh reliability re-review found that the first cleanup correction still constructed capture dictionaries and `Thread` objects between `Popen` and the `try/finally`. A `MemoryError` in that interval could leave Git running with open unread pipes and without the configured timeout. The new guard covers all post-spawn setup.

## Affected paths

- `tools/vst/slice.py`
- `tools/vst/schemas/README.md`
- `core/BACKLOG.md`
- `docs/changes/0440-guard-bounded-git-post-spawn-setup.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and review

- Starting repository HEAD: `1621122`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- The finding came from a fresh `reliability-reviewer` pass (GPT-6 Luna, medium effort) on the first correction/test head `dc1741b`; it is a static resource-exhaustion path and was not runtime-reproduced.
- Prior reader-start/read regressions passed on `dc1741b`; they use a fake process and do not launch or kill a real process. The new constructor-failure regression is being authored by `functional-test-reviewer` and has not been run.
- No tests, checks, builds, CI, migrations, or runtime scenarios were run for this source correction. No policy-excluded selector was run.

## Acceptance and next steps

- VST-017 remains under verification until the new constructor-failure regression passes at an exact source/test head and fresh reliability/silent-failure review accepts the cleanup boundary.
- Preserve the timeout/restart, process-kill, crash/resume, and mutation selectors as `NOT_RUN` under the current policy.
- Owner: Codex implements; `functional-test-reviewer` authors tests; `e2e-runner` executes only the targeted safe selector; reliability and silent-failure reviewers re-review.

## Attribution

Change: 0440
Executor: Codex
