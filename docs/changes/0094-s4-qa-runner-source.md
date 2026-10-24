# 0094 S4 bounded native QA runner source slice

## What changed

- Added the committed `docs/qa/categories.json` category and test-ID inventory, strict registry/manifest projection validation, a POSIX-only CLI, and a hash-pinned pytest 7.4.4 dependency lock for the observed Ubuntu 24.04 / CPython 3.12.3 environment.
- Added a pytest plugin that emits bounded collection/outcome events and the existing v2 VST runner's optional canonical report artifact path. The report, registry, dependency lock, events, and content-free stdout/stderr digest references are predeclared signed artifacts.
- The v2 path validates report/event evidence and derives PASS/FAIL/INCONCLUSIVE before signer calls. Structurally valid acceptance failures, including skipped, xfailed, uncollected and XPASS cases, remain typed FAIL receipts; malformed or inconsistent event evidence aborts signing.
- The CLI enforces a per-run worker-group writable artifact directory and refuses execution unless tracked source and Git state are read-only to the worker identity.
- Only the exact validated report/events/stream-reference artifacts are excluded from source-diff evidence; they remain separately hashed signed artifacts. Other untracked files remain in the candidate diff.

## Why

S4 requires manifest-derived category selection and a deterministic privacy-safe report bound to the existing exact-head v2 TestRun gate. The repository's signer execution path is POSIX-only. The named Ubuntu 24.04 inventory therefore supersedes the stale Windows Python 3.14.3 plan pin for this implementation slice.

## Affected contracts and paths

- `tools/qa/`: CLI, registry validator, pytest event plugin, direct dependency input and lock.
- `docs/qa/categories.json`: canonical static inventory; each run's tracked v2 task manifest must project supported categories, IDs, and exact selectors.
- `tools/vst/runner.py`: optional report artifact seam; omitted arguments preserve existing callers and signed v1/v2 fields/domains.
- `docs/S4_QA_RUNNER_TECHNICAL_DESIGN.md`, `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex / `implementation-engineer` (GPT-6 Luna).
- Canonical technical owner for runner and lock maintenance is not established in project ownership sources; `UNKNOWN`.
- Only required runtime dependencies are pinned: pytest 7.4.4, iniconfig 1.1.1, packaging 24.0, and pluggy 1.4.0. pytest-asyncio is absent in the named environment and no current async test marker was found, so it is not added speculatively.
- Coverage inventory remains provisional/partial. The runner does not implement Windows-to-WSL repository transfer, package provisioning, or signer provisioning.

## Verification state

- Manual source review only; no tests, checks, builds, CI, installations, migrations, or QA execution were run during coding.
- Runtime availability outside the named inventory, source snapshot transfer into WSL, signer socket access, full S4 test denominator, seeded-failure fixtures, and end-to-end gate acceptance remain `NOT_RUN`.
- Local code is not yet independently reviewed or runtime-proven. A missing/unsafe worker permission boundary fails closed.

## Follow-up

1. Functional/E2E agents expand and map the category denominator to accepted S4 stories, then author/run required tests after source coding is complete.
2. Provide an in-scope immutable source snapshot and signer/runtime access inside the named WSL environment; technical service owner is `UNKNOWN`, next action is to define and provision that integration boundary.
3. Run exact-head gate and report-artifact validation only after those dependencies are available.
