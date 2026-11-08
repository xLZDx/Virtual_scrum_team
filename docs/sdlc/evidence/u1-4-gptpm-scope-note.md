REVIEW ITEM: U1-4 "[VST] Role table and validator" (one task; the diff is limited to tools/uc/role_table.py, catalog/role_table.json and tests/uc/test_role_table.py).

Context: Unified Core sprint U1. A table maps every agent and skill role of the virtual team to a class (LOCAL, LOCAL_PLUS_MODEL, MODEL_ONLY, OUT_OF_SCOPE), the AEVE profile and executors that can check it locally, and a coverage_state. The router uses it to decide which part of a review is done by deterministic local code and which part still needs a model.

Acceptance for U1-4: a table of all agent and skill definitions (93 entries) built from the inventory, the draft decisions and the LIVE AEVE matrix, pinned to the AEVE head and matrix digest; a validator that refuses a table that does not match the live matrix (executors must equal the matrix's, coverage_state must follow the matrix, a class not supported by evidence is refused, draft classes upgraded by evidence are flagged); the builder must not leave an invalid table at the output path.

Evidence already in hand (HEAD 69a121a): tests/uc 815 passed, 0 failed, 3 skipped (symlink creation not permitted on this host); one test validates the committed table against the real AEVE matrix. Three internal reviews done, findings fixed in 55578c0. U1-2, U1-3, U1-5 and U1-6 were approved by you earlier; do not re-review them.

Decisions already taken (do not reopen without new evidence): class describes the role and coverage_state what the matrix covers; the router answers NOT_COVERED whenever coverage_state is not COVERED_PARTIAL, whatever the class (19 entries are affected and that is intended); the draft classification is an unreviewed input, the evidence-based upgrade of 7 draft roles is deliberate; the router also checks the table shape on every request.

Please review ONLY role_table.py, the committed table and its tests for correctness and integrity defects: BLOCKER/MAJOR with a concrete failing input. Do not ask for full test runs, lint, typecheck or verification scripts (prohibited by the operator); documentation findings are out of scope.
