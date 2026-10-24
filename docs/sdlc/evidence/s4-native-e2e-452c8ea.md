# S4 mapped native E2E on the identified snapshot at 452c8ea

## Scope and provenance

- Snapshot run ID: `e8b68c59c17a449eb2e30803021a37ae`.
- Snapshot candidate HEAD: `452c8ea8da5545bdce0f584a6b51662b93a33abf`.
- Transfer and run-scoped worker permission evidence is separate: `docs/sdlc/evidence/s4-wsl-transfer-452c8ea.md`.
- Environment: Ubuntu `24.04.5 LTS`, Python `3.12.3`, pytest `7.4.4`; mapped selectors ran as the provisioned read-only worker. Private POSIX account and snapshot path are omitted.
- No signer, report, receipt, gate, package installation, or unrelated suite was used.

## Mapped scenarios and command

Seven E2E registry selectors were run using the pinned pytest shape, bounded temporary directory, disabled bytecode/cache/ambient plugins, optional Git locks disabled, and a 120-second timeout. Command (private run-specific `--cd` path redacted):

```text
wsl.exe --distribution Ubuntu-24.04 --user [read-only worker] --cd [private path to identified run repo] --exec env TMPDIR=/dev/shm PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 GIT_OPTIONAL_LOCKS=0 /usr/bin/timeout --signal=TERM 120s /usr/bin/python3 -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin <seven exact registry selectors>
```

Exact selectors:

- `tests/qa/test_s4_qa_e2e.py::test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence`
- `tests/qa/test_s4_qa_e2e.py::test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_app_checkpoint_can_resume_same_effect_under_new_store_epoch`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_candidate_identity_cannot_be_self_selected`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_commits_only_the_manifest_scoped_synthetic_change`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_pilot_rejects_out_of_scope_edit_before_worker_invocation`
- `tests/vst/test_s3_worker_pilot_e2e.py::test_s3_stop_fences_interrupted_attempt_idempotently_and_rejects_stale_start`

Result: **7 passed, 0 failed, 0 skipped**, 4.05 seconds; no warnings.

## Invocation correction and failure classification

The first invocation used WSL `--cd /`, so pytest could not import `tools.qa.pytest_pass_plugin` and no tests were collected (`No module named 'tools'`). Classification: **environment/command setup error**. No product or test assertion executed. The same seven selectors were then run with `--cd` set to the repository path inside the identified snapshot and all passed. This is not classified as a flaky test; no repeat-rate claim is made.

## Post-run snapshot boundary

After the seven tests, the read-only worker queried Git status with optional locks disabled and the exact run checkout marked as safe. It observed candidate HEAD `452c8ea8da5545bdce0f584a6b51662b93a33abf` and an empty porcelain status (`0` bytes). The clone remained clean. No writes to the snapshot were made by the worker or the verification probe.

## Limitations

This proves the mapped native E2E selectors and this run's file permission boundary only. The native report-bound QA command, signer socket, signed receipt, authoritative gate, and broader sandbox acceptance remain `NOT_RUN`.
