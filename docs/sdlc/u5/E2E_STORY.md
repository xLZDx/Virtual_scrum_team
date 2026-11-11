# U5-6: synthetic end-to-end story, model-forbidden

Files: `tests/vst/u5_e2e_support.py` (harness, not a test), `tests/vst/test_u5_e2e_story.py` (scenarios). Both are written and **NOT_RUN**: running tests is forbidden by the operator for this sprint; nothing was executed, only `ast.parse`.

Acceptance (PROJECT_PLAN U5-6): run with the model fallback disabled and every model invocation stubbed to raise; model-call count 0; a clean control story with only fully covered local roles returns CLEAN; a LOCAL_PLUS_MODEL role with the model part disabled is PARTIAL or another non-approving status, never CLEAN; each seeded defect names its stage, executor, rule and status (moved head, forged signature, skipped test, partial coverage, unsupported rule, role-table drift, secret in a finding); a negative control with the responsible check disabled by hand shows the defect is then not caught.

## What is real and what is simulated

| Stage (harness name) | Real code | Simulated |
|---|---|---|
| `role_table` | `tools/uc/role_table.validate_role_table`, `router.check_table` over three entries copied from `catalog/role_table.json` | the inventory, matrix and probe record (built from those entries; no AEVE checkout) |
| `worker_gate` | `tools/vst/worker_gate.gate_worker_change` and the real diff gate | the isolation context (fake `lstat`, as in `test_u5_worker_gate.py`) |
| `rule_coverage` | `tools/vst/rule_coverage.build_static_coverage` | the analyzer report and a hand-built `RuleCatalog` (two real required rule ids) |
| `aeve_adapter` / `router_normalize` | `adapter.build_aeve_request`, `adapter.check_response`, `router.normalize`, `contracts.validate_result` | the AEVE answer (`FakeAeve`: canned JSON in the AEVE shape, `llm_calls` = guard count) |
| `review_loop` | `tools/vst/review_loop.run_review_loop` on a real SQLite `PipelineState` | `submit` (fake AEVE + real router), `verify_report` (real HMAC from `tools/vst/signing.py` over the report, signature kept beside it) |
| `gate` | `tools/vst/gate.evaluate` with v1 receipts from `tests/vst/e1e4_helpers.py` (real HMAC signatures) | the receipts' content |
| `final_package` | `tools/vst/final_package.build_final_package` fed with `ReviewLoopResult.to_dict()` and the real isolation proof | the test evidence records and the diff bytes |

The story stops at the first stage that does not pass. A clean story has the trace `role_table, worker_gate, rule_coverage, router_normalize, review_loop, gate, final_package`.

## Model-forbidden run

The repository has no model-fallback switch (grep for "fallback" in `tools/uc` and `tools/vst` finds only unrelated process-kill and git-lookup comments). The harness therefore defines the flag itself: `StorySpec.model_fallback`, default `False`. Three harness seams read it and every one goes through one `ModelGuard.invoke`, which counts the call and raises `AssertionError('model invoked')`: the fake AEVE fallback, the model half of a LOCAL_PLUS_MODEL role (`resolve_model_residual`) and the model-writing fixer (`ModelGuard.fixer`, OD-8). `adapter.check_response` additionally rejects any AEVE answer whose `llm_calls` is not 0, and the fake reports the guard count there. Every scenario helper (`story`) asserts the flag is False and the count is 0; two tests wire a seam on purpose and assert the count is 1 and the loop is BLOCKED (`SUBMIT_FAILED`, `FIXER_FAILED`). What is NOT proven: that the real AEVE or the real Claude host never calls a model; only the seams of this harness are guarded.

## Scenarios (hand-written expectations)

