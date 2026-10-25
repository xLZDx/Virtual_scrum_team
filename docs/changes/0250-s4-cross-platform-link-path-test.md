# 0250 S4 cross-platform linked-path contract test

**Date:** 2026-10-25  
**Executor:** Codex  
**Test author:** `functional-test-reviewer`, GPT-6 Luna, medium effort  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `8eb8dbd38d196b1434b3fcb8d3f1a27eb7c54944`

## What changed

- Replaced the Windows privilege-dependent file-symlink setup with a directory junction (`mklink /J`) and retained a directory symlink on POSIX.
- Renamed the test selector to `test_s4_registry_rejects_linked_source_path_escape`, matching both platform mechanisms.
- Included the exact return code/stdout/stderr or exception type/message in any future `NOT_RUN` reason if link creation is genuinely unavailable.
- Preserved the failed functional report from the exact-head run in `docs/sdlc/evidence/qa/functional.report.jsonl`.

## Why

The functional category at exact HEAD `8eb8dbd` ran 109 concrete cases: 108 passed and one required link-escape selector was skipped because Windows file-symlink creation was unavailable. Since skipped required tests do not satisfy the gate, the lane correctly reported `FAIL`. The product assertion itself is valid: `registry.validate_registry()` must reject a source path whose resolved target escapes the candidate root. A Windows directory junction exercises that path containment invariant without requiring a privileged file symlink.

## Evidence and verification

- The exact-head report is in `docs/sdlc/evidence/qa/functional.report.jsonl`; it contains three append-only records: the d99 registry preflight block, the 0122 line-ending preflight block, and the 8eb functional `FAIL`.
- The 8eb functional run used Python 3.14.3 and pytest 9.0.3; it reported 108 passed, 1 skipped, 0 failed concrete tests. The required skipped selector was `tests/qa/test_s4_functional_runner_contracts.py::test_s4_registry_rejects_symlinked_source_path`; its test output only retained the general reason `symlink creation unavailable`, not the underlying exception detail.
- Test source was corrected after this run. **No tests were run after the correction**, so runtime acceptance remains pending.
- No process-kill, external call, CI/build, worktree, or product-code change occurred. The pre-existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-034: functional test logic now covers the link-escape invariant with Windows junction/POSIX symlink setup; rerun is pending.
- VST-032: regenerate the category registry after this test selector rename.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test author/executor: `functional-test-reviewer`/`e2e-runner`.
- Next: commit this test correction, regenerate the registry, then rerun all six QA categories at the new exact HEAD. Keep any genuinely unsupported link creation as `NOT_RUN` with its precise system error.
