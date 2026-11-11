# U5-7 GPT-PM code review scope

Task: U5-7, one small real change through the pipeline. Base: U5-6 approved head (5166f06), head = current HEAD. Review the delta only: `tools/vst/u5_real_change_driver.py`, `docs/sdlc/u5/REAL_CHANGE.md`, this note, and the `core/DECISION_LOG.md` and `core/LESSONS_LOG.md` entries. No production module was edited and no target file was changed.

Delivers: a reproducible driver and an honest record of one real run. The driver takes an AEVE `g6.patch.v1` proposal (real `capture_snapshot` + `propose_patches_report`, `llm_calls` 0) for `tests/uc/test_token_baseline.py` (four trailing-whitespace lines), applies it through `apply_proposals` with scope exactly that file, a real `IsolationContext` and the real git runner, then would run the real router/AEVE review loop and `build_final_package`.

Measured outcome: `apply_proposals` was BLOCKED twice and changed nothing. Full document: `PROPOSAL_REDACTED` (a redaction marker in another file's diff blocks the whole document). Narrow document (snapshot cut to the file): `UNTRUSTED_GIT_CONFIG` because the repository's own `.gitattributes` sets `*.py text eol=lf`. The review loop and the final package are NOT_RUN as a consequence. One extra real AEVE review of the unchanged file through router and adapter ran (PARTIAL, exit 3).

Interpretation: the acceptance asks for a run with the authoring path and isolation stated and unrun items marked NOT_RUN. The run is reported as measured; a block is a measured result and was not worked around. The outcome is not production-ready.

Limits: one run, one machine; stages 3 and 4 and the write stage of U5-2 are unproven; defects 5 and 6 in REAL_CHANGE.md are findings from reading code. The isolation is Windows-local with no OS sandbox and no process containment; only three isolation properties are VERIFIED and three are CALLER_ASSERTED. The manifest digest was made by the driver. No U5 module was changed.

Tests: NOT_RUN. Running tests is forbidden by the operator for this sprint. The driver was syntax-checked with `ast.parse` and executed once as a real run; it starts no test runner.
