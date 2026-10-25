# Change 0259: Preserve interim S4 source ACL unit evidence

## What changed

- Preserved the local five-case ACL preflight unit result at test HEAD `97c2c24` as interim, non-accepting Windows evidence with its static-registry limitation.
- Updated this historical draft to point to the corrected selector mapping and its later exact-head WSL/runtime proof at `bc32f6f` (change 0261).

## Why

The 97c2c24 Windows unit run occurred before discovery that the committed registry rejects bracketed parametrized node IDs. Its function bodies passed, but the mapped acceptance gate was invalid at that head. It remains interim/non-accepting evidence. The mapping was corrected in `180e330`; the corrected ACL selectors later passed as part of the 15-selector WSL run at `bc32f6f`, and the synthetic outer functional CLI passed 33/33 IDs with report, receipt, and diff gate PASS. Change 0261 and `docs/sdlc/evidence/s4-source-acl-preflight-runtime-bc32f6f.md` supersede this draft for current runtime acceptance.

## Decisions and ownership

- Do not count this run toward accepted mapped test coverage.
- Corrected mapped test ownership: `functional-test-reviewer`; exact-head WSL category/sandbox verification: `e2e-runner`.
- Accountable task owner: operator; coordinator: Codex.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-source-acl-preflight-97c2c24.md`
- ACL selectors and category mapping corrected by change 0258.

## Verification state

- Historical command/result: `C:\Python314\python.exe -m pytest -q tests\qa\test_s4_worker_boundary_contracts.py -k qa_preflight`; 5 passed, 7 deselected, exit 0, CPython 3.14.3 on Windows 11, one deprecation warning.
- Corrected selector/mapping runtime: 15 focused selectors passed at exact source/test HEAD `bc32f6f` in Ubuntu-24.04 WSL; the synthetic functional outer CLI passed 33/33 IDs with report/receipt/diff gate PASS. See change 0261 for commands, identities, and hashes.
- This 97c2c24 record remains historical interim evidence; it is not the current acceptance proof.

Executor: Codex
