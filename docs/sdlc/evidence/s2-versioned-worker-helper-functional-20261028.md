# S2 Versioned Worker Helper Functional Test Evidence

## Scope and provenance

- Repository: `D:\Repo\Virtual_scrum_team`
- Base revision observed: `9a5c41de5ce2878558402665eafaa0a80c09d177`
- Test changes in this worktree: `tests/vst/test_s2_persistent_runner_service.py` and `tests/vst/test_s2_runner_lifecycle.py`.
- Production implementation was already present in the worktree when this test assignment began; this test role made no production-source edits.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not modified or staged.

## Acceptance mapping

| Gate | Required behavior | Test coverage authored | Execution |
|---|---|---|---|
| S2-WH-1 | Helper path is the exact absolute versioned path derived from a full lowercase 40-character commit ID; malformed, legacy, alternate-head, and alternate-prefix paths fail closed. | `test_versioned_worker_helper_path_requires_full_lowercase_commit_id`; `test_versioned_worker_helper_rejects_unbound_path_before_filesystem`; config loader fixture now requires `worker_exec_helper_path`. | PASS at exact committed code/test HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976` |
| S2-WH-2 | Root helper file must be a regular singly linked file with root owner, daemon group, and exact setuid mode. | `test_versioned_worker_helper_rejects_invalid_file_metadata` (owner, group, mode, hard-link count). | PASS at exact committed code/test HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976` |
| S2-WH-3 | The binary digest and embedded build identity must match trusted configuration. | `test_versioned_worker_helper_rejects_digest_mismatch_before_execution`; `test_versioned_worker_helper_rejects_embedded_identity_mismatch`. | PASS at exact committed code/test HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976` |
| S2-WH-4 | Verification detects an inode replacement during validation and the service rejects a changed helper identity before a child launch. | `test_versioned_worker_helper_rejects_path_inode_change_during_verification`; `test_service_refuses_helper_identity_change_before_runner_spawn`; `test_versioned_helper_identity_mismatch_refuses_spawn_without_fallback`. | PASS at exact committed code/test HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976` |
| S2-WH-5 | POSIX distinct-UID launch uses only the versioned helper and runs identity verification before `Popen`, with no legacy-path fallback. | `test_versioned_worker_helper_verifies_immutable_identity_and_uses_no_legacy_fallback`; `test_versioned_helper_identity_callback_runs_before_spawn`; shared gate Popen fixture asserts its executable equals the exact versioned path. | PASS at exact committed code/test HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976` |

## Execution status

This functional-test author did not execute pytest because its role explicitly prohibits it. Codex handed execution to the authorized E2E role, which ran the focused modules. Attempts 1–3 exposed test assertion/fixture defects documented in the execution evidence; the test author corrected them without weakening assertions. Attempt 4 passed **179, failed 0, skipped 6**, exit 0, in 80.78 seconds with CPython 3.14.3 using the exact command:

```text
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_persistent_runner_service.py tests/vst/test_s2_runner_lifecycle.py
```

Attempt 4 is diagnostic evidence on dirty base HEAD `9a5c41de5ce2878558402665eafaa0a80c09d177`. The final exact-head run is attempt 5: **179 passed, 0 failed, 6 skipped**, exit 0, 77.53 seconds, CPython 3.14.3, at committed HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976`. It used the exact command above. The attempt-5 evidence file records source/test SHA-256 values, exact revision, one pytest-asyncio deprecation warning, and the six platform skips. Skips are not passes and remain unverified.

A separate E2E-role run reported that the three parameter cases in `test_versioned_worker_helper_rejects_unbound_path_before_filesystem` failed because the assertion expected stale error wording (`not bound to the exact-version path`). The matcher now uses the implementation's actual message (`not the configured exact-version path`). That failure predates the assertion-only fix and is retained as attempt 1 history; attempt 5 in the current run record verifies the corrected committed revision.

The E2E role's attempt 2 is recorded in `s2-versioned-worker-helper-execution-20261028-attempt2.md`: 176 passed, 3 failed, 6 skipped. The exact failures were the two stale-cgroup tests reaching real `os.rmdir` while synthetic control files were ordinary Windows files, and the manifest capture test attempting to add `geteuid` to Windows `os` with pytest monkeypatch's default `raising=True`. The test-only corrections below postdate that run; attempt 2 does not verify the current revision. Attempt 5 is the final exact committed-head result for the corrected revision.

## Follow-up: pre-existing fixture blockers

The E2E-role report also identified three unrelated full-module fixture blockers that predate the versioned-helper cases. `test_posix_stale_cgroup_reconciliation_removes_only_owned_scope` now shims the kernel `rmdir` boundary, removes only the two synthetic control files, then calls the real temporary-directory `rmdir`; it records the target and remaining deadline budget. `test_posix_stale_cgroup_reconciliation_refuses_unconfirmed_cleanup` now injects an `OSError` at that same boundary and asserts the implementation's actual fail-closed error text. Both retain the populated-state and stale-scope outcome assertions. `test_run_manifest_commands_stops_after_incomplete_cleanup_and_records_later_command_not_run` constructs the real `ExecutionAuthority` type with an isolated test grant verifier and claim/reserve/complete callbacks, preserving the production authorization guard and the intended mocked capture behavior; its POSIX identity shim injects the copied `_posix_runner_os` namespace into the execution-grant module rather than mutating the process-global Windows `os` module. These are test-fixture repairs only. Attempt 2 predates these repairs and the path-matcher fix; no rerun was made, so the latest test revision remains **NOT_RUN**.

The E2E attempt 3 report was **178 passed, 1 failed, 6 skipped**. Its sole failure was the manifest mock returning `EXIT_CAPTURE_INCOMPLETE` without invoking `_before_spawn`, so the real authority correctly rejected a receipt with no confirmed reservation. The mock now invokes the callback before simulating command launch/capture, exercising the real reserve-and-helper-verification boundary while preserving the one-command and `INCONCLUSIVE` assertions. Attempt 4 passed on this corrected dirty-diff revision.

## Limitations and next action

- Exact-head focused functional acceptance is proven by attempt 5; this does not prove privileged-helper installation or service runtime behavior. Separate successful artifact-install evidence is in `s2-versioned-worker-helper-install-d5001797-20261028.md`; no service was activated.
- Owner: Codex maintains provenance and coordinates; e2e-runner owns remaining permitted runtime acceptance.
- Next action: finish fresh exact-head specialist review and GPT-PM adjudication; keep root configuration, E5 signature, effective egress, containment, and unit-test proof as separate criteria.
