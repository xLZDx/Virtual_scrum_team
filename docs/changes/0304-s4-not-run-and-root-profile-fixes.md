# 0304 S4 policy NOT_RUN reporting and restricted-root fixture correction

**Date:** 2026-10-25  
**Executor:** Codex  
**Base HEAD:** `980d8787b7d55f5d44991bb0fe1459d1de5de23b`

## What changed

- `tools/qa/run.py` now reports explicit category-wide policy `NOT_RUN` reasons even when those selectors have no runtime profile. They remain outside expected/executed pytest IDs, while their presence makes a category result non-approving through the existing `INCONCLUSIVE` path. Selectors assigned to another runtime profile remain `unassigned`, not `NOT_RUN`.
- `tools/qa/matrix.py` now validates those category-wide report fields and removes policy `NOT_RUN` IDs from the profile-unassigned expectation. Its reason describes category-level exclusions rather than claiming they are assigned to a profile.
- The S2 root signer-isolation test fixture now gives its synthetic IPC parent to `root:runner` with mode `0710`. The socket remains `signer:runner`, mode `0660`; worker identity and denial assertions are unchanged.

## Why

At candidate `980d878`, the safe synthetic E2E outer contract demonstrated that a sandbox-dependent selector recorded in the category inventory but declared `NOT_RUN` could be omitted from `expected_test_ids` and still yield `PASS`, with an empty `not_run_test_reasons` field. This was a product defect; the underlying sandbox selector was not invoked. The full Windows and WSL matrix reproduced the affected outer contract test.

The restricted-root integration report at the same candidate showed only the signer-isolation test failing. The report identity was UID/GID `0:0`, groups `[]`, with no `CAP_DAC_OVERRIDE`. The fixture's IPC parent was signer-owned, runner-group, mode `0710`; `require_worker_cannot_access_signer()` must stat through that parent. Source review confirmed the restricted root could not traverse it. The revised parent owner keeps the path private to root and the runner group, while the worker remains outside that group and the socket retains signer ownership.

## Verification state

- Before the fixes, the designated test agents ran focused Windows S4 contracts at exact HEAD `980d8787b7d55f5d44991bb0fe1459d1de5de23b`; the valid focused set passed 114/114, while the policy `NOT_RUN` contract exposed the false `PASS` described above.
- Before the fixes, the exact-head matrix at `980d878` returned `FAIL`. Windows functional/integration/API/seeded-failure passed; E2E and regression failed on the `NOT_RUN` contract and Windows E2E also had a native-collection failure. WSL functional/integration/API/seeded-failure passed; E2E and regression failed on the `NOT_RUN` contract. The restricted-root API selector passed; the root signer-isolation selector failed because its test parent directory was inaccessible to the restricted root. The matrix's policy `NOT_RUN` exclusions also remained non-approving.
- A code reviewer initially found a MAJOR mismatch between the newly category-wide runner report and profile-scoped matrix validation. The matrix validator was aligned; fresh review found no remaining material findings.
- The root stdout artifact contained only pytest progress and a failure count, with no assertion text; the root selector's cause was derived from its verified identity and source path semantics. It has not yet been rerun after the fixture correction.
- No tests, checks or registry generation ran during this coding pass. The changed test source makes the selector registry stale until the next committed refresh.

## Next

Commit the code/fixture corrections, regenerate and commit the selector registry from those committed sources, then have the designated test agents run focused Windows contracts and the restricted-root signer selector. If those pass, rerun the complete assigned S4 Windows/WSL/restricted-root matrix at one exact committed head. Preserve all policy `NOT_RUN` rows as non-approving and never select timeout, process-kill/death, mutation, or underlying sandbox-dependent scenarios.
