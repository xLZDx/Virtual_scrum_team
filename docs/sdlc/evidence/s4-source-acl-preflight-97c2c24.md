# INTERIM — S4 QA source ACL preflight focused evidence

> This is interim, non-accepting Windows unit evidence only. It does **not** validate the committed category mapping: the tested parametrized node IDs were not source-resolvable under the category registry contract. The mapping was corrected in commit `180e330`; those corrected selectors later passed in the exact-head Ubuntu-24.04 WSL run at `bc32f6f`. See change 0261 and `docs/sdlc/evidence/s4-source-acl-preflight-runtime-bc32f6f.md` for the superseding WSL/runtime proof and artifact hashes.

## Exact source and test state

- Branch: `s4-native-qa-runner`.
- Repository HEAD at execution: `97c2c24538a5e1e3c9aee549b1766b26a283d7ac`.
- Worktree: clean before execution (`git status --short --branch` returned only branch header).
- Product source commit: `c51105abfef72aceb295633bbdf637666ad843a2`.
- Test code still used a parameterized named-user/named-group test; the registry mapping then included bracketed node IDs and was not statically resolvable.

## Environment and command

- Interpreter: CPython 3.14.3, 64-bit Windows 11.
- Command: `C:\Python314\python.exe -m pytest -q tests\qa\test_s4_worker_boundary_contracts.py -k qa_preflight`.
- Interim result: **5 passed, 7 deselected**, exit code 0, one unrelated pytest-asyncio deprecation warning, 5.03 seconds.

## Limits and current status

- Tests injected synthetic access/default ACL xattr values, inspection failure, and ACL absence while isolating the mode-bit fallback.
- This run does not prove Linux ACL kernel semantics or the WSL sandbox boundary.
- It also does not prove the mapped category because registry resolver rejects parameterized node IDs.
- Corrected static selector functions/mapping are in `180e330`; their exact-head WSL evidence is recorded in change 0261: 15 focused selectors passed and synthetic outer functional CLI passed all 33 mapped IDs with report, receipt, and diff gate PASS.
- This historical record does not represent aggregate, trusted deployed signer, authoritative task gate, or current E2E category execution. The registry now defines E2E/report-bound acceptance at the outer `tools.qa.run --category e2e` boundary; exact-head category results are recorded separately from denominator completeness.
