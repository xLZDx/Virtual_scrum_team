# S2-M01 untracked DiffGate inventory fix and tests

Date: 2026-10-26  
Repository: `D:\Repo\Virtual_scrum_team`  
Source HEAD during runs: `7d801671125435da3fc5152813ecd52d4e481dd7` (working tree dirty)  
Test owner: designated `e2e-runner`, GPT-6 Luna

## Finding and source correction

Correlated GPT-PM exact-diff review (request `172f1abb-0023-48b8-ab8b-57b6b5b1f528`, reply `da8c2bb2-56f9-5c3b-923a-a0674163ba9c`) found that `_diff_paths()` used `git ls-files --others --ignored --exclude-standard -z`, which enumerated ignored files but omitted ordinary non-ignored untracked files. That allowed an ordinary untracked out-of-scope file to be absent from `changed_paths` and the supplemental digest.

The working-tree correction runs separate Git enumerations for ordinary untracked and ignored files, takes the sorted deduplicated union, and passes all paths through the existing scope, file-type, symlink and content-digest handling. The explicit policy is that ignored files remain in candidate-change inventory and are judged by the same manifest scope.

## New signed temp-Git integration tests

All new tests call the real `_diff_paths()` collector in a temporary Git repository, pass its output to `git_diff_evidence()`, and sign/verify the resulting evidence.

| Scenario | Oracle |
|---|---|
| Ordinary untracked out-of-scope file | Signed `FAIL / OUT_OF_SCOPE_PATH`; file is in `changed_paths` |
| Ordinary untracked blocked installer path | Signed `FAIL / BLOCKED_PATH_CLASS`; file is in `changed_paths` |
| Allowed ordinary untracked file | `PASS`; candidate bytes are in the digest input; changing bytes changes `diff_sha256` |
| Allowed ignored file plus ordinary untracked file | Both paths are sorted/included, both contents are bound, and result is `PASS` under explicit allowlist |
| Ignored untracked out-of-scope file | Signed `FAIL / OUT_OF_SCOPE_PATH`; ignored file remains included |

## Runs

Python 3.14.3; every run emitted one `pytest-asyncio` deprecation warning.

| Command | Result | Duration |
|---|---|---:|
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_diffgate.py -k "runner_"` | Exit 0; 5 passed, 17 deselected | 20.24 s |
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_diffgate.py` | Exit 0; 22 passed | 14.51 s |
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_contract_gate.py -k diff_gate` | Exit 0; 5 passed, 38 deselected | 0.65 s |
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands` | Exit 0; 7 passed | 3.61 s |

An earlier too-narrow focused selector selected four of the five new tests and passed; the test owner then ran the correct five-case selection and the full module. No failures were reported. HEAD was unchanged; final dirty paths are the implementer's source edit, the test author's test edit, and the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`. The implementer also ran `git diff --check` inadvertently; it emitted no output and is not verification evidence.

## Remaining acceptance

These results are working-tree evidence, not exact committed-head evidence. Exact committed-head rerun and independent review are pending. Real Windows/POSIX platform behavior, sandbox/resource enforcement and policy-restricted runtime scenarios remain separate open S2 criteria.
