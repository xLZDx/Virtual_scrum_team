# S4 mapped native E2E run on the transferred snapshot

## Scope and provenance

- Snapshot run ID: `a198f0afd1c64dc2b960a08f757eff9c`.
- Snapshot candidate HEAD: `e43329f0d8312c94a0e4316a4d54ece605a79dec`.
- The snapshot transfer and permission checks are recorded separately in `docs/sdlc/evidence/s4-wsl-transfer-e43329f.md` (change 0123).
- Environment: named WSL `Ubuntu-24.04`, Python 3.12.3, pytest 7.4.4, executed as the provisioned non-root worker. The source snapshot remained read-only.
- The S4 plan's report-bound command is a run-specific `tools.qa.run` invocation requiring a v2 manifest and signer socket; that path was not invoked. This read-only task executed only the exact pytest argv selector list derived from the committed E2E registry and its `validate_projection()` contract. No signer, report, receipt, or gate was used.

## Exact mapped scenarios and command

The seven E2E IDs from `docs/qa/categories.json` were invoked with the manifest-pinned argv shape:

```text
/usr/bin/python3 -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin <seven sorted E2E registry selectors>
```

The effective bounded invocation used `TMPDIR=/dev/shm`, `PYTHONNOUSERSITE=1`, `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, and `GIT_OPTIONAL_LOCKS=0`, wrapped by `/usr/bin/timeout --signal=TERM 120s`. `/dev/shm` is a bounded temporary filesystem; pytest's cache provider and bytecode writes were disabled. The checkout was selected with WSL `--cd` using this run's snapshot path; the private path and worker identity are excluded from this public record.

The IDs were:

- `tests/qa/test_s4_qa_e2e.py::test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence`
- `tests/qa/test_s4_qa_e2e.py::test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_app_checkpoint_can_resume_same_effect_under_new_store_epoch`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_candidate_identity_cannot_be_self_selected`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_rejects_out_of_scope_edit_before_worker_invocation`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_stop_fences_interrupted_attempt_idempotently_and_rejects_stale_start`

## Results and failure classification

The first run used an extra `--basetemp` argument and completed in 3.51 seconds: **6 passed, 1 failed**. Because that argument was outside the registry-pinned argv, the same selectors were run again using the exact pinned pytest argv with the bounded `TMPDIR`; that execution completed in 4.29 seconds: **6 passed, 1 failed**. There was no warning output.

Failure:

- Journey: S4 E6 snapshot CLI refusal.
- Location: `tests/qa/test_s4_qa_e2e.py:64`.
- Classification: **test defect**.
- Expected by the assertion: `distribution must be the named Ubuntu-24.04 WSL distro`.
- Observed product result on POSIX: `snapshot transfer must be invoked from the Windows host`.
- Evidence: `transfer_snapshot()` checks `os.name != "nt"` before checking the requested distribution. On the named POSIX runtime, the host-platform precondition therefore fires first. This is the intended fail-closed platform guard; the test assumes Windows validation order.
- Required action: update the E2E oracle to expect the POSIX host guard on POSIX and retain the wrong-distribution assertion for Windows. Do not weaken the guard. A corrected test requires a new committed source snapshot before another native run.

The six other listed E2E IDs passed. The assertion defect reproduced in two invocations; this is not classified as flakiness because the expected-versus-observed contract mismatch is deterministic and platform-specific. No test was quarantined.

## Read-only boundary and remaining acceptance

After the exact-argv run, a worker-side, per-command `safe.directory` Git status query with `GIT_OPTIONAL_LOCKS=0` returned exit code 0 and empty output, confirming no tracked or untracked snapshot changes. The worker used the snapshot only for this E2E selector set and its bounded temporary artifacts.

Native report-bound runner, signer socket, signed receipt, and exact-head VST gate were not run and remain `NOT_RUN`. The test defect blocks the complete mapped E2E category until corrected and re-executed on a new clean snapshot.
