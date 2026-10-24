# S5 v3 Store-to-Gate E2E evidence

## Scope

This run exercises the local VST persistence and authoritative-gate boundary with synthetic analyzer receipts. It does not execute AEVE, an adapter, a provider, an external repository, a signer service, or a sandbox.

## Exact candidate and command

- Repository: `D:\tmp\scratch_worktrees\Virtual_scrum_team-s5`
- Branch: `s5-bounded-aeve-evidence`
- Exact full HEAD: `7cd83eac005e318dca5ae8784b25d2c443cdccc0`
- Worktree before run: clean (`git status --short --branch` returned only the branch header).
- Command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider tests/vst/test_s5_v3_store_gate_e2e.py`
- Runtime: Windows PowerShell, Python `3.14.3`, pytest `8.4.2`.
- Result: **3 passed, 0 failed, 0 skipped**, 1.79 seconds; 3 collected.
- Warning: one global `pytest-asyncio` `DeprecationWarning` for `asyncio.get_event_loop_policy`, slated for removal in Python 3.16. It did not affect this synchronous test module.

## Collected IDs and outcomes

| Test ID | S5 acceptance map | Outcome and observed boundary |
|---|---|---|
| `tests/vst/test_s5_v3_store_gate_e2e.py::test_s5_store_round_trips_v3_receipt_and_gate_accepts_only_static_acceptance` | AC-3/4, AC-9 | A v3 `StaticAnalysis` receipt was appended to and read from temporary SQLite Store, then verified by Gate using a separate analyzer key plus file-backed report/source digest resolvers. Only the manifest static-analysis acceptance ID was satisfied; the overall decision remained non-APPROVE because test and review receipts were absent. |
| `tests/vst/test_s5_v3_store_gate_e2e.py::test_s5_store_persisted_stale_v3_receipt_does_not_satisfy_current_head` | AC-10/11 | A structurally persisted receipt for another candidate head remained non-approving and left the static acceptance unmet. |
| `tests/vst/test_s5_v3_store_gate_e2e.py::test_s5_store_persisted_finding_remains_failure_at_authoritative_gate` | AC-7/11 | A persisted receipt with a finding derived `FAIL`; Gate did not credit its static acceptance. |

Report, evidence, and candidate source bytes were created under pytest temporary paths and resolved by hashing those exact files. No repository product source was modified.

## Prior authoring failures retained

1. At test commit `030607975e99acbbe66aefad8fc789fe1f3f577b`, collection failed before execution because the E2E module imported `STORY` from a test module that did not export it. Classification: **test defect**. Corrected in commit `2f4f8cee96d6058aba6f7993236abd2b19715276`, change record 0130.
2. At clean HEAD `2f4f8cee96d6058aba6f7993236abd2b19715276`, all 3 cases failed during fixture construction because the shared receipt helper received `candidate_head` twice. Store and Gate were not reached. Classification: **test defect**. Corrected in commit `7cd83eac005e318dca5ae8784b25d2c443cdccc0`, change record 0132.

These attempts are not counted as flaky or product failures. The final focused run was performed once after the fixture correction; no repeat-rate claim is made.

## Limitations and next work

- V1/v2 golden compatibility remains covered by the existing functional module, not duplicated in this E2E denominator.
- Real analyzer execution, bounded runtime controls, signer provisioning, sandbox isolation, network/write refusal, and full-suite evidence remain `NOT_RUN` or unsupported in this checkout. The S5 plan identifies the missing analyzer identity/runtime and trust provisioning as dependencies; technical service owner is not established there.
- E2E category coverage remains `PARTIAL`; the registry now lists these three nodes alongside its existing synthetic S3 pilot nodes.
