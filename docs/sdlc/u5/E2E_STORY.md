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

What the repository has (files opened and grepped, `tools/`): `llm_calls` appears in `tools/uc/adapter.py` (`check_response` rejects any AEVE answer whose `llm_calls` is not 0, line 233), `tools/uc/aeve_probe.py` (doctor and matrix must report 0), `tools/vst/analyzer_adapter.py` (report `llm_calls` must be 0) plus `tools/vst/patch_proposals.py` and `tools/qa/executor_aeve.py`. No file under `tools/` mentions `anthropic` or `openai`. The word "fallback" matches `tools/uc/router.py` (a parameter name of `to_token`), `tools/uc/aeve_probe.py` ("no bare git fallback"), `tools/vst/runner.py`, `supervisor.py`, `patch_proposals.py`, `analyzer_adapter.py` (a rule name) and some `tools/qa` files, all unrelated to a model. So there is a contract that AEVE reports zero model calls, but no model-fallback switch.

The harness therefore defines two flags itself, both default `False` and independent: `StorySpec.model_fallback` (the model half of a LOCAL_PLUS_MODEL role, read by `resolve_model_residual`) and `StorySpec.aeve_model_fallback` (the fake AEVE falls back to a model). The model-writing fixer (`ModelGuard.fixer`, OD-8) is the third seam. All three call `ModelGuard.invoke`, which counts and raises `AssertionError('model invoked')`.

