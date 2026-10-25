# Change 0249: Test and map the narrowed pytest pass prefix

## What changed

- Updated the functional parser regression selector to accept only plain `PASS <id>` and exact `.PASS <id>` lines.
- Added `..PASS` to malformed lookalike cases; it must not be parsed as a pass.
- Updated functional coverage prose and source provenance to parser code commit `ced64321330921cd1e6fcd2ed749789bed8401b3`.

## Why

The security review at code source `869cf36` found no BLOCKER/MAJOR and one MINOR: the previous implementation accepted an arbitrary number of leading progress dots while runtime evidence showed exactly one. Change 0248 narrows the implementation; this change locks the narrower parser contract into the functional selector registry.

## Decisions and ownership

- Keep the parser contract aligned with observed pinned pytest `-q` output and reject repeated dots or arbitrary prefixes.
- Test author and executor: `e2e-runner` (GPT-6 Luna, medium effort). Accountable task owner: operator. Coordinator: Codex.

## Affected contracts and paths

- Functional parser regression in `tests/qa/test_s4_pass_line_parser.py`.
- Functional category source provenance and coverage in `docs/qa/categories.json`.

## Verification state

- Parser source HEAD: `ced64321330921cd1e6fcd2ed749789bed8401b3`.
- Test and mapping are committed before execution. No test was run while authoring.
- Prior eight-selector and 26-ID functional CLI PASS evidence is at `e89fd18` and predates this exact-prefix narrowing.
- Required next steps: fresh snapshot at the commit containing this regression, run mapped selectors and full synthetic functional CLI, then obtain a fresh security review. Trusted signer, authoritative task gate, aggregate regression and E2E denominator remain open.
