# U3-2 GPT-PM code review scope

Task: U3-2, one test-executor interface with two executors (operator decision OD-2: build both and compare). Base 58ed30c (U3-1 accepted), head = current HEAD (two commits). Review the delta only: tools/qa/executor.py, tools/qa/executor_native.py, tools/qa/executor_aeve.py, docs/sdlc/u3/EXECUTORS.md.

Delivers: ExecutorReport and TestExecutor with a closed registry {vst-native, aeve-sandbox}; judge() returns APPROVABLE, COARSE_ONLY or NON_APPROVING. Executor A runs the native runner (tools.qa.run) as a bounded child and maps its schema-3 record; because the candidate runs its own runner and registry, its verdict is capped at COARSE_ONLY unless two caller pins (registry sha256, tools/qa tree sha256) are supplied and match; the executor re-reads HEAD and the worktree status itself. Executor B runs `aeve sandbox project-test` as a bounded child, refuses any profile with mutants (max_mutants 0, mutation_paths empty), applies the same AEVE pin and clean-checkout rules as the U1 router before and after the run, compares source_head itself, and can never exceed COARSE_ONLY (no per-test ids are available from AEVE). Anything not run is NOT_RUN.

Already fixed after two read-only reviews (python 2 MAJOR, security 2 MAJOR): candidate-attested approval, record selection by run id, clean-tree precondition, AEVE pin parity with the router.

Settled, do not reopen: AEVE is not modified; no mutation run is ever performed; the comparison of the two executors (U3-7) and the gate wiring (U3-5) are separate tasks; recorded limits: git resolution is checked not replaced, the VST process must run with -P and not with cwd on the candidate. Tests NOT_RUN (operator forbids pytest); neither executor, Docker nor AEVE was executed; evidence is static review only.

Ask: the complete BLOCKER/MAJOR set for this delta only.

## Verification round (after GPT-PM round 1, reply a6c11da7, MAJOR x1)
Base: 460a3a2. Fixed: tools/qa/executor.py worktree_dirty_paths (git status porcelain v1 -z with untracked files, trusted git, renames and copies both paths); tools/qa/executor_aeve.py refuses CANDIDATE_DIRTY_BEFORE_RUN before launch (after the pin check and the pre-launch HEAD re-read) and CANDIDATE_DIRTY_AFTER_RUN after the run (after the post-run pin and HEAD re-check), no exceptions; EXECUTORS.md updated. Ask: verify this one correction and direct regressions only.
