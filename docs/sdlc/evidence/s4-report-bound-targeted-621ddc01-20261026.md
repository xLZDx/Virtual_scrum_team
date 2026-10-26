# S4 targeted report-bound acceptance — 2026-10-26

## Scope and exact candidate

- Candidate HEAD: `621ddc01d1b5bbf701ccced7bb073c26e89c8c07`.
- Category registry: `docs/qa/categories.json`, SHA-256 `7b03dd4ac32b671a5e9a9a95a04c717dd6af2628dfda5d485d712788a4f2dd7a`; registry source head `3885d8a143d4cfa95cd3f0c0e5c840a6ed72dfda`.
- Registry contains 963 selector assignments; 53 have no runtime profile and remain policy `NOT_RUN`. The two supported requested categories assign one WSL-only AC-16 identity selector and three Windows/WSL AC-12 seeded-failure selectors each.
- Only those seven assigned runs were requested here: Windows seeded-failure 3/3, WSL identity 1/1, and WSL seeded-failure 3/3. No broad category/matrix, root profile, timeout, process-kill/death, crash, or mutation selector ran.
- AC-17 same-identity in-run dependency change-and-restore remains `NOT_VERIFIED`. The synthetic selector `tests/qa/test_s4_dependency_provenance.py::test_s4_runner_reports_post_execution_dependency_mutation` was not part of these three targeted runs; it did pass in the separate Windows regression at code-identical candidate `bdc8e3be7d74ca20a380ecade6acd4e277e9c4dd`. That test injects a persistent change into a synthetic target and proves post-run detection, not change-and-restore during an actual pytest process.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved and not edited. No source or test files were changed. No commit was created.

## Acceptance matrix

| Item and meaning | State | Evidence | Remaining acceptance / blocker | Next action and owner |
|---|---|---|---|---|
| Windows AC-12 seeded-failure (three synthetic invalid-input/rejected-outcome cases) | **PASS 3/3**, report exit 0 | Run `s4-seeded-failure-20261026-win-621ddc-r1`; exact selectors and hashes below. Candidate and registry match. Dependency target verified before/after with identical hash. | In-run same-identity dependency mutation/change-and-restore protection remains `NOT_VERIFIED` under AC-17. | Codex records evidence; GPT-PM owns exact-head gate adjudication. |
| WSL AC-16 identity (runner UID/GID 997:988 to fixed worker identity boundary) | **PASS 1/1**, report exit 0 | Run `s4-identity-20261026-wsl-621ddc-r2`; report binds UID/GID 997:988, no supplementary groups, no Windows drive mounts, exact helper version/head. | AC-17 remains `NOT_VERIFIED`; this run does not cover broader matrix profiles. | Codex records evidence; GPT-PM owns exact-head gate adjudication. |
| WSL AC-12 seeded-failure (same three synthetic cases under Ubuntu 24.04) | **PASS 3/3**, report exit 0 | Run `s4-seeded-failure-20261026-wsl-621ddc-r2`; exact selectors and hashes below. Candidate and registry match; WSL target verified before/after. | AC-17 remains `NOT_VERIFIED`; this run does not cover broader matrix profiles. | Codex records evidence; GPT-PM owns exact-head gate adjudication. |
| AC-17 in-run dependency integrity (detect same-identity mutation/change-and-restore) | **NOT_VERIFIED / NOT_RUN** | Not selected or executed by this task. All three report rows say `dependency_execution_integrity=NOT_VERIFIED`. | Requires the separately authorized AC-17 scenario and exact runtime evidence. | GPT-PM adjudicates whether to authorize/require this acceptance; Codex preserves the status meanwhile. |
| 53 profile-less policy exclusions | **NOT_RUN** | Registry has 963 selectors, of which 53 have no runtime profile. The three report rows have no unexpected selectors and only the requested IDs executed. | Excluded by current policy. | Keep `NOT_RUN`; policy owner/operator decides any future policy change. |

## Selector assignments and exact results

### Windows seeded-failure

- Run ID: `s4-seeded-failure-20261026-win-621ddc-r1`.
- Candidate: `621ddc01d1b5bbf701ccced7bb073c26e89c8c07`; profile `windows-cpython-3.14.3`; CPython 3.14.3; pytest 9.0.3.
- Selectors, all **PASS**:
  - `tests/qa/test_s4_seeded_failure_contracts.py::test_s4_seeded_invalid_approve_decision_is_rejected_and_observed`
  - `tests/qa/test_s4_seeded_failure_contracts.py::test_s4_seeded_invalid_task_manifest_is_rejected_and_observed`
  - `tests/qa/test_s4_seeded_failure_contracts.py::test_s4_seeded_skipped_required_test_derives_fail_and_is_observed`
