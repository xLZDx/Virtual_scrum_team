# Change 0250: Record exact-head S4 report-bound functional evidence

## What changed

- Added `docs/sdlc/evidence/s4-reportbound-functional-c2eefda.md` with the exact focused-selector run and synthetic report-bound functional CLI evidence at source/test HEAD `c2eefda17d1294e81fe11f5b7dc16552e0916ca8`.
- Recorded artifact hashes, WSL unit/invocation IDs, worker identity/capability observations, report/receipt/diff-gate outcomes and explicit remaining boundaries.

## Why

After the pass-line parser was narrowed to exact plain `PASS ` and `.PASS ` lines and the test regression was mapped, a fresh exact-head WSL run passed all eight focused selectors. The synthetic COMPLETE-functional CLI then passed all 26 mapped IDs, generated a PASS QA report and TestRun receipt, and passed its diff gate. This closes a local functional report-serialization/runtime gap while preserving the distinction from trusted signing, E2E-category coverage, aggregate regression and authoritative task-gate acceptance.

## Decisions and ownership

- Treat this as evidence for the functional category only. Do not infer deployed signer trust or an E2E denominator pass from a synthetic signer and a functional-only receipt.
- Keep the E2E denominator PARTIAL until an accepted runner-owned orchestration contract or equivalent design makes report-bound E2E testable without allowing the worker to regain runner identity.
- Accountable task owner: operator under delegated S4 work. Executor: Codex. Test author/executor: `e2e-runner` (GPT-6 Luna, medium effort).

## Affected contracts and paths

- S4 functional category report/receipt and worker boundary in `tools/qa/run.py`, `tools/vst/runner.py`, `tools/vst/worker_exec.py`, `tools/vst/sandbox.py`, and `tools/vst/contracts.py`.
- Evidence and S4 status: `docs/sdlc/evidence/s4-reportbound-functional-c2eefda.md`, `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`, bilingual S4 reports and VST-032–037 backlog row.

## Verification state

- Focused run: eight selectors passed in 0.77 seconds on source/test HEAD `c2eefda`; unit `vst-s4-boundary-parser-c2ee.service`, invocation `e4b3f9df04a6476eb856a0de8d033a1a`.
- CLI run: 26/26 functional IDs passed; report PASS, TestRun receipt PASS, diff gate PASS. Unit `vst-s4-cli-functional-c2ee.service`, invocation `9afefd4da15c4173b6e5c8f10dad28db`.
- Report, events, full evidence JSON, stream references and hashes are detailed in the evidence file. The signer/key were synthetic and ephemeral.
- The authoritative task gate was not evaluated. Trusted signer NOT_USED; aggregate regression NOT_RUN; E2E denominator PARTIAL. Fresh exact-head specialist review and GPT-PM approval remain pending.
