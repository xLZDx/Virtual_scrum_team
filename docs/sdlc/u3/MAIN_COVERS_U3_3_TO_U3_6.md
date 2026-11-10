# What main already provides for U3-3 .. U3-6

Source: read-only mapping of origin/main (fa26e3c) against the acceptance text of the four "land" tasks of sprint U3. The branch inventory (BRANCH_INVENTORY.md) found no file on the five old branches that should land, because main already carries the S4 testing core. Facts are file-level and were read, not executed. Every re-earned count is NOT_RUN (pytest is forbidden by the operator).

| Task | Acceptance clause | Where main implements it | State |
|---|---|---|---|
| U3-3 | each required test ID bound to one committed test and one category | tools/qa/registry.py: exact-key test records, test_id equals selector, primary_category in PRIMARY_CATEGORIES, committed blob provenance | implemented |
| U3-3 | duplicate, missing and unknown IDs rejected | registry.py: duplicate selector or id rejected, registry set must equal the static AST set, count_passed rejects unknown outcome selectors | implemented |
| U3-3 | rejected before a run can give an accepting result | tools/qa/run.py calls validate_registry before any child is spawned; failure writes a BLOCKED record | implemented |
| U3-3 | counts re-earned on the landed head | no run on the landed head | NOT_RUN |
| U3-4 | bounded runner on Windows with argv, exit code, expected and collected IDs, artifact digests | tools/qa/run.py: suspended child in a Job Object with process and memory limits, wall-clock cap, output caps, tree kill; report holds redacted command, exit code, expected, collected, executed and passed IDs, artifact digests and sizes | implemented |
| U3-4 | report bound to the candidate head | run.py records candidate_head and head_after; tools/qa/gate_check.py requires both to equal the expected head | implemented |
| U3-4 | hash-pinned | dependency target and lock verified by digest; the interpreter is pinned by path and version only, not by hash | implemented with that limit |
| U3-4 | re-earned on the landed head | real lanes were NOT_RUN or red from known S2 failures | NOT_RUN |
| U3-5 | skipped or uncollected required test makes the result non-approving; policy exclusions keep INCONCLUSIVE | run.py reasons and gate_check.py codes SKIPPED_IDS, UNCOLLECTED_IDS, XFAIL_IDS, FAILED_IDS, UNEXPECTED_CASES, NOT_RUN_IDS, UNASSIGNED_IDS, RESULT_INCONCLUSIVE | implemented as a function |
| U3-5 | gate integration | gate_check.py is an advisory verifier and is not wired into tools/vst/gate.py | OPEN: this is real work in U3-5 |
| U3-6 | seeded-failure fixtures, no product code mutated, no mutation or CI runs | tests/qa/test_s4_seeded_failure_catalog.py (eight cases) and tests/qa/seeded_failure/catalog.json plus four AEVE fixture pairs | implemented; run NOT_RUN |

Real residual work of U3: U3-2 (no executor interface exists; the nearest thing is the CLI python -m tools.qa.run writing fixed report files), the gate wiring of U3-5, and the comparison of U3-7. Re-earning on the landed head stays NOT_RUN unless the operator names the exact run.
