# S2 bounded synthetic E8 helper run — 2026-10-28

## Result

The focused synthetic-helper file passed at exact repository HEAD
`23c4a678358728fb7b65ceb84e2fe70a636f97ca`: **5 passed, 0 failed, 0 skipped**, with one
pytest-asyncio deprecation warning. This is local functional evidence for report labeling and the
safe synthetic candidate/budget flow only. It does **not** establish E8 acceptance, real E5/E6/S1
qualification, sandbox isolation, blocked egress, process/crash containment, STOP, resume/restart,
out-of-scope mutation behavior, external-candidate comparison, or operator choice.

## Exact run

- Command: `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`
- HEAD before and after: `23c4a678358728fb7b65ceb84e2fe70a636f97ca`
- Python: CPython 3.14.3
- pytest: 8.4.2
- Source SHA-256, `tools/vst/slice.py`:
  `6944E77A20E839C562712AD47545A5802F3835ADDA8D26AEA6E066EFED0EBC8B`
- Test SHA-256, `tests/vst/test_s2_e8_synthetic_lifecycle.py`:
  `AD11DF4B16C256D65607B5296AF3768E3751DB4C54444AAF87DB9F70220D08EA`
- Collected and executed selectors (5):
  - `test_report_explicitly_does_not_claim_real_e8_acceptance`
  - `test_restricted_process_stop_resume_and_mutation_scenarios_remain_unrun`
  - `test_report_marks_budget_overflow_as_rejected`
  - `test_bounded_synthetic_candidate_report_has_no_worker_remote`
  - `test_caller_probe_values_are_not_upgraded_to_environment_egress_evidence`
- Output summary: `5 passed, 1 warning in 15.31s`; process exit code 0.
- The test's only work root is scoped through `tempfile.TemporaryDirectory` in a module-scoped
  fixture. The context manager owns cleanup when pytest tears down the fixture. No directory scan
  or operation on prior pytest temporary roots was performed.

## Failed setup attempts retained for provenance

These attempts are failures, not acceptance evidence. Each stopped before a test body ran; no
process/crash, STOP, resume/restart, mutation, egress, or real system scenario ran.

| HEAD | Result | Primary cause | Provenance limit |
|---|---|---|---|
| `83ffe604bcba9293407741510f14420fed580b68` | 6 setup errors, 0 test bodies | Initial synthetic `Supervisor` omitted its distinct required operator key. | Exact source/test hashes were not recorded. |
| `99368ebbb2110706f108a75bfeae224b96026d92` | 6 setup errors, 0 test bodies | `git commit` summary contaminated captured stdout before `rev-parse HEAD`; the receipt got a multi-line candidate hash. | CPython 3.14.3, pytest 8.4.2; source SHA-256 `14327C5F83E1E76DFD6C85D3CE50A57879EF6F9C8965072E8D7A51C42FC39DF2`; test SHA-256 `0FB3C665C768BF2DDA2075B78A5A8F8EE26EF7FD10690E2C356F17BACF57D69C`. |
| `43c5d3d327f529674ca96a93669e5116147e1219` | 6 setup errors, 0 test bodies | Restarted synthetic `Supervisor` lacked required trusted run/probe/operator context after store restart. | Shared test file changed concurrently after hash capture; this attempt is not exact test-source evidence. Captured source hash `DF35B6D6237796ADFDB185DADF5EBCD2E48085EE154580F546310305B3EADD84`; captured pre-change test hash `0FB3C665C768BF2DDA2075B78A5A8F8EE26EF7FD10690E2C356F17BACF57D69C`. |

## Worktree and scope

Before and after the successful run, the only worktree status entry was the pre-existing protected
untracked `docs/sdlc/evidence/s2-functional-test-run.md`; it was not opened, modified, staged, or
removed. No other tests, system probes, service actions, credential provisioning, or E5
attestation were part of this run.