- Outer command (from canonical checkout working directory):

  ```powershell
  & 'C:\Python314\python.exe' -m tools.qa.prepare_dependencies --repo-root 'D:\Temp\vst-s4-targeted-621ddc01-win' --wheelhouse 'D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse' --dependency-target 'D:\Temp\vst-s4-targeted-621ddc01-win-deps'
  $env:PYTHONPATH='D:\Temp\vst-s4-targeted-621ddc01-win-deps'
  $env:PYTHONPYCACHEPREFIX='D:\Temp\vst-s4-targeted-621ddc01-win-pycache'
  & 'C:\Python314\python.exe' -m tools.qa.run --category seeded-failure --repo-root 'D:\Temp\vst-s4-targeted-621ddc01-win' --dependency-target 'D:\Temp\vst-s4-targeted-621ddc01-win-deps' --dependency-wheelhouse 'D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse' --scratch-root 'D:\Temp\vst-s4-targeted-621ddc01-win-scratch' --run-id s4-seeded-failure-20261026-win-621ddc-r1 --expected-head 621ddc01d1b5bbf701ccced7bb073c26e89c8c07 --report-path docs/sdlc/evidence/qa/seeded-failure.report.jsonl --stdout-path docs/sdlc/evidence/qa/seeded-failure.stdout.txt --stderr-path docs/sdlc/evidence/qa/seeded-failure.stderr.txt
  ```

- Candidate snapshot was made with `git clone --no-hardlinks --no-checkout D:\Repo\Virtual_scrum_team D:\Temp\vst-s4-targeted-621ddc01-win`, detached checkout at the exact candidate, initially clean status, and registry SHA as above.
- Report row SHA-256 (compact JSON bytes, excluding trailing LF): `18ed4fa2f4f3c0e18de2310df2116a34772269568317817b76db013d5e9c8df1`; row byte range 49,711–57,302.
- Dependency target SHA-256 before and after: `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84`; report says content verified both times. Independently captured sorted file-hash inventory before/after compared equal; each inventory listing SHA-256 `acbab3969a756dc86b2ba3d0b1b286d7df319dce978ba50c891037101502ff38`.
- Full preserved files under [`qa/s4-seeded-failure-20261026-win-621ddc-r1/`](qa/s4-seeded-failure-20261026-win-621ddc-r1/):
  - `report.jsonl`: 57,302 bytes; SHA-256 `99e90182e7e847f7958bc4c6632bdbbefdd0b9c40e721dd95aca31046be86c51`.
  - `stdout.txt`: 800 bytes; SHA-256 `afaa187b016797020317098148216f84bebbf5482d0c5acf59b043607e5ff9bd`.
  - `stderr.txt`: 101 bytes; SHA-256 `a528b1e4d996e9b60eccbc8a0592358d1272e47b0eedcbdee4f448ee8777562b`.
- This report row appended 100 stdout bytes at range 700–800 and zero stderr bytes at range 101–101; earlier bytes in those full files were preserved.

### WSL identity

- Run ID: `s4-identity-20261026-wsl-621ddc-r2`.
- Selector: `tests/qa/test_s4_functional_worker_identity.py::test_s4_worker_helper_drops_runner_identity_and_denies_runner_sentinels` — **PASS 1/1**, exit 0.
- Candidate: exact `621ddc01d1b5bbf701ccced7bb073c26e89c8c07`; profile `wsl-ubuntu-24.04-cpython-3.12.3`; registry SHA as above.
- Report runtime identity: UID 997, GID 988, supplementary groups `[]`. Candidate boundary `/tmp/vst-s4-candidate/repo`; `windows_drive_mounts_present=false`; mountinfo SHA-256 `1a6414f104a4890ee6f36ba7af5cbe1d516336b42f3ac15ff72353dc10542446`.
- Fresh target path: `/tmp/vst-s4-621ddc01-identity-deps-r6`; target SHA-256 before and after `94f1a1e0330fe63dbba1bdf8ed173cb8862dbe707a4a654603e281d9cc9cc81f`; content verified before/after. This WSL target contains the five platform-applicable locked wheels.
- Report row SHA-256 (compact JSON bytes, excluding trailing LF): `dc34f2b945d211271165cdc2a37b9335d018351c3ea9f73b1afe3b53e29e7f89`; row byte range 9,522–14,243.
- Full preserved files under [`qa/s4-identity-20261026-wsl-621ddc-r2/`](qa/s4-identity-20261026-wsl-621ddc-r2/):
  - `report.jsonl`: 14,243 bytes; SHA-256 `136fec2853d1cebb836554280fe39a07f56704229f95fde984bc56ae37e41653`.
  - `stdout.txt`: 316 bytes; SHA-256 `228505be0be36ef2b1797d6b577fdefd9dffee8850efc9502ebff5376aae9e09`.
  - `stderr.txt`: 0 bytes; SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- This row appended stdout bytes 207–316 and zero stderr bytes 0–0; existing earlier bytes were preserved.

### WSL seeded-failure

