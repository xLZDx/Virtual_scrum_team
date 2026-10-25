# Change 0262: Define the outer report-bound S4 category contract

## What changed

- Marked the existing 12-selector E2E denominator and 124-ID regression union COMPLETE in `docs/qa/categories.json`, while explicitly separating denominator completeness from exact-head runtime acceptance.
- Updated the S4 plan, backlog, decision log, and lessons log to define the outer `tools.qa.run --category ...` invocation as the report-bound boundary. Mapped selectors remain local and non-recursive; the outer runner executes them under worker identity and binds the QA report, event/stream evidence, manifest diff gate, and TestRun receipt.
- Reconciled the two preserved 97c2c24 drafts: their Windows unit run remains interim/non-accepting, and change 0261 at `bc32f6f` is cited as the superseding WSL/runtime evidence.
- No test IDs or product code changed.

## Why

The former PARTIAL rationale required a mapped selector to recursively invoke `tools.qa.run`. That cannot safely execute under worker UID 999, which has no runner capabilities or access to the runner-owned signer/output boundary. AC-2 and AC-9–11/14 are instead exercised by the complete outer category invocation: it runs the committed local selectors under the worker and binds the v2 report and receipt after exact ID/event accounting and the manifest diff gate. This satisfies the runner boundary without privilege regain or recursive CLI calls.

`COMPLETE` describes only committed denominator completeness. Exact-head outer CLI results remain separate runtime evidence. Trusted signer deployment, authoritative VST gate consumption, and sandbox deployment remain open. Regression remains the S4.5.1 union of functional (33), integration (6), API (73), and E2E (12) = 124 IDs; seeded-failure is separate.

## Decisions and ownership

- Preserve every existing test ID and primary-category assignment.
- Do not allow selectors to recursively launch the QA CLI, regain runner identity, or weaken worker restrictions.
- Test owner/executor: `e2e-runner` (GPT-6 Luna, medium effort). Accountable task owner: operator; executor: Codex. QA runner/gate and signer technical owners remain UNKNOWN in current records.

## Affected contracts and paths

- `docs/qa/categories.json`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`
- `docs/changes/0259-s4-source-acl-preflight-test-evidence.md`
- `docs/sdlc/evidence/s4-source-acl-preflight-97c2c24.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Verification state

- Source runtime evidence inherited from change 0261: at exact source/test HEAD `bc32f6f`, 15 focused selectors passed and synthetic functional outer CLI passed 33/33 IDs with report, receipt, and manifest diff gate PASS. The signer was synthetic and in-process.
- This documentation/contract change has not yet had an exact-head runtime run. The next verification is one clean exact-head snapshot and outer CLI invocations for functional, integration, API, E2E, seeded-failure, and regression, preserving each report/receipt/diff-gate artifact.
- Trusted signer, authoritative VST gate consumption, and sandbox deployment are NOT_RUN and not claimed by this change.

Executor: Codex
