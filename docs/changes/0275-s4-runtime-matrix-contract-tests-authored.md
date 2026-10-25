# 0275 S4 runtime-matrix contract tests authored

**Date:** 2026-10-25  
**Executor:** Codex with `functional-test-reviewer` as test author  
**Baseline HEAD:** `835c5271b26e29b1308ae0db8da055c694344ece`

## What changed

Added `tests/qa/test_s4_functional_runtime_matrix.py` with 15 focused test functions (including
parameterized cases) mapped in docstrings to S4 acceptance criteria AC-4, AC-11 and AC-14 and
backlog items VST-032, VST-033 and VST-037. Coverage includes:

- Windows, unprivileged WSL and restricted root-profile selector assignments and identity checks;
- policy `NOT_RUN` preservation in the committed registry;
- WSL candidate mount rules, including allowing unrelated WSLg `9p` and rejecting a candidate
  covered by a `9p` mount or a Windows-drive mount;
- root-harness network proof requiring a private loopback-only interface set and a local canary;
- report/proof candidate binding; and
- matrix rejection of missing references, policy `NOT_RUN`, skipped cases, stale candidate HEADs,
  and corrupted artifact byte ranges, plus acceptance of matching profile report fixtures.

## Why

The schema-v2 runtime assignments and matrix validator need falsifiable contract coverage before
any exact-head profile execution. Policy-excluded selectors remain explicit and non-approving.

## Verification state

- Test author: `functional-test-reviewer` (GPT-6 Luna; exact effort is not exposed in the launch
  result, so it is recorded as `UNKNOWN`).
- The agent performed static consistency review only and corrected the exact existing `NOT_RUN`
  selector/category binding before handoff.
- No tests, checks, builds, CI, migrations, or runtime commands were run. The manifest has not yet
  been regenerated to include the new test source; that follows its commit.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved.

## Next step

Commit the test source and its records, regenerate `docs/qa/categories.json` from the committed
test source, commit that registry refresh, and then have the designated test agents execute the
focused tests at the refreshed exact HEAD.
