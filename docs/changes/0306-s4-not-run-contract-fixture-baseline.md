# 0306 S4 NOT_RUN contract fixture baseline

**Date:** 2026-10-25  
**Executor:** Codex  
**Base HEAD:** `d2c5dd2fbe182def7fdb0f5bb1a7656dc917614c`

## What changed

Updated `tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_cli_preserves_sandbox_dependent_selector_as_not_run` to build its synthetic runner from committed source HEAD `fc20c9e31e1d4bb9bd9356921add66e14e5e230a`, which contains the category-wide policy `NOT_RUN` correction from change 0304. The test's non-approving assertion is unchanged.

## Why

At exact candidate `d2c5dd2fbe182def7fdb0f5bb1a7656dc917614c`, the safe WSL E2E test failed because its fixture pinned `08252020`, whose runner still used profile-scoped `NOT_RUN` handling. The synthetic report therefore returned `PASS` for a registry containing a sandbox-dependent policy exclusion. This was a stale fixture baseline; it did not execute the underlying sandbox-dependent selector. Pinning the synthetic runner to the committed corrected implementation makes the test exercise the intended contract.

## Verification state

- Before this correction, the designated E2E agent ran seven safe focused WSL cases at exact candidate `d2c5dd2fbe182def7fdb0f5bb1a7656dc917614c`: six passed and one failed on this stale-baseline fixture. No underlying sandbox-dependent selector was executed.
- A separate restricted-root report-bound run at the same candidate executed the assigned signer-isolation selector: one passed, zero failed, skipped or uncollected. The category outcome was `INCONCLUSIVE` because category-wide policy exclusions were retained. The report stayed in its ephemeral WSL candidate snapshot and is diagnostic evidence only until consolidated into the exact-head matrix record.
- The fixture correction itself has not been tested. No tests, checks, or registry generation ran during this coding pass.
- The selector registry is stale until refreshed after this source commit.

## Next

Commit this fixture correction, regenerate and commit the selector registry from that committed source, then rerun the safe focused Windows and WSL contracts at the exact registry candidate. Keep the underlying sandbox-dependent selector, timeout, process-kill/death, and mutation scenarios unexecuted.