- Run ID: `s4-seeded-failure-20261026-wsl-621ddc-r2`.
- The same three exact selectors listed in the Windows section all **PASS**; exit 0.
- Candidate, profile, registry, UID/GID/groups, candidate boundary, mountinfo SHA, and `windows_drive_mounts_present=false` match the WSL identity row.
- Fresh separate target path: `/tmp/vst-s4-621ddc01-seeded-deps-r6`; target SHA-256 before and after `94f1a1e0330fe63dbba1bdf8ed173cb8862dbe707a4a654603e281d9cc9cc81f`; content verified before/after.
- Report row SHA-256 (compact JSON bytes, excluding trailing LF): `ab911c4b1028506dec8e07f4cc85a8b743306b82e944dc813fa497ab5a1fff6e`; row byte range 49,703–57,406.
- Full preserved files under [`qa/s4-seeded-failure-20261026-wsl-621ddc-r2/`](qa/s4-seeded-failure-20261026-wsl-621ddc-r2/):
  - `report.jsonl`: 57,406 bytes; SHA-256 `6c6d9f62693220a59c735b71a0a6623c773fa794fd80050183cdac83aa9d8f8b`.
  - `stdout.txt`: 784 bytes; SHA-256 `f25166f5db672a722b55c798a1508c7ce587675e3383caf9579781dd1e4e4b03`.
  - `stderr.txt`: 100 bytes; SHA-256 `a6baba77cac1431d237727ff9cdbfd2ab3d0d98806012726f4cad09644fa61fb`.
- This row appended stdout bytes 686–784 and zero stderr bytes 100–100; existing earlier bytes were preserved.

## WSL helper lifecycle and setup provenance

The old helper was read-only verified before rotation as SHA-256 `6973df62818be76759f87e1231b6a5dfea4b64c08f16fb19f1b6c77975818e68`, owner/group/mode `0:988:4750`, version bound to old candidate `4fe150326a36faf401b045cfa1b9a2e64d89436b`. Under the previously authorized narrow helper lifecycle rotation, it was retained at `/usr/local/libexec/vst-s4-worker-exec.previous-4fe150326a36faf401b045cfa1b9a2e64d89436b` and its setuid bit disabled (`0:988:750`, unchanged bytes/hash). The candidate-bound installer was streamed from the immutable commit blob using the documented sanitized `git show <HEAD>:tools/qa/install_wsl_worker_helper.sh | env -i ... /bin/sh -s -- <HEAD> /tmp/vst-s4-candidate/repo` pipeline; installer output records the new binary SHA `a9d381acab8cbfd299be2e631caeca370f98193271df85fa8583172dbc0591dc`, owner/group/mode `0:988:4750`, and version `schema=1 head=621ddc01d1b5bbf701ccced7bb073c26e89c8c07 source_sha256=8c1a5986c8e081a05a3291b65f082fbd3a0dd0f93109a6395dd2bf57d43beb21`. Read-only post-run checks confirmed both installed and retained helper states.

Two directly relevant failed setup attempts before the successful WSL run are preserved in [`qa/s4-wsl-session-20261026-621ddc-r6/`](qa/s4-wsl-session-20261026-621ddc-r6/):

1. `setup-attempt-cwd-failure.*`: candidate staging and exact-head checks passed, and the authorized helper installation succeeded. Both dependency-preparation commands then exited 1 with `/usr/bin/python3.12: Error while finding module specification for 'tools.qa.prepare_dependencies' (ModuleNotFoundError: No module named 'tools')` because the shell was not in the candidate directory. No selector ran in that attempt; the candidate path was no longer present in the next WSL invocation. The subsequent r6 script explicitly `cd`'d into the staged repo before `python -m` commands.
2. `setup-attempt-shell-syntax.*`: the next command failed at shell line 33 with `/bin/bash: line 33: [: missing ']'` due to an incorrectly serialized shell line. No selector ran. This was corrected in the preserved `atomic-runner.sh` used for the successful run. An earlier preflight also stopped at `/usr/bin/id -g 988` (`id: 988: no such user`); `getent group 988` confirmed the existing `vst-runner` group, and the successful script uses that lookup. None of these pre-selector setup failures started a test selector.

The successful one-process WSL controller accepted a 5,366,579-byte payload with matching SHA-256 `6f6bd31687c75237c3def4fdb3acb011bb591534675ace5e98833a995b270d7f`. The committed bundle and trusted wheelhouse were streamed into the same WSL process; the candidate HEAD/status/registry preflight passed before helper verification, target preparation, and selectors. Session script/controller and complete WSL stdout/stderr are preserved in the same session directory. No Windows drive mount was present in the candidate boundary.

## Conclusion and next action

The three requested acceptance slices are runtime-proven PASS at the exact candidate and registry above, with exact target content verification before/after. No selector outside the three requested assignments ran. The 53 profile-less policy selectors remain `NOT_RUN`; AC-17 remains `NOT_VERIFIED`; neither is upgraded by these results. The WSL helper now matches the candidate; the previous helper is preserved with setuid disabled.

Next steps:

1. Codex records this evidence and its raw artifact files in the sprint review packet; do not alter the protected S2 file.
2. GPT-PM reviews the exact-head evidence and determines whether remaining acceptance, especially AC-17, is required for its gate.
3. Keep all 53 policy exclusions and AC-17 `NOT_VERIFIED` unless their policy/acceptance is explicitly changed and separately executed.


