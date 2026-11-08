REVIEW ITEM: U1-7 "[VST] Single entry command" (one task; the diff is limited to tools/uc/router.py, reviewed here only for its command-line entry (main and argument handling), and the end-to-end tests in tests/uc_e2e/test_u1_router_e2e.py).

Context: Unified Core sprint U1. The orchestrator (an LLM) calls ONE command with a role request JSON and gets a role result JSON, with no change to global Claude configuration.

Acceptance for U1-7: `python tools/uc/router.py review --request <json> --aeve-root <dir> --table <json> --state-dir <dir> --allowed-root <dir>` prints a validated uc.role-result.v1 (exit 0 all roles CLEAN, exit 3 open items) or a uc.blocked.v1 envelope (exit 2) for every failure (unreadable request or table, invalid request, AEVE problems, internal errors); usage errors exit 2 with an empty stdout; iteration_of links resubmissions of the same request_id.

Evidence already in hand (HEAD 946dacf): tests/uc 829 passed, 0 failed, 3 skipped; tests/uc_e2e 94 passed, 0 failed, 1 skipped with 5 real AEVE runs per run (mixed roles, hostile repository, request-id conflict, moved head, identical retry). The router internals (U1-6), the adapter (U1-5), the probe (U1-2), the contracts (U1-3) and the role table (U1-4) were approved by you earlier; do not re-review them.

Decisions already taken: the request-id record binds a request_id to its reviewed root permanently and iteration_of is the resubmission link (see your U1-6 round); the entry command never changes global configuration.

Please review ONLY the entry command behaviour (main, exit codes, envelopes) and the end-to-end tests for BLOCKER/MAJOR defects with a concrete failing input. Do not ask for full test runs, lint, typecheck or verification scripts (prohibited by the operator); documentation findings are out of scope.
