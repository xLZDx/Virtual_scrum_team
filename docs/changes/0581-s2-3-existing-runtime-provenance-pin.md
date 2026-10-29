# S2-3: preserve target inventory identity in existing-runtime verification

## Task and review finding

- Sprint task: S2-3, continuation of the immutable non-secret runtime bundle and bounded WSL
  qualification preparation.
- Repository: `D:\Repo\Virtual_scrum_team`.
- Prior implementation commit: `f34cefd0827f631466e66b39a03b1d999c770388`.
- GPT-PM exact-head review request: `d4577012-d47b-4b43-b598-bfcbb8d064c9`; verdict `MODIFY`.
- Review summary: `docs/sdlc/evidence/s2-3-review-m-s2-3-03-d4577012.md`.
- GPT-PM confirmed the two earlier source-map and fresh-stage MAJOR findings were resolved, then
  identified M-S2-3-03: the existing-runtime branch referenced `inventory_sha` but the shell
  invocation did not pass/unpack it. Reusing an already-present matching runtime would therefore
  raise `NameError` before the intended schema-3 marker comparison.

## Correction

- `tools/qa/install_wsl_runner_runtime.sh` now passes the inventory digest between the plan digest
  and bundle root to the embedded Python verifier and unpacks it in that same order.
- `tests/vst/test_s2_stage_only_install.py` extracts and executes the actual existing-runtime
  validation block with disposable POSIX fixtures. It checks that a matching schema-3 marker is
  accepted and that mismatched inventory and source-head values are rejected. A separate assertion
  binds the shell invocation and Python tuple unpacking to the same argument order.
- No live WSL artifact, systemd unit, runtime selector, Store, key, E5, or dispatch path was used.

## Verification

- The direct POSIX test result is pending. The code and regression must be committed first, then
  executed by the designated `e2e-runner` against that committed source. No result is inferred from
  the previous 54-case run, which was bound to the pre-f34 working-tree overlay and did not cover
  this existing-runtime branch.
- Static review by `code-reviewer` verified that both the marker-writer and existing-runtime
  verifier invocations pass and unpack `inventory_sha` in matching positions. This is not a test
  result or GPT-PM approval.
- GPT-PM's `MODIFY` disposition remains open until the direct committed-source regression is
  evidenced and a focused exact-head re-review closes M-S2-3-03.

## Next actions

1. Commit this fix, its focused test and linked evidence/status updates as the current S2-3 task.
2. Execute the focused test against the committed tree through `e2e-runner`; preserve the exact
   command, commit, environment, result and input hashes.
3. If it passes, submit a new GPT-PM review focused only on M-S2-3-03 and the direct regression;
   do not reopen the two resolved findings without contradictory evidence.
4. Do not stage, select, activate services, or proceed to S2-4 until the exact package gates and
   fresh source-bound target inventory are satisfied.