What the guard covers: `story()` installs `install_escape_guards` inside `monkeypatch`, so the REAL escape points raise and count too: `subprocess.Popen`, `subprocess.run`, `socket.socket.connect`, `adapter.run_review` (the real AEVE CLI entry), `router._call` (the router's AEVE execution seam), `aeve_probe.probe`, and the `anthropic`/`openai` client constructors when those modules are importable (they are not installed here, so none are patched). The stories do not need any of them (`FakeAeve` replaces the AEVE call at the injected seam), so a count above 0 means real code escaped. `test_escape_seams_raise_and_count` calls every patched seam directly and asserts it raises and counts, which proves the assertion is not vacuous. The expected count and the expected `model_fallback` flag are literals in each test; `FakeAeve` reports `llm_calls: 0` as a literal, not the guard count. Three tests wire a harness seam on purpose (AEVE fallback, model residual with `MODEL_ROLE`, model fixer) and assert count 1, loop BLOCKED and the exact `guard.calls`.

What it cannot cover: the real AEVE process and the real Claude host (nothing here starts them), an HTTP client other than the two named, in-process code that calls a model without any of the patched names, and any model use that a future module adds. A count of 0 therefore proves "the harness and the patched escape points did not reach a model", not "the real pipeline never calls one".

## Scenarios (hand-written expectations)

Harness constants (hard-coded in the fake, not produced by the code under test): the analyzer profile id `g2.python-rules` in the fake static report, the test ids, the diff, the receipts' content and the AEVE answers. "Executor" in the table below is the evidence producer for the gate and package rows (slot, test id, section). An AEVE executor id is named only where the code under test produced it (the router result `executors` and the review loop `coverage` / `missing_coverage`).

| Scenario | Catching stage | Executor named | Rule named | Stops at, final status |
|---|---|---|---|---|
| Clean control (`repo-recon`, `git-worktree-ops`: class LOCAL, COVERED_PARTIAL) | none | declared set g1.repository-snapshot, g4.worktree-facts, g5.layering-shapes all COMPLETE | none | `final_package`, review CLEAN, gate APPROVE, package READY |
| LOCAL_PLUS_MODEL (`python-reviewer`), model part disabled | `review_loop` | g2.python-rules (COMPLETE locally) | MODEL_RESIDUAL_OPEN, COVERAGE_PARTIAL, EXIT_NOT_ZERO; iteration verdict PARTIAL | `review_loop`, loop BLOCKED; with the package forced: REFUSED REVIEW_NOT_CLEAN; never CLEAN, never READY |
| Moved head (test evidence at another head) | `final_package` | test id `tests/vst/test_story.py::test_beta` | `("STALE_EVIDENCE", "test:<T2>: evidence names head <HEAD2>, the package head is <HEAD>")` | `final_package`, REFUSED |
| Moved head (gate at another head) | `gate` | slot `tests` (receipt r-tests-1) | reason `receipt r-tests-1 stale head: candidate_head != current head (slot 'tests' attempt 1)` | `gate`, NO_GO |
| Forged signature (receipt signed with the wrong key) | `gate` | slot `tests` | reasons `receipt[0] (r-tests-1) invalid signature` and `missing receipt for slot 'tests'`; `acceptance_unmet == [AC-1]` | `gate`, MODIFY |
| Forged signature (report signed with the wrong key) | `review_loop` | none named by the stage (iteration `coverage` lists the COMPLETE executors) | iteration reasons `("SIGNATURE_UNVERIFIED",)`, loop reason ITERATION_CAP | `review_loop`, BLOCKED |
| Skipped test (required test NOT_RUN, no acknowledgement) | `final_package` | test id | `("NOT_RUN_UNACKNOWLEDGED", "required tests not run and not acknowledged: <T2>")` | `final_package`, REFUSED |
| Partial coverage (g5.layering-shapes PARTIAL) | `review_loop` | g5.layering-shapes (`missing_coverage`) | DECLARED_EXECUTOR_MISSING (also COVERAGE_PARTIAL, EXIT_NOT_ZERO) | `review_loop`, BLOCKED (iteration PARTIAL, cap reached) |
| Unknown rule (status for a rule outside the required catalog) | `rule_coverage` | none (harness profile id only) | `CoverageError.code` STATUS_UNKNOWN_RULE, rule id PY-NOT-IN-CATALOG | `rule_coverage`, BLOCKED |
| Unsupported rule (required rule PY-IDENTITY-LITERAL-COMPARISON marked UNSUPPORTED) | `rule_coverage` | none (harness profile id only) | `unsupported_rules == [PY-IDENTITY-LITERAL-COMPARISON]`, `coverage` PARTIAL, `clean` False (harness stops when not clean) | `rule_coverage`, BLOCKED |
| Role-table drift: pin head | `role_table` | none (table-wide) | "pin: AEVE head differs from the probed checkout" | `role_table`, BLOCKED |
| Role-table drift: matrix digest | `role_table` | none (table-wide) | "pin: AEVE matrix digest differs from the probed matrix" | `role_table`, BLOCKED |
| Role-table drift: executor list | `role_table` | python-reviewer | "executors differ from the matrix" | `role_table`, BLOCKED |
| Secret in a finding (AEVE rule id shaped like a credential) | `router_normalize` | g5.layering-shapes | rule id replaced by `redacted` | `review_loop`, BLOCKED (iteration FINDINGS, cap reached) |
| Secret in evidence free text (test record reason) | `final_package` | section `test_evidence` | `("SECRET_IN_EVIDENCE", "test_evidence contains a value that looks like a secret")` | `final_package`, REFUSED |

"Status" words are the real vocabularies: `ReviewLoopResult` CLEAN/BLOCKED with iteration verdicts CLEAN/FINDINGS/PARTIAL/BLOCKED, gate APPROVE/MODIFY/NO_GO, package READY/REFUSED/BLOCKED, worker gate ACCEPTED/REFUSED/BLOCKED. The `role_table` and `rule_coverage` stages raise or return problem lists instead of a verdict; the harness maps both to BLOCKED. The secret literal is built at runtime (`"api" + "_key=" + ...`) so no credential-shaped text sits in the repository.

## Negative controls

Each control reruns the same scenario with exactly one check removed, inside the test's own `monkeypatch` scope (or one relaxed input), and asserts the defect is no longer caught. Production code is never edited. This is not a mutation run.

| Defect | What is disabled | Result asserted |
|---|---|---|
| moved head (package) | `final_package._stale` replaced by a no-op | READY, no STALE_EVIDENCE |
| forged signature (receipt) | `gate.verify` returns True | gate APPROVE, package READY |
| forged signature (report) | `verify_report=lambda doc: True` | review CLEAN, READY |
| skipped test | `allow_not_run` acknowledgement given (the documented escape hatch, a relaxed input) | READY, the test is still listed under `not_run` |
| partial coverage | `review_loop.judge_report` wrapped by `lenient_coverage_judge` (drops the coverage reasons) | review CLEAN with empty `loop_result.reasons` (so it is not a BLOCKED-by-exception), READY, while the report role is still PARTIAL |
| unknown rule | the catalog admits the extra rule (relaxed input) | `clean` True, READY |
| unsupported rule | the harness "stop when coverage is not clean" check relaxed by hand (`require_clean_coverage=False`) | READY while `clean` is still False |
| role-table drift (3 rows) | `role_table.validate_role_table` returns `[]` | READY |
| secret in a finding | `router.has_secret` returns False | the credential-shaped text appears in the result as rule id `api_key-abcd1234wxyz` |
| secret in evidence text | `final_package._refuse_secrets` is a no-op | READY and the text is inside the package |

## Honest gaps

* **Moved head (gate) and forged signature (receipt)** are caught by inline code in `gate.evaluate` (no function seam), so these two rows have no negative control; the closest control is `gate.verify` for the forged receipt (done) and none for the stale-head test in the gate. Moved head has a control only at `final_package`.
* **Executor naming**: no real stage names an AEVE executor in every case. Where the stage output names none (pin drift, secret in evidence) the table says so; the evidence producer is named instead (slot, test id, section, role). The review loop names executors only through `coverage` and `missing_coverage`.
* **Skipped test, unknown-rule and unsupported-rule controls are relaxed inputs or harness checks**, not a disabled function, because the code has no separate function for those checks.
* **Pin check in the router**: `router.review()` checks the AEVE pin inline and needs a real AEVE checkout through `aeve_probe.probe`; the harness exercises `role_table.validate_role_table` instead, which compares the same pin fields. The router's inline check is not exercised here.
* **Receipts of the gate are v1 receipts** from `e1e4_helpers`; the v3 StaticAnalysis path (`receipt_builder.build_static_receipt`) needs a real git tree and an analyzer report and is not used. Report signatures are a harness convention (the `uc.role-result.v1` contract has no signature field).
* **Not proven**: nothing ran. Expected values were derived by reading the code; the first real run may expose wrong expectations, in particular the coverage control (`lenient_coverage_judge`) whose CLEAN result must also pass the store and `ReviewLoopResult.__post_init__`.
