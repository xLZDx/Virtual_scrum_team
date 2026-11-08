REVIEW ITEM: U1-3 "[VST] Request and result contracts" (one task; the diff is limited to tools/uc/contracts.py and tests/uc/test_contracts.py).

Context: Unified Core sprint U1. A deterministic local analyzer returns findings about an UNTRUSTED repository to an LLM orchestrator, so the result channel must not carry repository-controlled text as instructions.

Acceptance for U1-3: schemas uc.role-request.v1 and uc.role-result.v1 (plus the uc.blocked.v1 envelope) with strict validators: root on an allowlist; changed_paths relative POSIX without .., drive letter, backslash, control / format / bidi characters, reserved Windows device names, symlink or junction parts, length-capped; unknown fields rejected (the error does not echo the unknown field name); result findings hold only enums, integers, hashes and validated paths; a CLEAN role is impossible with findings, uncovered scope, a model residual, a non-COMPLETE executor, class MODEL_ONLY / OUT_OF_SCOPE / UNKNOWN; exit_code agrees with the role statuses.

Evidence already in hand (HEAD 128f039): tests/uc 815 passed, 0 failed, 3 skipped (symlink creation not permitted on this host; junction tests ran). Three internal reviews done, findings fixed in 55578c0. U1-2, U1-5 and U1-6 were approved by you earlier; do not re-review them.

Decisions already taken: path text reaching the orchestrator is further restricted by the router (allowlisted charset or opaque digest) and is out of scope here; free-text criteria exist only in the request and are never executed.

Please review ONLY contracts.py and its tests for correctness and security defects: BLOCKER/MAJOR with a concrete failing input. Do not ask for full test runs, lint, typecheck or verification scripts (prohibited by the operator); documentation findings are out of scope.
