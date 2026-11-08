# S4-B GPT-PM code review scope

Task: S4-B pinned test environment and bounded native test runner (one task). Base 0b1be7d (S4-A approved and pushed), head is the branch head at request time.
Code: tools/qa/run.py, pytest_plugin.py, dependencies.py, prepare_dependencies.py, report.py, requirements.lock, the registry.py changes (worktree binding, check_artifacts flag), tests/qa/test_s4b_runner.py, docs/qa/categories.json (generated).

Settled before this review (do not reopen):
- Windows only (CPython 3.14.3 profile). WSL execution is out of scope by the operator decision and is recorded NOT_RUN in every report. Seeded-failure pieces, matrix, root harness belong to later S4 tasks.
- Trust model (operator decision, recorded in the code and in a trust_model report field): the pytest child runs as the operator with no identity separation; reporting from inside the pytest process is candidate-attested evidence, not tamper-proof against hostile code in that process.
- Two independent reviews (python-reviewer and security-reviewer) ran before this request; their MAJOR findings were fixed in one batch: isolated interpreter (-P -s, pinned empty pytest.ini, rootdir/confcutdir, target-first sys.path, no cacheprovider), hook allowlist (tests/ conftest with guarded hooks refused; a root conftest.py is never loaded because of --confcutdir), ignored-file and non-H index-flag rejection, .git config/info hash and HEAD re-read, append-only evidence snapshot with a per-repo lock, caps and BLOCKED record on any exception, Job Object limits, token redaction, extra-wheel rejection. Known and accepted: wheel verifier heuristics beyond the extra-wheel rule (second line, after a hash-pinned wheel), --expected-head optional, no ACL hardening of the interpreter directory, no run from a git-archive export.
- Operator rules: no mutation runs, no full npm test; tests were written and run by the functional-test agent only.

Evidence (all by the functional-test agent): tests/qa/test_s4b_runner.py on d69c824: full file 223 passed and 5 failed (all five were test mistakes), then the five fixed tests plus four conftest tests rerun: 15 passed; the full file was NOT rerun after the test-only fixes (about 48 minutes). Network lane: the real lock downloaded and verified once with no TLS workaround. S4-A regression on the S4-B head: tests/qa/test_s4a_registry.py full run 272 passed and 2 failed (the two were rewritten because the new binding refuses skip-worktree on purpose), then the changed and real-manifest tests: 9 passed at 9046df7. NOT_RUN: mutation runs, WSL, a live end-to-end category run on the real repo (it appends evidence files; the test agent ran the runner only in throw-away repos).

Ask: find the complete BLOCKER/MAJOR set for this task only.
