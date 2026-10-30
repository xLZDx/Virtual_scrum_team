# S2-4 bounded preflight mount diagnostics — 2026-10-30

## Purpose and acceptance delta

The authorized S2-4.12c preflight refused an unapproved Windows/host mount but its message did
not identify a safe mount class. This change makes that fail-closed refusal diagnosable without
including raw mount sources or nested usernames. It does not change the rejection predicate or
convert the prior runtime HOLD into acceptance.

## Changed files

- `tools/vst/preflight_host_capture.py`: add sanitized target/filesystem classes, deduplicate
  details, cap rendered findings at eight, and count omitted unique details accurately. The
  refusal still occurs whenever Windows mounts or unapproved host mounts are present.
- `tools/qa/collect_s2_runtime_config_inventory.py`: pin the updated helper SHA-256
  `aafd67378416c869ef527d08a39c97a24831f3c67cebd7bf57d171354e5e1387`.
- `tests/vst/test_s2_preflight_host_capture.py`: add a duplicate-finding regression and retain
  the redaction/classification coverage.
- `tests/vst/test_s2_runtime_config_inventory.py`: update the helper source pin.
- `docs/sdlc/evidence/s2-runtime-qual-8ee40d1a-outcome-20261030.md`: accurately record that the
  one-shot sandbox-probe unit started as the preflight measurement stage; no downstream service,
  bootstrap, claim/probe, or TestRun followed.
- `docs/sdlc/backlog.md`: reconcile S2-4 ownership and checkpoint to the settled delegation and
  actual runtime/code-review evidence.

## Verification evidence

`functional-test-reviewer` ran at base HEAD
`38f843ff958ea67f1692edc392c3b900b87feb68`:

```text
python -m pytest -q tests/vst/test_s2_preflight_host_capture.py::test_mount_inventory_deduplicates_repeated_findings_before_suffix_count tests/vst/test_s2_preflight_host_capture.py::test_mount_inventory_refusal_reports_sanitized_mount_classification tests/vst/test_s2_preflight_host_capture.py::test_mount_inventory_rejects_windows_drive_and_unlisted_host_mount tests/vst/test_s2_runtime_config_inventory.py
36 passed, 1 warning in 14.76s
```

The warning is the existing pytest-asyncio deprecation for `asyncio.get_event_loop_policy`.
The run is reported by the test owner; Codex did not execute the tests.

- Security review: no remaining security/privacy issue; fail-closed behavior unchanged.
- Python review: the deduplicated suffix fix is correct; no further Python correctness findings.
- GPT-PM request `b4b83501-9945-4cb8-9f61-157e525b3db3`, correlated reply `6fd7e3f4-9ed4-530e-861f-6188289a1998`: `ACCEPT — CODE GATE PASSED`, exact attached helper SHA verified, no code BLOCKER/MAJOR/material MINOR. GPT-PM explicitly did not grant runtime authorization.

## Runtime limitation and next action

The previous one-shot authorization `8ee40d1a-27a4-4e1b-9129-292a58959aa3` is consumed. Its
preflight started the one-shot probe service, which refused the namespace before writing an
attestation. No assignment bootstrap, issuer, Supervisor, Runner, dispatch, durable Owner-to-Runner
claim/probe, or report-bound TestRun ran; restricted scenarios remain `NOT_RUN`.

S2-4 remains `IN PROGRESS`; S2-5 remains queued. Codex owns normal commit/push and technical
configuration/evidence reconciliation. The next action is a fresh, narrowly scoped GPT-PM runtime
authorization bound to the committed helper and configuration source pins; only then may
`e2e-runner` execute the permitted one-shot qualification. This record does not authorize a retry,
preflight bypass, or production activation.
