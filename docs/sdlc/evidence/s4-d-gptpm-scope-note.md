# S4-D GPT-PM code review scope

Task: S4-D e2e and regression selectors through the S4-B runner (one task). Base cd5a8d0 (S4-C approved and pushed), head is the branch head at request time.
Code in this delta: tests/qa/test_s4d_lanes.py (new), tools/qa/build_registry.py (one mapping line that assigns the new test file to the qa-tooling category), docs/qa/categories.json (generated). No change to the runner or registry logic: the runner is category-generic and the tests prove it for the e2e and regression lanes.

Operator decision for this task (2026-11-09): "mechanism and a small slice, no big runs". Therefore the real e2e lane (168 selectors) and the real regression aggregate (about 1830 selectors) were NOT run; they are NOT_RUN by that decision, and S4-F is where a no-skip gate consumes such results.

What the tests pin (14 tests, test agent, 407.6 s):
- AC-11 on the regression lane: all members passing is a typed PASS over the exact union of functional, integration, api and e2e; one skipped, one xfail, one failing, one uncollected and one unexpected extra case each make the run non-approving, each in its own result list with its own reason.
- AC-10 on the e2e lane: a selector declared NOT_RUN with a reason stays in the denominator and the inventory, is never passed or executed, and the run is INCONCLUSIVE, never PASS; the regression run goes INCONCLUSIVE too.
- Unit level: the regression denominator is the exact union and complete only when all members are runnable; count_passed never counts a NOT_RUN selector even if an outcome claims passed; _resolve_cases puts every outcome in exactly one list, rejects malformed event files and digests unsafe node IDs.

Settled, do not reopen: Windows-only, WSL NOT_RUN, trust model of S4-B, accepted S4-C results (the three lanes are red because of pre-existing S2 tests), no mutation runs, no big suites.

Evidence limits: the first run of the new file had 4 failures caused by a test-authoring mistake (the NOT_RUN policy line was appended after the __main__ guard of the throwaway builder), fixed by the test agent and the file was run a second time: 14 passed. The NOT_RUN selector is declared in a throwaway registry copy, not in the real registry. Real-repo evidence for e2e is a smoke by the e2e-runner agent on an earlier head: the first 5 of 37 tests of tests/vst/test_e5_slice.py passed (32 NOT_RUN). real_manifest passing on the final head is confirmed separately by a test agent run.

Ask: find the complete BLOCKER/MAJOR set for this delta only.
