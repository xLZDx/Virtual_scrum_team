# S1 third round: E1/E2 test run (invisible/filler principal characters)

Command (repo root, branch s1-control-plane-core):
`C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_e1_contracts.py tests/vst/test_e2_gate.py`

Head: `git rev-parse HEAD` = f1956e24933ca4a89cb215b7ce174d65ea263f49
Dirty state: dirty (13 entries in `git status --short`: modified contracts.py, runner.py, slice.py, store.py, the two test files, docs; one untracked change record). Results are for the working tree, not for the bare head.

Result of the final run: 863 passed, 1 warning (pytest-asyncio deprecation), 0 failed.

Tests changed/added:
- Three `match="control or format"` assertions updated to the new message in test_e1_contracts.py.
- New parametrized cases (11 characters: VS-1, VS-16, VS supplement U+E0100, U+034F, U+3164, U+FFA0, U+17B4, U+17B5, U+115F, U+1160, unassigned U+0378) for normalize_principal, review receipt reviewer/author principal, and manifest author_principal; `alice\ufe0f` is asserted not to equal `alice`.
- test_e2_gate.py: gate-level test that an invisible-suffix reviewer variant of the author never yields APPROVE.

Defects found in tests (fixed): the first run had 2 failures. My expected code point for U+3164 and U+FFA0 was wrong; NFKC maps both to U+1160 before the check, so the error message reports U+1160. Expected values corrected.

Product bugs: none found. Note: the error message reports the NFKC-composed code point, not the original input, which can confuse an operator (not a defect against the stated contract).

Not verified: the E2 gate test accepts either ContractError or a non-APPROVE verdict (it does not pin which); no mutation/red-run was done (operator rule); other test files, CI and full suite not run; characters outside the listed set (e.g. other default-ignorable code points such as U+2800 braille blank, category So) are not rejected and not tested.
