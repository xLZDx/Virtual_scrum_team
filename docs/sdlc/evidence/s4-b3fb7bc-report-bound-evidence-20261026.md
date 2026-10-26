# S4 report-bound evidence at candidate `b3fb7bc` — 2026-10-26

## Candidate and prerequisites

- Candidate HEAD: `b3fb7bc38aee308520e29091707e4c6cb3d46da1`.
- S4 code/test source commit: `62e9c946bdb66fccc6eaf0b164b8c5e178592cf8`.
- Category registry SHA-256: `aa9c7370d87500d280771d8eb356f8a3debd903238f48f763af4b0c7c0c2b72b`; the registry binds the changed test source to `62e9c94`.
- The verified trusted wheelhouse is `D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse`, containing the six hash-pinned wheels from `tools/qa/requirements.lock`. A fresh offline Windows dependency target was prepared for this run; its SHA-256 was `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84`.
- The stale, pre-existing installed target `D:\Temp\virtual_scrum_team_qa_f4ef8e7` was not modified. Its inventory mismatch is recorded in change 0355.

## Windows seeded-failure result

The designated `e2e-runner` executed the three policy-permitted seeded-failure selectors through the report-bound runner on a clean temporary runtime snapshot at the exact candidate HEAD.

| Run | Result | Candidate / registry | Dependency-content evidence |
|---|---|---|---|
| `s4-seeded-failure-20261026-win-b3fb7bc-r1` | **PASS 3/3**, exit 0 | Candidate `b3fb7bc38aee308520e29091707e4c6cb3d46da1`; registry SHA above | `dependency_content_verified_before=true`; `dependency_content_verified_after=true`; target SHA-256 `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84` both before and after |

Report row SHA-256: `480762444bacc8a9ec853b8802a66f6ed9929382d945d0aacae4f61eecbde172`.

Byte-preserving snapshots of the runtime report and complete stdout/stderr artifact files are retained under [`qa/s4-seeded-failure-20261026-win-b3fb7bc-r1/`](qa/s4-seeded-failure-20261026-win-b3fb7bc-r1/):

- `report.jsonl`: 57,303 bytes; SHA-256 `227ac94b7e8e9601e11087775651abed396764083e4156edf938821ad9d6dff1`.
- `stdout.txt`: 800 bytes; SHA-256 `b306fd6308f5c5b80b8e17fe269382260d6dd0a5fedc84cc6cf14482ddae55b1`.
- `stderr.txt`: 101 bytes; SHA-256 `a528b1e4d996e9b60eccbc8a0592358d1272e47b0eedcbdee4f448ee8777562b`.

The report explicitly keeps AC-17 same-identity mutation/change-and-restore during pytest as `NOT_VERIFIED`; the pre/post snapshots prove only the stated before/after inventory and content checks.

## WSL result and exclusions

- WSL seeded-failure and the WSL-only AC-16 identity selector at this candidate are **NOT_RUN**. Several bounded staging attempts failed before candidate/target preparation and before the report-bound CLI. The final attempt sent the input archive in one `wsl.exe` process but WSL did not expose the file for hash verification (`/tmp/vst-s4-b3fb7bc-r5.tar.gz` absent). No WSL selector was started. Controller/output files are in `D:\Temp\vst-s4-b3fb7bc-wsl-atomic-r5.py` and `D:\Temp\vst-s4-b3fb7bc-wsl-atomic-r5-console.txt`.
- This is a staging/tool-path failure, not a WSL test failure. Its precise root cause is not verified. Prior exact report-bound WSL evidence remains at older candidate `4fe1503`: AC-16 identity passed 1/1 and seeded-failure passed 3/3 (see `s4-report-bound-allowed-runs-20261026.md`).
- The restricted-root profile was not run because its installed helper did not match the required candidate/source identity. The helper was not modified.
- All 52 policy-excluded selectors remain `NOT_RUN`. No process-kill, process-death, timeout-termination, mutation, crash/resume or prohibited kill-table selector was executed.

## Ownership and next action

- Accountable task owner: operator.
- Evidence coordination and local records: Codex.
- Test execution: designated `e2e-runner`.
- Next: preserve this Windows PASS and the explicit WSL `NOT_RUN`; obtain a supported WSL runtime transfer mechanism before another WSL exact-candidate attempt. Do not weaken the report-bound or dependency-integrity contract.