| Scenario | Catching stage | Executor named | Rule named | Stops at, final status |
|---|---|---|---|---|
| Clean control (`repo-recon`, `git-worktree-ops`: class LOCAL, COVERED_PARTIAL) | none | declared set g1.repository-snapshot, g4.worktree-facts, g5.layering-shapes all COMPLETE | none | `final_package`, review CLEAN, gate APPROVE, package READY |
| LOCAL_PLUS_MODEL (`python-reviewer`), model part disabled | `review_loop` | g2.python-rules (COMPLETE locally) | MODEL_RESIDUAL_OPEN, COVERAGE_PARTIAL, EXIT_NOT_ZERO; iteration verdict PARTIAL | `review_loop`, loop BLOCKED; with the package forced: REFUSED REVIEW_NOT_CLEAN; never CLEAN, never READY |
| Moved head (test evidence at another head) | `final_package` | test id `tests/vst/test_story.py::test_beta` | STALE_EVIDENCE | `final_package`, REFUSED |
| Moved head (gate at another head) | `gate` | slot `tests` | "stale head" | `gate`, NO_GO |
| Forged signature (receipt signed with the wrong key) | `gate` | slot `tests` | "invalid signature" | `gate`, MODIFY |
| Forged signature (report signed with the wrong key) | `review_loop` | g5.layering-shapes (in the coverage list) | SIGNATURE_UNVERIFIED | `review_loop`, BLOCKED |
| Skipped test (required test NOT_RUN, no acknowledgement) | `final_package` | test id | NOT_RUN_UNACKNOWLEDGED | `final_package`, REFUSED |
| Partial coverage (g5.layering-shapes PARTIAL) | `review_loop` | g5.layering-shapes (`missing_coverage`) | DECLARED_EXECUTOR_MISSING (also COVERAGE_PARTIAL, EXIT_NOT_ZERO) | `review_loop`, BLOCKED (iteration PARTIAL, cap reached) |
| Unsupported rule (status for a rule outside the required catalog) | `rule_coverage` | analyzer profile g2.python-rules | STATUS_UNKNOWN_RULE, rule id PY-NOT-IN-CATALOG | `rule_coverage`, BLOCKED |
| Role-table drift: pin head | `role_table` | none (table-wide) | "pin: AEVE head differs from the probed checkout" | `role_table`, BLOCKED |
| Role-table drift: matrix digest | `role_table` | none (table-wide) | "pin: AEVE matrix digest differs from the probed matrix" | `role_table`, BLOCKED |
| Role-table drift: executor list | `role_table` | python-reviewer | "executors differ from the matrix" | `role_table`, BLOCKED |
| Secret in a finding (AEVE rule id shaped like a credential) | `router_normalize` | g5.layering-shapes | rule id replaced by `redacted` | `review_loop`, BLOCKED (iteration FINDINGS, cap reached) |
| Secret in evidence free text (test record reason) | `final_package` | section `test_evidence` | SECRET_IN_EVIDENCE | `final_package`, REFUSED |

"Status" words are the real vocabularies: `ReviewLoopResult` CLEAN/BLOCKED with iteration verdicts CLEAN/FINDINGS/PARTIAL/BLOCKED, gate APPROVE/MODIFY/NO_GO, package READY/REFUSED/BLOCKED, worker gate ACCEPTED/REFUSED/BLOCKED. The `role_table` and `rule_coverage` stages raise or return problem lists instead of a verdict; the harness maps both to BLOCKED. The secret literal is built at runtime (`"api" + "_key=" + ...`) so no credential-shaped text sits in the repository.

## Negative controls

Each control reruns the same scenario with exactly one check removed, inside the test's own `monkeypatch` scope (or one relaxed input), and asserts the defect is no longer caught. Production code is never edited. This is not a mutation run.

| Defect | What is disabled | Result asserted |
|---|---|---|
| moved head (package) | `final_package._stale` replaced by a no-op | READY, no STALE_EVIDENCE |
| forged signature (receipt) | `gate.verify` returns True | gate APPROVE, package READY |
| forged signature (report) | `verify_report=lambda doc: True` | review CLEAN, READY |
| skipped test | `allow_not_run` acknowledgement given (the documented escape hatch, a relaxed input) | READY, the test is still listed under `not_run` |
| partial coverage | `review_loop.judge_report` wrapped by `lenient_coverage_judge` (drops the coverage reasons) | review CLEAN, READY, while the report role is still PARTIAL |
| unsupported rule | the catalog admits the extra rule (relaxed input) | `coverage=FULL clean=True`, READY |
| role-table drift (3 rows) | `role_table.validate_role_table` returns `[]` | READY |
| secret in a finding | `router.has_secret` returns False | the credential-shaped text appears in the result as rule id `api_key-abcd1234wxyz` |
| secret in evidence text | `final_package._refuse_secrets` is a no-op | READY and the text is inside the package |

## Honest gaps

* **Moved head (gate) and forged signature (receipt)** are caught by inline code in `gate.evaluate` (no function seam), so these two rows have no negative control; the closest control is `gate.verify` for the forged receipt (done) and none for the stale-head test in the gate. Moved head has a control only at `final_package`.
* **Executor naming**: no real stage names an AEVE executor in every case. Where the stage output names none (pin drift, secret in evidence) the table says so; the evidence producer is named instead (slot, test id, section, role). The review loop names executors only through `coverage` and `missing_coverage`.
* **Skipped test and unsupported-rule controls are relaxed inputs**, not a disabled function, because the code has no separate function for those checks.
* **Pin check in the router**: `router.review()` checks the AEVE pin inline and needs a real AEVE checkout through `aeve_probe.probe`; the harness exercises `role_table.validate_role_table` instead, which compares the same pin fields. The router's inline check is not exercised here.
* **Receipts of the gate are v1 receipts** from `e1e4_helpers`; the v3 StaticAnalysis path (`receipt_builder.build_static_receipt`) needs a real git tree and an analyzer report and is not used. Report signatures are a harness convention (the `uc.role-result.v1` contract has no signature field).
* **Not proven**: nothing ran. Expected values were derived by reading the code; the first real run may expose wrong expectations, in particular the coverage control (`lenient_coverage_judge`) whose CLEAN result must also pass the store and `ReviewLoopResult.__post_init__`.
