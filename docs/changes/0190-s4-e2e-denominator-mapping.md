# 0190 — Map bounded S4 E2E selectors and preserve report-bound gap

## What changed

- Mapped the five local E2E selectors from change 0189 in `docs/qa/categories.json`; the E2E primary list now contains twelve selectors at source commit `598d22ddf4db6a64c61db3f6441855e2f143bc30`.
- Kept E2E and aggregate regression coverage `PARTIAL`. The explicit remaining denominator gap is an E2E selector that drives `tools.qa.run` report serialization and v2 signed artifacts.
- Updated the sprint plan and runner technical design to distinguish fixture-level v1 runner/gate tests from report-bound v2, trusted signer, WSL transfer, and sandbox runtime acceptance.

## Why

Coverage completeness (`coverage_state`) describes whether accepted selector scope is enumerated, not whether tests ran. The five selectors are now enumerated, but they do not satisfy AC-9/AC-10 report-bound runner coverage. Runtime results are recorded separately after exact-head execution.

## Contracts and paths

- `docs/qa/categories.json` is the committed selector denominator; the mapped test IDs are E2E-primary.
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` and `docs/S4_QA_RUNNER_TECHNICAL_DESIGN.md` state the remaining report-bound denominator gap and separate runtime gates.
- `tools.qa.run` + v2 report serialization/signed artifact E2E remains the precise unimplemented coverage item. Trusted signer, WSL source transfer, and sandbox execution are independent runtime dependencies and are not asserted by local fixture selectors.

## Verification

- Reviewed the JSON diff and parsed `categories.json` with PowerShell `ConvertFrom-Json` before commit.
- The five mapped selectors are committed but runtime execution is pending the post-documentation exact-head E2E run; no PASS is claimed here.
- `source_head` records the commit that introduced the test code, not the later documentation commit.

Executor: Codex
