# S5-A GPT-PM code review scope

Task: S5-A (VST-038), versioned static-analysis evidence provenance contract. Base f52069b (S4 merged), head = current HEAD. Review only: tools/vst/contracts.py, tools/vst/gate.py (minimal fail-closed change), tools/vst/schemas/README.md.

Delivers (plan docs/S5_AEVE_GATE_PLAN_2026-10-24.md S5.1.1, AC-1, AC-2): a v3 receipt/manifest contract with analyzer provenance fields for StaticAnalysis, closed enums, strict validation, v1/v2 unchanged; v3 manifest field required_rule_ids and require_static_rule_set_matches_manifest; derive_result gives FAIL on HIGH/CRITICAL findings; gate.py compares exact contract versions and returns NO_GO for any v3 manifest or receipt until S5-E wires v3 trust (fail closed).

Already fixed after two read-only reviewer rounds (python-reviewer, functional-test-reviewer): gate treating v3 as v1, findings ignored by derive_result, rule set not bound to the manifest.

Settled, do not reopen: v3 signing and trust roots, analyzer adapter, AEVE integration (S5-B..E, NOT_RUN, no authorized AEVE source). Tests: NOT_RUN (operator forbids pytest); evidence is static review only.

Ask: the complete BLOCKER/MAJOR set for this delta only.
