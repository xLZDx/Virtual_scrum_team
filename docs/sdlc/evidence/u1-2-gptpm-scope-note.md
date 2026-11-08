REVIEW ITEM: U1-2 "[VST] AEVE environment probe" (one task; the diff is limited to tools/uc/aeve_probe.py and tests/uc/test_aeve_probe.py).

Context: Unified Core sprint U1. A deterministic local analyzer (AEVE, separate repository, zero model calls) is run from its checkout by an isolated child process. The probe establishes whether the checkout is usable and records its identity; the router then compares that identity with a pinned role table.

Acceptance for U1-2: AEVE runs from its checkout with a neutral working directory, a minimal explicit environment, no bytecode written and no user site, on an interpreter of at least 3.12; the probe records AEVE head, dirty state, matrix digest and executor count and returns BLOCKED for a wrong path, an old interpreter, a failing doctor or matrix, a malformed output, or a report of model calls or project-code execution. The AEVE repository must be unchanged by the probe. No executable may be resolved from the current directory (the previously noted bare "git" fallback is removed in commit b028eb1: no absolute PATH entry with git means GIT_NOT_FOUND).

Evidence already in hand (HEAD b028eb1): tests/uc 806 passed, 0 failed, 3 skipped (symlink creation not permitted on this host), including one test against the real AEVE checkout (before/after tree state identical). Three internal reviews (security, silent failures, reliability) were done and their BLOCKER/MAJOR findings fixed in 55578c0. U1-5 (adapter) and U1-6 (router) were approved by you earlier; do not re-review them.

Decisions already taken (do not reopen without new evidence): the AEVE-dirty rule is enforced by the router (tracked changes or new files under src/), the probe only reports the counts; probe subprocesses are bounded by a per-call timeout, not by a request-wide budget.

Please review ONLY aeve_probe.py and its tests for correctness and security defects: BLOCKER/MAJOR with a concrete failing input. Do not ask for full test runs, lint, typecheck or verification scripts (prohibited by the operator); documentation findings are out of scope.
