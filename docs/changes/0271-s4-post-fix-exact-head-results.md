# 0271 S4 post-fix exact-head QA results

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/candidate:** `s4-reproducible-qa-automation` / `fd49fad2bac249f329f4020ca5c1d55e38aa9bd7`  
**Registry source:** `1012a5e15715777ea70fc63ef0c132e625eb7975`  
**Dependency lock SHA-256:** `b4e6eea19e0e0d498d82756fe94ed343b8ed147a660a876b50b8283ba32a51e3`

## What changed

- Recorded the six-category S4 run at candidate `fd49fad` and a same-head regression-category rerun.
- Preserved the original report that had one failed selector, followed by evidence from three isolated passes and a full-category rerun where that selector passed.
- Recorded a limitation: the original child pytest invocation used `--tb=no`, so the assertion that failed cannot be identified from saved evidence. Do not label the cause as known or the result as waived.
- Updated S4 state, backlog, and lessons to separate the observed failure, later non-reproduction, and outstanding platform/policy gates.

## Exact-head results

The test executors used a disposable test-only clone at `D:\Temp\vst_s4_acceptance_fd49fad_20261025T`; it was not a Git worktree and was not used for development. All source and documentation development remained in `D:\Repo\Virtual_scrum_team`.

| Category | Run | Result | Eligible selectors | Passed | Failed | Skipped | Policy `NOT_RUN` | Nodes (passed/failed/skipped) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Functional | `s4-fd49fad-functional-20261025t` | PASS | 59 | 59 | 0 | 0 | 0 | 114 / 0 / 0 |
| Integration | `s4-fd49fad-integration-20261025t` | FAIL | 48 | 42 | 0 | 6 | 36 | 84 / 0 / 10 |
| API | `s4-fd49fad-api-20261025t` | FAIL | 693 | 688 | 0 | 5 | 12 | 1,492 / 0 / 10 |
| E2E | `s4-fd49fad-e2e-20261025t` | INCONCLUSIVE | 55 | 55 | 0 | 0 | 1 | 59 / 0 / 0 |
| Regression, initial | `s4-fd49fad-regression-20261025t` | FAIL | 855 | 843 | 1 | 11 | 49 | 1,748 / 1 / 20 |
| Regression, rerun | `s4-fd49fad-regression-repeat-20261025t` | FAIL | 855 | 844 | 0 | 11 | 49 | 1,749 / 0 / 20 |
| Seeded failure | `s4-fd49fad-seeded-failure-20261025t` | PASS | 3 | 3 | 0 | 0 | 0 | 3 / 0 / 0 |

The rerun still reports `FAIL` because its 11 platform skips and 49 policy `NOT_RUN` selectors are non-approving. Its child pytest exited 0; capture was complete with no timeout or truncation. The selector `tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_cli_native_collection_binds_candidate_and_repeatable_artifact_chunks` failed once in the initial aggregate run, then passed in the full-category rerun and in three consecutive isolated reruns. This is evidence of a non-reproduced failure, not proof of its cause or proof that it can never recur. The failure remains unexplained because the initial stdout omitted traceback/assertion detail.

Runtime recorded by the candidate-bound reports: Windows 11 x64, CPython 3.14.3, pytest 9.0.3, isolated dependency target `D:\Temp\virtual_scrum_team_qa_f4ef8e7`; candidate and source identities are in each JSONL report. The extra regression rerun took 533.478 seconds, with a 900-second bound and 1 MiB output cap.

## Artifact integrity and limits

- The 18 artifacts from the six-category run were copied into `docs/sdlc/evidence/qa/` and independently compared with the test-only clone by SHA-256 and size: 18/18 matched.
- The rerun's three artifacts were then copied and independently compared: report 4,032,744 bytes (`D153075A4A5555F88B39306AB54A8861CC9B18C1DB93FA24249F5C8B7403AB07`), stdout 8,365 bytes (`37DED27F2E3F702914E317BB3456CF9EE5331B0FFD4A4C814A0C80458A73CFAC`), stderr 101 bytes (`A528B1E4D996E9B60ECCBC8A0592358D1272E47B0EEDCBDEE4F448EE8777562B`).
- No process-kill, timeout, `os._exit`, or kill-table selector was authorized or run. Those selectors remain policy `NOT_RUN`.
- The primary coordinator did not author or execute tests. `functional-test-reviewer` performed the three isolated selector reruns; `e2e-runner` performed the category rerun and artifact copy. Specialist review and the exact-head GPT-PM gate have not been repeated for `fd49fad`.
- An earlier progress message incorrectly described the initial regression run as having zero failed selectors. The final JSONL row recorded one failed selector; this change record and current state use the final evidence.

## Acceptance and next steps

- VST-032 manifest/denominator: exact candidate is bound to the refreshed registry and all six categories collected their registered denominators.
- VST-033 / VST-034 / VST-036: functional and seeded-failure categories pass. API remains non-approving due to platform skips and policy exclusions.
- VST-035: integration, E2E, and regression remain non-approving. The initial regression failure did not recur in four later runs, but its assertion is unknown; platform skips and policy exclusions still prevent a pass.
- VST-037: artifact copy integrity is established for the 18 primary-run artifacts and the three rerun artifacts. No-skip acceptance and a fresh gate receipt remain unavailable.
- Accountable task owner: operator under delegated autonomous continuation. Executor: Codex. Required test owners: `functional-test-reviewer` and `e2e-runner`. Technical owner for external dependency-target provenance and cross-platform runtime is not identified in canonical records.
- Next: determine whether S4's platform-required POSIX selectors can run under the already authorized WSL2 environment; only change QA runner code after defining a compatible pinned interpreter/runtime contract. Keep process-termination cases `NOT_RUN`. Once all in-scope code is complete, refresh the selector registry, execute the required exact-head categories, conduct fresh specialist review, and request exact-head GPT-PM approval. Do not push or merge without that approval.
