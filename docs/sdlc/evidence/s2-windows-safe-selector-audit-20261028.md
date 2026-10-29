# S2 Windows containment selector audit — 2026-10-28

## Scope and result

The designated `e2e-runner` reviewed the S2 Windows containment selectors in the canonical
repository at source/test commit `d5001797cb94113efd9a8dc26e4a15f2dc130976`. Current repository
HEAD is `b639efc1d39fb4bf663785a652887d82312261d9` and contains documentation-only commits after
the source/test commit. The review found **no selector that proves real Windows containment while
staying inside the current restrictions**. No tests ran and no files were changed by the test agent.

## Candidate dispositions

| Selector | Evidence it can provide | Restriction / limitation | Disposition |
|---|---|---|---|
| `tests/vst/test_s2_runner_lifecycle.py::test_strict_windows_launch_suspends_assigns_job_then_resumes_before_command` | Launch-ordering behavior through a synthetic command callback | Windows APIs are mocked; it does not establish real Job Object containment. Existing code evidence does not make it a runtime containment result. | Not rerun for this criterion |
| `tests/vst/test_e4_runner.py::test_stray_descendant_is_killed_after_the_root_command_exited_normally` | Descendant cleanup under the E4 runner | Depends on terminating a descendant, which is prohibited in the current scope. | `NOT_RUN` |
| E4 process/descendant-containment selector family | Real containment under process exit/cleanup | Explicitly excluded by the current process-termination boundary. | `NOT_RUN` |

## Acceptance status and next action

`VST-013` remains `PARTIAL / NOT_VERIFIED`; this audit is a selector review, not runtime proof.
No test result, platform pass, or waiver is inferred. Codex owns coordination; GPT-PM owns
adjudication of an alternative acceptance path; the operator owns any scope exception that changes
the existing restriction. Until an allowed genuine containment scenario is identified, preserve
`NOT_VERIFIED` and keep process/descendant scenarios `NOT_RUN`.
