# U5-6 GPT-PM code review scope

Task: U5-6, synthetic end-to-end story, model-forbidden. Base: U5-5 approved head (dd8dc0b), head = current HEAD. Review the delta only: tests/vst/u5_e2e_support.py (harness, not a test), tests/vst/test_u5_e2e_story.py, docs/sdlc/u5/E2E_STORY.md, tools/qa/build_registry.py (two map lines), core/DECISION_LOG.md and core/LESSONS_LOG.md entries. No production module was edited.

Delivers: an in-process story harness that chains the real `role_table` validation, `worker_gate`, `rule_coverage`, `adapter.check_response` + `router.normalize`, `review_loop` (real SQLite `PipelineState`), `gate.evaluate` and `final_package`, with a fake AEVE answer, a fake isolation `lstat` and real HMAC signatures. A single `ModelGuard` counts and rejects every model-capable seam of the harness (fake AEVE fallback, model-residual resolver, model-writing fixer); every scenario asserts the flag is off and the count is 0. Scenarios: clean control (CLEAN end to end, READY), LOCAL_PLUS_MODEL with the model part disabled (iteration PARTIAL, loop BLOCKED, never CLEAN or READY), and the seeded defects moved head, forged signature, skipped test, partial coverage, unsupported rule, role-table drift (3 variants), secret in a finding, each with hand-written stage, executor, rule and status. Negative controls disable the one responsible check inside the test's `monkeypatch` scope (or pass one relaxed input) and assert the defect is not caught.

Interpretation decisions:
- The repository has no model-fallback switch; the flag is defined by the harness (`StorySpec.model_fallback`) and only harness seams read it. Nothing is claimed about the real AEVE or Claude host.
- "Executor" is the AEVE executor id where a stage names one (review loop coverage, role-table executors) and otherwise the evidence producer the stage names (slot, test id, section); pin drift names none. Listed as a gap in E2E_STORY.md.
- `role_table` and `rule_coverage` signal by problem list or exception; the harness maps both to BLOCKED.
- The router's inline pin check needs a real AEVE checkout; `role_table.validate_role_table` (same pin fields) is exercised instead.
- Moved head and forged receipt are also caught inline in `gate.evaluate`; those two rows have no function-level control (gap).
- A credential-shaped literal is built at runtime so the public repository holds none.

Limits: nothing was run; every expected value comes from reading the code; the `lenient_coverage_judge` control is the riskiest expectation; the harness is not a test file and is not registered; `docs/qa/categories.json` was not regenerated (the registry builder is a prohibited run) and is left to the coordinator.

Tests: written, NOT_RUN (running tests is forbidden by the operator). Evidence is static reading and `ast.parse` only.
