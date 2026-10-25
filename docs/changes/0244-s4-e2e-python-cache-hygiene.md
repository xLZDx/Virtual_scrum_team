# 0244 S4 E2E synthetic candidate cache hygiene

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `0b73000bb7eb2a0d25caa8364b066c64299abd85`

## What changed

- Added a minimal `.gitignore` to each synthetic E2E candidate before its initial commit, ignoring `__pycache__/` and `*.py[cod]`.

## Why

The prior E2E report showed that importing `tools.qa.run` generated Python bytecode in the candidate before its pre-execution cleanliness snapshot. The synthetic candidate is created from a limited product archive and did not include repository hygiene rules, so those expected interpreter cache files made it dirty.

## Evidence and verification

- A retained report in pytest's temporary directory recorded only `tools/qa/__pycache__/*.pyc` and `tools/vst/__pycache__/*.pyc` in both before/after dirty paths.
- The E2E test asserts the candidate is clean immediately before CLI execution at `tests/qa/test_s4_e2e_runner_cli.py`.
- This is test-only fixture hygiene; no product code or other test source changed in this commit.
- No tests were run for this correction. The timeout/process-tree test remains policy-skipped.
- No worktree or clone was created; the pre-existing untracked S2 evidence file remains untouched.

## Acceptance and next step

- Synthetic candidate cleanliness: expected bytecode cache files are ignored before the candidate's first commit; rerun remains pending.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test executor: `e2e-runner`.
- Next: commit this fixture correction, then rerun the E2E suite on the exact resulting HEAD. Preserve the timeout selector's `NOT_RUN` policy.
