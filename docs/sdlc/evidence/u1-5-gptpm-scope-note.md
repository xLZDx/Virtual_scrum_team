REVIEW ITEM: U1-5 "[VST] AEVE CLI adapter" (one task; the diff is limited to tools/uc/adapter.py and tests/uc/test_adapter.py).

Context: Unified Core sprint U1. A deterministic local analyzer (AEVE, separate repository, zero model calls) is called through its CLI by an isolated child process; the output goes to an LLM orchestrator, so the reviewed repository and everything it controls is untrusted.

Acceptance for U1-5: builds an AEVE review request (v2) and calls the CLI with a neutral working directory, -P -s -B interpreter flags, an explicit minimal environment, a pinned application-data location, shell=False, a stdout cap, and a timeout that kills the whole process tree. Every failure row must end BLOCKED, never a clean-looking result: missing or mismatched AEVE, timeout, invalid / oversized / control-byte output, dirty tree for a receipt request, moved head, AEVE ERROR status or ledger not persisted, duplicate or malformed executor results, findings from executors that were not requested. A reviewed repository containing json.py and an aeve/ package, or git.exe in the working directory, must not change the analyzer.

Evidence already in hand (HEAD 98696f5): tests/uc 805 passed, 0 failed, 3 skipped (symlink creation not permitted on this host); tests/uc_e2e 94 passed, 0 failed, 1 skipped (5 real AEVE runs). Three independent internal reviews (security, silent failures, reliability) were done and their BLOCKER/MAJOR findings fixed in commit 55578c0. The router (U1-6) was already approved by you in an earlier round; do not re-review it.

Decisions already taken (do not reopen without new evidence): the adapter sends request v2 because v1 makes AEVE refuse 15+ executors; there is no per-executor retry loop (measured 15-30 s per AEVE call); the per-request lock and request records live in the router, not here.

Please review ONLY adapter.py and its tests for correctness and security defects: BLOCKER/MAJOR with a concrete failing input. Do not ask for full test runs, lint, typecheck or verification scripts (prohibited by the operator); documentation findings are out of scope.
