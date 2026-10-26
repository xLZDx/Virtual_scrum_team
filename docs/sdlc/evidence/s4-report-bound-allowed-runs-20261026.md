# S4 report-bound allowed runtime evidence — 2026-10-26

## Candidate and registry identity

- Report-bound candidate HEAD: `4fe150326a36faf401b045cfa1b9a2e64d89436b`.
- Source/test commit: `96c9c1556e0bd7d7731bbfba40806c4d1e209907`.
- Registry source hash: `9d232d33cd9b788fe5e4418b010ca0a7a29ee9cc1e2b81dd1e88ca72e3601b70`.
- Registry inventory: 905 runnable regression IDs plus 52 policy-excluded `NOT_RUN`; one WSL-only identity selector and three seeded-failure selectors.
- Environment for both reports: Ubuntu 24.04 WSL2, CPython 3.12.3, pytest 9.0.3, runner UID/GID `997:988`, no supplementary groups, no Windows drive mounts in the candidate boundary.

## Accepted permitted selectors

| Run | Category and scope | Result | Evidence |
|---|---|---|---|
| `s4-identity-20261026-r3` | The one AC-16 worker identity selector | **PASS 1/1**, exit 0 | Report row SHA-256 `92034a057c721032373dc5d221375a90b023ccc54b09b1a4516b58055ec36cb4`; stdout range 98–207 bytes. |
| `s4-seeded-failure-20261026-r4` | The three permitted synthetic AC-12 seeded-failure selectors | **PASS 3/3**, exit 0 | Report row SHA-256 `057adf3e2d0150f48d7a4bcd431617cb4a3a377caeb2784ca1d1489411783191`; stdout range 598–696 bytes. |

The report rows and output ranges are appended to `qa/identity.{report.jsonl,stdout.txt,stderr.txt}` and `qa/seeded-failure.{report.jsonl,stdout.txt,stderr.txt}`. Earlier `r2` rows and bytes were preserved. An initial identity failure at candidate `52c3a7d` and its diagnostic cause are retained as history; change 0352 fixes only the temporary socket path, without weakening assertions. The prior seeded `r2` run is also preserved. An unpreserved seed `r3` execution passed in WSL but its host-side artifact return failed; the preserved acceptance run is `r4`.

## Dependency evidence and limits

For both accepted rows, `dependency_content_verified_before=true` and `dependency_content_verified_after=true`. The isolated external dependency target SHA-256 was `94f1a1e0330fe63dbba1bdf8ed173cb8862dbe707a4a654603e281d9cc9cc81f` before and after; all five runtime wheels and versions matched the committed lock. Reports state `dependency_execution_integrity=NOT_VERIFIED`. Therefore this proves exact pre/post inventory and content snapshots, but does not prove prevention or detection of a same-identity change-and-restore during pytest. This limitation is explicit in AC-17 and the runner report.

The report-bound helper was built from committed `tools/qa/worker_exec.c` for candidate `4fe1503`; reported binary SHA-256 `6973df62818be76759f87e1231b6a5dfea4b64c08f16fb19f1b6c77975818e68`, installed identity `0:988:4750`, and embedded source SHA `8c1a5986…`. The source and candidate heads are explicit in the report rows. This is per-run evidence only, not persistent production deployment evidence.

## Exclusions and approval state

- The 52 policy-excluded selectors were not run. Timeout/process-tree termination, process death, mutation, crash/resume, and prohibited kill-table cases remain `NOT_RUN`.
- No broad Windows/WSL/root category matrix was run; this report covers only the selectors listed above.
- The report-bound results do not themselves approve S4. Exact-head GPT-PM adjudication remains pending after specialist review.
- S2 remains Phase 8 `NOT APPROVED`; this S4 sandbox run is not S2 acceptance evidence.

## Specialist review

- `code-reviewer`, GPT-6 Luna, low effort: no actionable finding on candidate diff `52c3a7d..4fe1503`.
- `security-reviewer`, GPT-6 Luna, medium effort: no BLOCKER/MAJOR/MINOR finding on the same diff. The reviewer explicitly did not upgrade the runtime report's `NOT_VERIFIED` dependency-integrity field.
- Neither review ran tests or changed files. Their reviewed scope is the committed S4 diff; broader platform acceptance remains outside these conclusions.

## Provenance and ownership

- Test execution: designated `e2e-runner` at GPT-6 Luna; report-bound results are inherited from that agent and independently checked for their candidate/source/manifest IDs in the preserved JSONL rows.
- Accountable project owner: operator. Evidence collation and next gate coordination: Codex. Exact-head product/gate decision: GPT-PM.
- No push, PR, merge, acquisition, or Temporal execution is authorized by this evidence.
