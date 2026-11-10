# U2-1 GPT-PM code review scope

Task: U2-1, bridge facts in the v3 receipt. Base bcdd25f (main after S5), head = current HEAD (two commits). Review the delta only: tools/uc/contracts.py, tools/uc/router.py (result gains role_table_sha256 and aeve_head), tools/vst/contracts.py (validate_bridge_facts, v3 StaticAnalysis fields), tools/vst/analyzer_authority.py (six new signed payload fields), tools/vst/analyzer_adapter.py (bridge_facts_from_role_result), tools/vst/analyzer_evidence.py, tools/vst/gate.py (_V3_RUN_FIELDS only), tools/vst/schemas/README.md, tests/uc fixture updates.

Delivers: the signed v3 evidence carries role_table_sha256, aeve_head, model_residual, reviewed_paths_sha256, findings_count, highest_severity, all bound by the analyzer-authority signature and compared by the gate against the verifier-owned expectation. bridge_facts_from_role_result re-validates the whole U1 result, requires the exact base revision, role status CLEAN or FINDINGS, no uncovered items, non-empty residual for LOCAL_PLUS_MODEL, unique repo paths. v1/v2 code paths are untouched (additions only).

Already fixed after three read-only reviewer passes (python 1 MAJOR, security 1 MAJOR, functional-test none).

Settled, do not reopen: refusal rules in the gate (any finding blocks, non-empty residual refuses, comparison of role_table_sha256/aeve_head with pinned values, findings cross-check) are task U2-4 and are intentionally absent here; the evidence record labels the two pins NOT_RUN. Negative tests are task U2-6. Tests NOT_RUN (operator forbids pytest); evidence is static review only.

Ask: the complete BLOCKER/MAJOR set for this delta only.
