# Change 0372: Exclude the timeout-cleanup selector from S4 regression

## What changed

- Added `tests/vst/test_e4_runner.py::test_root_that_survives_the_kill_gives_exit_minus_four` to `POLICY_NOT_RUN` in `tools/qa/build_registry.py`.
- Extended `test_s4_audited_e4_terminating_selectors_remain_not_run` to require this selector in the policy and API `NOT_RUN` records.
- This adds one explicitly excluded selector while preserving all prior exclusions; the policy total will be 53 after registry regeneration.

## Why

The test monkeypatches `_kill_tree` to a no-op, but it deliberately drives the command timeout and post-timeout cleanup/reporting branch, including a child process and an expected `exit_code == -4`. The accepted S4 regression scope excludes timeout/process-cleanup execution, so this selector must not be included in the runnable Windows category. Excluding by explicit policy preserves the user’s boundary and makes the reason visible in reports.

The adjacent selectors were reviewed by their bodies: `test_timeouts_are_bounded_by_the_manifest` uses a fast successful command within a five-second timeout and does not trigger timeout cleanup; the S4 dependency-mutation selector mutates only its synthetic temporary target via a monkeypatch after child completion and does not prove or perform AC-17 in-run mutation of the trusted target.

## Verification state

- Read-only registry inspection at HEAD `817bfde9bc3520c97e595e86d4112f3fdae9619c` showed this timeout selector had Windows and WSL profiles and no `NOT_RUN` reason.
- No prohibited selector was executed.
- Focused policy-contract test, registry regeneration, and report-bound regression remain pending after this change.

## Next action

Codex regenerates and commits the registry at the post-policy code head. The designated E2E runner then runs the focused contract test and full authorized Windows regression, preserving the new timeout selector and existing policy set as `NOT_RUN`.

## Ownership

Accountable task owner: operator under the delegated sprint request. Policy implementation, evidence and local Git: Codex. Test execution: designated E2E runner.
