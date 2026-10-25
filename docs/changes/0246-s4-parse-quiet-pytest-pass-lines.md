# Change 0246: Parse pytest quiet-mode pass records

## What changed

- Updated the built-in `vst.pass-lines` parser in `tools/vst/contracts.py` to accept an exact `PASS <test-id>` output line with zero or more leading pytest quiet-mode progress dots.
- The parser rejects arbitrary leading text, empty test IDs, and test IDs with surrounding whitespace. Its trusted parser digest remains derived from the parser source.

## Why

The S4 report-bound CLI reached and executed the full functional category on exact snapshot HEAD `5b5e6c7607b40a37bea8f4105c58e3577d830cf4`. The plugin event file recorded 25 collected and passed IDs, while the report parser returned none. The run was correctly rejected with `PARSER_AND_EVENT_PASS_IDS_MISMATCH` and produced no receipt. A bounded diagnostic run of the exact pinned pytest argv established the cause: pytest `-q` emitted all 25 pass records as `.PASS <nodeid>`, while `_parse_pass_lines` accepted only lines starting at column zero with `PASS `. This is a parser compatibility defect, not test failure or environmental inability.

## Decisions and ownership

- Preserve parser/event reconciliation as a fail-closed integrity check; do not make worker-generated event JSON the sole source of executed test IDs.
- Strip only leading `.` progress markers, require the complete `PASS ` record shape, and reject malformed or unrelated output.
- Accountable task owner: operator under delegated S4 work. Executor: Codex via `implementation-engineer` (GPT-6 Luna, medium effort). Test author and executor: `e2e-runner`.

## Affected contracts and paths

- Trusted pass-line parser and derived parser source digest in `tools/vst/contracts.py`.
- QA report/event reconciliation in `tools/vst/runner.py` remains unchanged.

## Verification state

- Base source HEAD: `5b5e6c7607b40a37bea8f4105c58e3577d830cf4`.
- Focused worker-boundary regression suite at that head passed 7/7 in Ubuntu-24.04 WSL, unit `vst-s4-worker-boundary-5b5e`, invocation `8a1ee98442e64efca2abf95e7820d4f9`.
- Report-bound functional attempt ran all 25 expected tests with exit status 0 and plugin events showing 25 passes, but parser output was empty. It returned BLOCKED/INCONCLUSIVE with no receipt. Unit `vst-s4-cli-functional-5b5e`, invocation `2cf26d1c16db463097b8ed326d5b0e56`; evidence JSON SHA-256 `a677c2795f978e1c472e74f41f32c34ec0a33fd613d0beeea0020f7fb349543a`.
- The exact pinned pytest argv diagnostic produced 25 `.PASS <nodeid>` lines, exit 0, stdout 2,595 bytes with SHA-256 `8b6d1951a494b0ed073c0df9a0429a3f138aa2bb8eeb7b6ffb8e133314f08ae1`; stderr was empty. Unit `vst-s4-pytest-stdout-diag-5b5e`, invocation `668b9b37ffc142e08ab85e2a4da6e0c8`.
- The source parser fix has not yet been tested. Required next steps: test-owner regression for dot-prefixed lines and malformed input; fresh exact-head WSL snapshot; focused tests; then retry the report-bound CLI. No signed receipt, trusted signer, aggregate regression, or full E2E denominator is claimed.
