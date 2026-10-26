# S4 Windows regression report-bound evidence

## Candidate and runtime

- Candidate HEAD: `bdc8e3be7d74ca20a380ecade6acd4e277e9c4dd`.
- Registry source HEAD: `3885d8a143d4cfa95cd3f0c0e5c840a6ed72dfda`.
- Registry SHA-256: `7b03dd4ac32b671a5e9a9a95a04c717dd6af2628dfda5d485d712788a4f2dd7a`.
- Registry contains 963 selectors and 53 committed policy `NOT_RUN` selectors.
- Runtime: Windows 11, CPython 3.14.3, pytest 9.0.3, pluggy 1.6.0.
- Candidate snapshot: `D:\Temp\vst-s4-regression-candidate-20261026-bdc8e3b`; it was clean at exact HEAD before execution.
- Fresh dependency target: `D:\Temp\vst-s4-regression-target-20261026-bdc8e3b`.
- Wheelhouse: `D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse`.
- Dependency lock SHA-256: `6e23fdd343a14e9d85a27f6d86cfb4498c1af9d33281e05ca5a3ff331c45e691`.
- Target SHA-256 before and after: `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84`.

## Policy selector contract check

Before the category run, only this selector was executed on the exact candidate
snapshot:

```text
C:\Python314\python.exe -m pytest -vv --tb=long -ra --show-capture=all -p no:cacheprovider tests/qa/test_s4_functional_runner_contracts.py::test_s4_audited_e4_terminating_selectors_remain_not_run
```

Result: exit 0, 1 passed in 12.73 seconds. Its stdout SHA-256 is
`7e0ab66e6fe0f7f84550a849e778e26ba672aef0b6d2bf87892813a96441a4bc`; stderr was
empty. Raw evidence is under
`D:\Temp\vst-s4-policy-contract-evidence-20261026-bdc8e3b\`.

The committed forbidden timeout selector
`tests/vst/test_e4_runner.py::test_root_that_survives_the_kill_gives_exit_minus_four`
is present in the 53-row policy `NOT_RUN` set and absent from both the category's
expected selectors and executed node IDs. The regression report's complete
53-entry `not_run_test_reasons` mapping equals the committed registry mapping.

## Report-bound regression

Run ID: `s4-regression-20261026-win-bdc8e3b-r1`.

Exact command:

```text
C:\Python314\python.exe -m tools.qa.run --category regression --repo-root D:\Temp\vst-s4-regression-candidate-20261026-bdc8e3b --dependency-target D:\Temp\vst-s4-regression-target-20261026-bdc8e3b --dependency-wheelhouse D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse --scratch-root D:\Temp\vst-s4-regression-scratch-20261026-bdc8e3b --run-id s4-regression-20261026-win-bdc8e3b-r1 --expected-head bdc8e3be7d74ca20a380ecade6acd4e277e9c4dd --timeout-seconds 900 --report-path docs/sdlc/evidence/qa/regression.report.jsonl --stdout-path docs/sdlc/evidence/qa/regression.stdout.txt --stderr-path docs/sdlc/evidence/qa/regression.stderr.txt
```

The runner's report row is `INCONCLUSIVE`, with row `exit_code=0`; the outer CLI
exit code is 1 because committed policy selectors remain `NOT_RUN`. The only
report reason is `one or more inventory selectors are explicitly NOT_RUN by
policy`.

| Measure | Result |
| --- | --- |
| Expected Windows regression selectors | 897 |
| Passed selector IDs | 897 |
| Failed selector IDs | 0 |
| Skipped / xfailed / xpassed selector IDs | 0 / 0 / 0 |
| Concrete collected and executed pytest nodes | 1,845 / 1,845 |
| Policy `NOT_RUN` selectors | 53; exact mapping matches registry |
| Windows-unassigned selectors | 9 |
| Forbidden timeout selector expected / executed | No / No |
| Unexpected candidate changes | None |

The five S2 selectors that failed in the prior regression all passed in this run:

- `tests/vst/test_s2_runner_lifecycle.py::test_bounded_source_preflight_rejects_before_pack_or_index_writer`
- `tests/vst/test_s2_runner_lifecycle.py::test_cumulative_target_storage_cap_rejects_before_pack_process_starts`
- `tests/vst/test_s2_runner_lifecycle.py::test_hook_free_publication_transfers_source_only_commit_without_running_pre_push`
- `tests/vst/test_s2_runner_lifecycle.py::test_source_object_alternates_are_rejected_before_pack_or_index_writer`
- `tests/vst/test_s2_runner_lifecycle.py::test_synthetic_backend_fast_forward_and_conflicting_branch_and_pr_refs`

This run establishes passing outcomes for those selectors at the current candidate;
it does not classify the earlier discrepancy as a flake.

## Artifact integrity

- Appended report row SHA-256:
  `0eb134b9ab349524587167b8a87e61b5902a3269b2fe92ece58bd2965a6921c7`.
- Full report file SHA-256:
  `900c4b481d5963b8a50878b53931d99db4b4f8f14c75d3a4b72c059998c7a052`.
- Full stdout file SHA-256:
  `24e8770b92bd152f6fcca28e4c2edd5226f8aa62f3c88a634467ed8fef9f6f60`.
- Full stderr file SHA-256:
  `a528b1e4d996e9b60eccbc8a0592358d1272e47b0eedcbdee4f448ee8777562b`.
- Reported stdout append range: bytes `[12789, 14944)`, 2,155 bytes; range SHA-256
  `a3a98c6b4fd11c3056b263b4b09ace1f4c4033a75cd74778fa96a5a3d8c2a2ad`.
- Reported stderr append range: bytes `[101, 101)`, empty; range SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- The candidate worktree changed only the fixed append-only report and stdout
  artifacts. Prefix checks against the Windows CRLF checkout baseline passed for
  all three artifacts; the report/stdout ranges bind the newly appended bytes.
- The 53 `NOT_RUN` rows, `selection.json`, `events.json`, raw report/stdout/stderr,
  controller output, exact command, and before/after target evidence are preserved
  under `D:\Temp\vst-s4-regression-evidence-20261026-bdc8e3b\`. The same raw evidence is now retained in-repository under `docs/sdlc/evidence/qa/s4-regression-20261026-win-bdc8e3b-r1/`. The raw report row SHA-256 is `0eb134b9ab349524587167b8a87e61b5902a3269b2fe92ece58bd2965a6921c7`; the full report SHA-256 remains `900c4b481d5963b8a50878b53931d99db4b4f8f14c75d3a4b72c059998c7a052`.

No broad E2E category was rerun. No source or registry file was changed, and no
commit was created by this run.
