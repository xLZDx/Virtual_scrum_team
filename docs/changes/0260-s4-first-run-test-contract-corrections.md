# 0260 S4 first-run test contract corrections

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / product fix `f0c91163ce1af3c952539df0aef9ce571976f238`

## What changed

- Updated QA command and plugin unit tests to selection schema v2 and source-module argv.
- Updated stale E3 store expectations from schema v3 to the current schema v4.
- Updated gate tests to match the accepted waiver contract: only `NOT_RUN`, `INCONCLUSIVE`, and `BLOCKED` result classes are waiver eligible. Missing receipts, empty evidence, stale `PASS`, a `PASS` receipt with required-rule gaps, old-epoch-only evidence, and incomplete acceptance remain non-approving.
- Updated E2E synthetic contracts for schema-v2 module invocation, `.pytest_cache` hygiene, dirty-tree preflight, output truncation, and fail-closed node accounting.
- Added semantic digest coverage where differently sized raw output chunks retain per-run size/hash integrity but do not change an otherwise equivalent semantic digest.
- Pinned the E2E synthetic baseline to product fix `f0c91163ce1af3c952539df0aef9ce571976f238`.

## Why

The first exact-head suite at `d1bd2cf` exposed stale assertions that still expected selector argv, schema v1, store schema v3, and waivers for missing or successful-but-incomplete evidence. It also exposed a semantic-digest mismatch for repeated runs because raw output metadata varies with timing. Test sources now reflect the committed contracts without weakening no-skip, exact-head, rejection, or per-run artifact-integrity requirements.

## Evidence and verification

- The complete six-category run at candidate HEAD `d1bd2cf32b998ff16f15ab054b844382d0e7e55b` reported: functional 54/57 selectors passed, 3 failed; integration 42/48 passed, 6 skipped for unavailable Windows POSIX permissions/sandbox; API 681/693 passed, 7 failed and 5 skipped; E2E 50/55 passed, 5 failed; regression 827/853 passed, 15 failed and 11 skipped; seeded-failure 3/3 passed. Process-termination and `os._exit` selectors remained `NOT_RUN`.
- All 18 report/stdout/stderr artifact files were copied from the exact candidate; source and destination SHA-256 matched. Full run summaries are in those artifacts under `docs/sdlc/evidence/qa/`.
- Designated agents authored the test changes and did not run tests. The `e2e-runner` updated the fixture baseline to the verified `f0c9116` commit. No rerun has occurred after these corrections.
- The functional-test reviewer accidentally ran `git diff --check` once during test authoring; it returned with no output and changed no files. The coordinator initially sent an incorrect candidate SHA for baseline update, corrected it from `git rev-parse HEAD` before any run; no test used the incorrect value.
- The pre-existing untracked S2 evidence file remains untouched. Development stayed in `D:\Repo\Virtual_scrum_team`; no worktree was created or used.

## Acceptance and next steps

- VST-032: authored corrections are not committed; manifest refresh is pending.
- VST-033–037: corrected test contracts are not yet executed; all prior failing results remain in force until exact-head reruns pass.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test authors/executor: `functional-test-reviewer` and `e2e-runner`.
- Next: commit these test sources, regenerate `docs/qa/categories.json`, and run the complete six-category suite at the resulting exact head. Preserve the six POSIX-dependent integration skips and all policy `NOT_RUN` rows as non-passing unless a separately authorized environment can run them safely.
