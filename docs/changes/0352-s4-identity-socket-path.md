# Change 0352 — Bound the S4 identity fixture's AF_UNIX path

## What changed

The WSL-only S4 identity test now creates its protected Unix-domain socket in a unique short directory under `/tmp` rather than below pytest's nested `tmp_path`. It still uses `tmp_path` for the runner-only sentinel file. The socket directory is removed in a `finally` path, including setup and execution failures.

## Why

At report-bound candidate `52c3a7d740529cee6ea42958cef6918be452c830`, the identity selector failed before reaching the worker helper: `listener.bind()` raised `OSError: AF_UNIX path too long`. The pytest scratch path was nested under `/tmp/vst-s4-candidate/.../pytest-of-vst-runner/...`, exceeding the Unix-domain socket path limit. A verbose diagnostic using the same selector and boundary passed with a short `/tmp` path; a runner-context diagnostic reproduced the path failure. Both diagnostics are non-acceptance evidence.

## Affected contract and paths

- AC-16 identity test setup: `tests/qa/test_s4_functional_worker_identity.py`.
- Product helper source and assertions are unchanged. Expected runner/worker identities, file/socket denial, `no_new_privs`, and inherited-FD assertions remain intact.

## Verification state

- Focused tests: `NOT_RUN` for this change; the designated test author made no test execution.
- Report-bound WSL identity: prior result remains `FAIL` at the preceding test-source head. A fresh exact-head report-bound identity run is required after this change is committed.
- Seeded-failure: previous exact-head run passed 3/3, but it does not verify this fixture change.

## Provenance

- Baseline candidate: `52c3a7d740529cee6ea42958cef6918be452c830`.
- Baseline source/test head: `4d4341e4812ba726c0b35e83ee2fad0a3fb5a7f1`.
- Test-author role: `functional-test-reviewer` (`gpt-6-luna`); this record attributes the edit to the current coordinated task. No test was run by that role for this change.
