# S2 E4 WSL skip triage

## Source and scope

- S2 branch: `s2-isolated-worker-sandbox`.
- Current repository HEAD at triage: `50647fb6f9c7d1720e98c1e26ad375a4532149c6`.
- Prior WSL selector run under review: `ed723a953d51b92827d3977c96e833258a38342c` (109 passed, 11 skipped).
- Test inventory is unchanged between those commits for the reviewed E4 modules: `tests/vst/test_s2_runner_lifecycle.py`, `tests/vst/test_s2_sandbox_probe.py`, and `tests/vst/test_e4_runner.py`.
- No test was run during this triage.

## Four E4 scenario values

The four skips are parameter values in `test_e4_platform_containment_scenarios_not_run`, an intentionally skipped placeholder in `tests/vst/test_s2_runner_lifecycle.py`:

1. `posix_process_group_cleanup`: requires process-group cleanup and termination; prohibited by the active process-kill/kill-table constraint.
2. `post_exit_descendant_cleanup`: requires descendant process termination/cleanup; prohibited by the same constraint.
3. `key_file_permissions_for_worker_identity`: the placeholder is not runnable, but the real `test_posix_worker_cannot_read_signer_or_key_file` ran in the recorded WSL suite. This behavior is not an outstanding selector from the four.
4. `windows_parent_job_nesting`: requires a Windows host with nested Job Object behavior; Ubuntu-24.04 WSL2 cannot provide this platform boundary.

## Result and ownership

The four entries are not independent runnable pytest selectors. No additional test was run because two require a prohibited action, one is already represented by a passing identity-boundary test, and one requires Windows. E4 remains partial. The operator is accountable for the delegated S2 work; `e2e-runner` performed read-only triage. The technical platform owner is `UNKNOWN` in canonical records. Next: preserve the two prohibited cases as `NOT_RUN`; run Job Object nesting only on an authorized Windows host; do not rerun the key-file placeholder in place of its real passing selector.
