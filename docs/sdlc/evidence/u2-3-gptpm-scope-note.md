# U2-3 GPT-PM code review scope

Task: U2-3, receipt builder. Base 38cc4ea (U2-4 accepted), head = current HEAD (two commits). Review the delta only: tools/vst/receipt_builder.py (new), tools/vst/analyzer_adapter.py (bridge_facts_from_role_result, tracked entries at the verified head), tools/uc/contracts.py and tools/uc/router.py (result gains purpose and changed_paths_sha256), tools/uc/secret_patterns.py (new), tools/vst/schemas/README.md, tests/uc fixture updates, docs/unified/UNIFIED_CORE_TDD.md.

Delivers: build_static_receipt returns an unsigned v3 StaticAnalysis receipt body and analyzer payload from a validated U1 role result. It binds the analyzer report to the reviewed set (tree digest, analysis_scope, candidate head), binds the role result to purpose=receipt and the changed-path hash, requires reviewed == required paths exactly, refuses dirty trees and secret-like values, maps every failure to an RB_* code, validates the body and payload before returning, and offers PASS only for a CLEAN role with no findings and no model residual. Signing stays in analyzer_authority; the gate decides.

Already fixed after three read-only reviewer passes (python 1 MAJOR, functional-test 2 MAJOR, security 3 MAJOR; converging on report/role-result binding and the RB contract).

Settled, do not reopen: the gate-side comparison of reviewed_paths_sha256 with a verified diff-gate path list is a recorded dependency for U2-5/U2-6, not part of this delta; deleted or renamed paths cannot be covered and fail closed; the gate decides on residual/findings (U2-4, accepted). Tests NOT_RUN (operator forbids pytest); negative tests are task U2-6; evidence is static review only.

Ask: the complete BLOCKER/MAJOR set for this delta only.
