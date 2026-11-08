# S4-A GPT-PM code review scope

Task: S4-A QA category manifest, test-ID registry and denominator (one task). Base 83cfd64 (origin/main), head is the branch head at request time.
Code: tools/qa/registry.py, tools/qa/build_registry.py, docs/qa/categories.json (generated), tests/qa/test_s4a_registry.py.

Settled before this review (do not reopen):
- Sprint order set by the operator: S4 right after S3; U sprints wait. The code is ported from origin/s4-canonical-continuation and made self-contained on main; the runner, report artifacts, matrix and S4-B..F files are deferred to later S4 tasks.
- Evidence report files are produced by later tasks: the artifact stage is optional and reports SKIPPED (explicitly not a success) when they are absent; PRESENT is existence-only.
- Operator rules: no mutation runs, no full npm test; tests were written and run by the functional-test agent only.
- A python-reviewer pass found 5 MAJOR and a pytest oracle test found 4 more collector gaps; all were fixed before this request: collector follows pytest default collection and fails closed on unresolved constructs, validation requires a clean tree for tests/, docs/qa/ and tools/qa/ and hashes HEAD blobs, count_passed is per runtime profile, empty or NOT_RUN categories report complete=False, category status is bound to content.
- Known and accepted: the category assignment of main test modules (MAIN_TEST_FILE_CATEGORIES) is by file name; the manifest category map is not independently pinned by a digest; WSL-only profile behavior is not exercised on this host.

Evidence: functional agent run on the exact head, 274 passed, 0 failed (tests/qa/test_s4a_registry.py, includes the real-manifest test, 4 pytest-oracle edge tests and a real-corpus assertion). Real corpus: 1939 selectors over 54 test modules. NOT_RUN: mutation runs, WSL execution, full npm test (prohibited).

Ask: find the complete BLOCKER/MAJOR set for this task only.
