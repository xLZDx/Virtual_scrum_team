# S2 section 9 contract rerun at a2a5d5a

Date: 2026-10-25

- Repository: `Virtual_scrum_team-s2`; branch `s2-isolated-worker-sandbox`.
- Exact repository HEAD before and after: `a2a5d5a34d45c02c095c993260e313078f75bde9`.
- Test owner/executor: `functional-test-reviewer`, GPT-6 Luna, low effort.
- Environment: Windows NT 10.0.26300.0, PowerShell 7.6.7, Python 3.14.3, pytest 8.4.2.
- Worktree before and after: clean; no files changed.

## Exact command

```text
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_v2_manifest_rejects_missing_or_untrusted_mandatory_parser_pin tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_v2_waiver_scope_never_includes_failure_or_review_rejection tests/vst/test_s2_contract_gate.py::test_v2_waiver_allows_only_named_non_execution_results
```

Result: exit 0; 12 passed, 0 failed, 0 skipped in 0.61 seconds; one pytest-asyncio deprecation warning (`asyncio.get_event_loop_policy`, slated for removal in Python 3.16).

## Acceptance mapping

- **S2.D1 / VST-025:** rejects missing mandatory command/pin, unknown parser ID/version, parser digest mismatch and caller-supplied parser implementations outside the trusted catalog.
- **S2.D2 / VST-026:** rejects waiver coverage of `FAIL`, `MODIFY`, `NO_GO`, and `PASS`; accepts only the named non-execution outcomes `NOT_RUN`, `INCONCLUSIVE`, and `BLOCKED`.

No mutation, CI, process-kill, or kill-table scenario ran. This evidence closes the focused local contract selectors only; it does not establish operator signing or full runtime acceptance.
