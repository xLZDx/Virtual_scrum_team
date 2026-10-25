# Change 0248: Narrow the accepted pytest pass-line prefix

## What changed

- Restricted `vst.pass-lines` to accept only `PASS <test-id>` and the observed pytest quiet-mode form `.PASS <test-id>`.
- Lines with two or more leading dots, arbitrary prefixes, an empty ID, or surrounding whitespace are rejected.

## Why

The security review of source HEAD `869cf36` found a MINOR parser-contract concern: using `lstrip('.')` accepted any number of leading dots, although the exact Ubuntu-24.04 diagnostic observed one leading dot on each of 25 pass lines. The runner still compares parser IDs to the event IDs, and no passing-receipt exploit was demonstrated, but narrowing the parser to the recorded format reduces ambiguity and matches the supported command output exactly.

## Decisions and ownership

- Do not use general prefix stripping. Permit the plain synthetic form and the one-dot pytest `-q` form only.
- Accountable task owner: operator under delegated S4 work. Executor: Codex via `implementation-engineer` (GPT-6 Luna, medium effort). Test author and executor: `e2e-runner`.

## Affected contracts and paths

- Trusted parser in `tools/vst/contracts.py`; its source-derived hash changes with the implementation.
- Functional parser regression selector will be updated to reject repeated dots before execution.

## Verification state

- Base source/test HEAD: `e89fd18670a1c4a7bfa4fa5d40819ec7bb209538`.
- At that head the eight focused worker-boundary/parser selectors passed, and the synthetic functional `tools.qa.run` run passed 26/26 with PASS report, TestRun receipt and diff gate. That evidence predates this parser narrowing.
- Fresh security review at code source `869cf36` recorded the MINOR; no BLOCKER/MAJOR were found. Review was read-only.
- This narrowing is not yet tested or re-reviewed. Required next steps: test owner updates the parser selector/mapping, fresh exact-head WSL snapshot, focused test and functional CLI retry, then a fresh security review. No trusted signer, aggregate regression, authoritative gate, or E2E denominator completion is claimed.
