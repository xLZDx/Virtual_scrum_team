# S2 pre-0473 schema-v5 recovery-history compatibility attempt 1

Historical failed run; superseded by [attempt 2](s2-pre0473-schema-v5-compatibility-20261028-attempt2.md), where the fresh-Store compatibility and focused S2 groups passed after the Store fix.

## Scope and identity

This attempt adds a deterministic in-memory Store fixture containing the exact seven-field `PREDECESSOR_GENERATION_STOPPED` / `PENDING` history event used by the pre-0473 schema-v5 writer. The fixture appends the same payload to both the runner side table and authenticated Store NOTE history, so validation observes a well-formed event chain. Negative variants keep the event chain valid while altering one legacy field.

| Field | Value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` |
| Committed base HEAD | `7120e2c647cc95703704905efa76de735ca8d0ec` |
| Interpreter | `C:\Python314\python.exe`, Python 3.14.3 |
| Test file | `tests/vst/test_s2_persistent_runner_service.py` |
| Test file SHA-256 at final attempt | `8a46e1f6252d744a99c4938f9ead91f7b0180bb784e0f5eda6d0b26e6cf48f89` |
| Store source SHA-256 at final attempt | `347bcd76855ba61c5d712b4401de58d4170f2cb4002aed997ec0a39983d24cef` |
| Test diff Git blob ID | `c8e7e0ad9346fcca18750050a3aa88a4f57fcfd3` |
| Store diff Git blob ID | `b2a2aa9c5715440c1d683d8c4caf8f11c88c6fbe` |
| Current whole-worktree binary diff Git blob ID | `64113ce1e9a712fbbd836498f4314ef081baaede` |

The whole-worktree diff includes concurrent edits in `docs/sdlc/STATE.md` and `tools/qa/install_wsl_runtime.ps1`; those files were not changed by this test role. The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not read or modified.

## Added regression coverage

| Node ID | Contract under test |
|---|---|
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_remains_readable_after_0473` | Exact old seven-field event remains readable through claim-status and permits the separately authorized successor when PENDING is authenticated in Store history. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[unexpected-legacy-field]` | Additional fields are outside the closed legacy event shape and must fail closed. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[predecessor-mismatch]` | A legacy record claiming `EXECUTION_RESERVED` where the recorded prior state is `PENDING` must fail closed. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[grant-mismatch]` | A record bound to another grant must fail closed. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[claim-digest-mismatch]` | A record with a different grant payload digest must fail closed. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[not-a-successor-generation]` | The recovery generation cannot equal the predecessor claim's generation. |

## Commands and results

The current attempt command was:

```text
C:\Python314\python.exe -m pytest -q -rs -x -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_remains_readable_after_0473 tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields
```

Result: **2 passed, 1 failed, 0 skipped; exit 1**, with one pytest-asyncio deprecation warning (`asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16). The valid legacy node passed; the `unexpected-legacy-field` variant passed its fail-closed assertion. Pytest stopped at the first failing parameter because of `-x`; the remaining three negative variants did not run.

The failing exact node ID was:

```text
tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[predecessor-mismatch]
```

At `tests/vst/test_s2_persistent_runner_service.py:287`, `runner_execution_claim_status()` did not raise `StoreError` after only `predecessor_state` was changed from `PENDING` to `EXECUTION_RESERVED`; the event remained authenticated and otherwise bound to its claim. This contradicts the test's fail-closed contract. No later E1, E2, or E6 groups ran. No source files were edited by this test role.

## Earlier attempt in this task

Before the implementation owner reported a compatibility source update, the same focused command used Python 3.14.3 and stopped on the positive legacy node at `acquire_lease(attempt=2)`: Store raised `StoreError: prior runner execution 'grant-1' is INDETERMINATE and blocks continuation` at `tools/vst/store.py:3119`. The claim-status assertion immediately before that point passed. Store source SHA-256 at that earlier execution was `520ef1be5653980713cce9889f750bcc11273d7c3fbbc73bad0fdc3dfb491dc1`.

After the parent confirmed successor eligibility was implemented, the current attempt passed the positive case and then exposed the separate mismatched-predecessor validation defect above. The current source SHA-256 is recorded in the identity table.

## Limits and next action

The fixture writes a deterministic in-memory event chain and tests Store history parsing; it does not start a runner, kill a process, simulate a crash/recovery runtime, mutate deployed data, or exercise E8/policy selectors. Relevant approved S2 regression groups remain `NOT_RUN` pending correction of the fail-open mismatched predecessor case. Next action: Codex's Store implementation owner must reject the mismatch in verified event replay; then the functional-test reviewer reruns the six legacy nodes and assigned focused S2 groups against the corrected source.
