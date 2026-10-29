# S2 bounded synthetic E8 helper run — 2026-10-28

## Result and scope

The focused synthetic-helper file passed at exact repository HEAD
`05a443c76b6453c48a103aa136576ba487c80b44`: **5 passed, 0 failed, 0 skipped**, with one
pytest-asyncio deprecation warning. This is local functional evidence for report labels and the
safe synthetic candidate/budget flow only. It does **not** establish E8 acceptance, real E5/E6/S1
qualification, sandbox isolation, blocked egress, process/crash containment, STOP, resume/restart,
out-of-scope mutation behavior, external-candidate comparison, or operator choice.

The earlier exact run at `23c4a678358728fb7b65ceb84e2fe70a636f97ca` is superseded for current-head
evidence by the later terminology-only change 0496, which renamed the synthetic gate verdict so it
cannot be confused with a real acceptance verdict. Its result remains historical evidence for the
then-current exact source/test revision; this record covers the updated label contract.

## Exact run

- Command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`
- HEAD before and after: `05a443c76b6453c48a103aa136576ba487c80b44`
- Python: CPython 3.14.3
- pytest: 8.4.2
- Source SHA-256, `tools/vst/slice.py`:
  `363FFFF1449BD34B794A1EB260244F0843DFCF2AD492EFA20FFEE1E942D085ED`
- Test SHA-256, `tests/vst/test_s2_e8_synthetic_lifecycle.py`:
  `B4A11FEC4C6BF3169CA10C69273A62473D8908B91620B3196B8CC3C4401F2D2B`
- Collected and executed selectors (5):
  - `test_report_explicitly_does_not_claim_real_e8_acceptance`
  - `test_restricted_process_stop_resume_and_mutation_scenarios_remain_unrun`
  - `test_report_marks_budget_overflow_as_rejected`
  - `test_bounded_synthetic_candidate_report_has_no_worker_remote`
  - `test_caller_probe_values_are_not_upgraded_to_environment_egress_evidence`
- Output summary: `5 passed, 1 warning in 13.07s`; process exit code 0.
- Warning: pytest-asyncio emitted a deprecation warning for
  `asyncio.get_event_loop_policy`; it did not fail the run.
- The sole test fixture uses `tempfile.TemporaryDirectory` as a context manager around the helper
  call, so teardown invokes cleanup for that synthetic work root. No scan or operation was made on
  prior pytest temporary roots.

## Earlier setup attempts retained for provenance

These attempts are failures, not acceptance evidence. Each stopped before a test body ran; no
process/crash, STOP, resume/restart, mutation, egress, or real system scenario ran.

| HEAD | Result | Primary cause | Provenance limit |
|---|---|---|---|
| `83ffe604bcba9293407741510f14420fed580b68` | 6 setup errors, 0 test bodies | Initial synthetic `Supervisor` omitted its distinct required operator key. | Exact source/test hashes were not recorded. |
| `99368ebbb2110706f108a75bfeae224b96026d92` | 6 setup errors, 0 test bodies | `git commit` summary contaminated captured stdout before `rev-parse HEAD`; the receipt got a multi-line candidate hash. | CPython 3.14.3, pytest 8.4.2; source SHA-256 `14327C5F83E1E76DFD6C85D3CE50A57879EF6F9C8965072E8D7A51C42FC39DF2`; test SHA-256 `0FB3C665C768BF2DDA2075B78A5A8F8EE26EF7FD10690E2C356F17BACF57D69C`. |
| `43c5d3d327f529674ca96a93669e5116147e1219` | 6 setup errors, 0 test bodies | Restarted synthetic `Supervisor` lacked required trusted run/probe/operator context after store restart. | Shared test file changed concurrently after hash capture; this attempt is not exact test-source evidence. Captured source hash `DF35B6D6237796ADFDB185DADF5EBCD2E48085EE154580F546310305B3EADD84`; captured pre-change test hash `0FB3C665C768BF2DDA2075B78A5A8F8EE26EF7FD10690E2C356F17BACF57D69C`. |

## Worktree and scope

Before execution, the only worktree status entry was the pre-existing protected untracked
`docs/sdlc/evidence/s2-functional-test-run.md`. After the run, the status contains that file plus
the two new evidence/change-record files authored for this result; the test command did not change
source or test files. The protected file was not opened, modified, staged, or removed. No other
tests, system probes, service actions, credential provisioning, or E5 attestation were part of
this run.
