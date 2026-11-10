# U2-4 GPT-PM code review scope

Task: U2-4, gate refusals on the bridge facts. Base 1b40bbb (U2-1 accepted), head = current HEAD (two commits). Review the delta only: tools/vst/gate.py (_check_static_v3), tools/vst/analyzer_evidence.py (pin-check fields), tools/vst/schemas/README.md.

Delivers: for a v3 StaticAnalysis receipt the gate refuses with hard reasons, for every result and coverage state, collected in one pass: STATIC_FINDINGS_PRESENT (any finding of any severity, or findings_count > 0), MODEL_RESIDUAL_OPEN (non-empty model_residual), ROLE_TABLE_DRIFT and AEVE_HEAD_DRIFT (strict compare to gate-owned trust["pinned"] values, format-validated, never run["expected"]). A waiver cannot cover them; nonce is not consumed on a refusal. The evidence record reports PASS/FAIL/NOT_RUN for the two pins and rejects contradictions with the decision. v1/v2 paths are unchanged.

Already fixed after three read-only reviewer passes (python none, functional-test none, security 1 MAJOR: early return on non-FULL coverage hid the refusals).

Settled, do not reopen: consequence that a role with an open model slice (LOCAL_PLUS_MODEL) cannot be approved by static evidence alone is intended. Recorded limits, not defects of this delta: reviewed_paths_sha256 is bound by the analyzer signature only (the gate has no own changed-path list for the static slot); no receipt expiry (no clock source; replay is covered by epoch, head and one-shot nonce); trust["pinned"] is supplied by the caller and must come from a source independent of run["expected"] (no in-tree builder yet). Negative tests are task U2-6. Tests NOT_RUN (operator forbids pytest); evidence is static review only.

Ask: the complete BLOCKER/MAJOR set for this delta only.
