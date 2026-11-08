REVIEW ITEM: U1-4 "[VST] Role table and validator", VERIFICATION ROUND for your BLOCKER and MAJOR of request c92e0b7f (diff base 9587052, head = current HEAD, limited to tools/uc/role_table.py, catalog/role_table.json and tests/uc/test_role_table.py).

Your findings and the changes:
1. BLOCKER, CLI control flow: main() now has separate build and validate branches. build: build_role_table, validate in memory, write only if there are no problems; validate: load --table and validate; both end with VALID (exit 0), INVALID (exit 1) or BLOCKED (exit 2 when the AEVE probe fails). Tests: 14 in-process main() cases (valid build, build then validate, tampered tables in four variants, probe failure) and 2 real subprocess CLI runs against the real AEVE (build reproduces catalog/role_table.json exactly, validate accepts it).
2. MAJOR, output before validation: the validated table is written to a temporary file next to --out and os.replace()d into place. Tests: an invalid build leaves an existing destination byte-for-byte unchanged, no .tmp file remains, and a new destination stays absent.

Known gap, deliberately not part of this fix: a builder refusal (inventory item without a draft decision) raises ValueError out of main().

Evidence: tests/uc 829 passed, 0 failed, 3 skipped (symlink creation not permitted on this host). Please check only that the two findings are closed and that the fix introduced no BLOCKER/MAJOR regression. Do not ask for full test runs, lint, typecheck or verification scripts (prohibited by the operator).
