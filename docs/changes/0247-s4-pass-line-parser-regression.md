# Change 0247: Map quiet-mode pytest pass-line regression

## What changed

- Added `tests/qa/test_s4_pass_line_parser.py` to cover plain `PASS`, dot-prefixed quiet-mode pass records, and rejection of arbitrary prefixes, malformed separators, empty IDs and lookalike output.
- Mapped the selector in the functional category and pinned functional source provenance to parser code commit `869cf369de4fbd7a3aa523f75660b3d2dba3cb3d`.

## Why

The report-bound functional run at `5b5e6c7` recorded 25 pass outcomes in pytest event JSON, but the trusted parser returned no test IDs because quiet-mode pytest prefixed plugin output with progress dots. Change 0246 fixed the parser; this selector makes that exact output contract falsifiable.

## Decisions and ownership

- Preserve strict complete-line parsing. Dot-prefixed records are accepted only when the remaining full line starts with `PASS ` and contains a non-empty ID without surrounding whitespace.
- Test author and executor: `e2e-runner` (GPT-6 Luna, medium effort). Accountable task owner: operator. Coordinator: Codex.
- Linux/WSL execution is required for the full S4 acceptance path; the parser selector itself is platform-independent.

## Affected contracts and paths

- Built-in parser in `tools/vst/contracts.py`.
- Functional test source and category mapping in `tests/qa/test_s4_pass_line_parser.py` and `docs/qa/categories.json`.

## Verification state

- Parser source HEAD: `869cf369de4fbd7a3aa523f75660b3d2dba3cb3d`.
- Test and mapping changes are committed before execution. No test was run while authoring.
- Required next run: transfer a fresh clean snapshot at the commit containing this test mapping, execute the full focused worker-boundary/parser selector set, then retry the report-bound functional CLI. The prior CLI attempt remains BLOCKED/INCONCLUSIVE and produced no receipt.
- Trusted signer, signed report/receipt, authoritative gate consumption, aggregate regression and full E2E denominator remain open.
