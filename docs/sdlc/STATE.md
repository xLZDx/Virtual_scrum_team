# SDLC state

Project: Virtual Scrum Team   Sprint: S2   Phase: 7 - Verify (partial)   Base HEAD: `6117ba24`   Code HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`   Documentation HEAD before this update: `0f69d16ce2c67cb5c7114b61119ea62be785f1cb`   Updated: 2026-10-24

The S2 branch is `s2-isolated-worker-sandbox`; `6117ba24` was the recorded base before branching. Functional and E2E agents completed their current focused runs, and the selected dedicated Ubuntu-24.04 WSL2 environment has per-run E5 evidence. S2 is **not fully accepted or ready for PR**: prohibited process-kill/kill-table scenarios, Windows Job Object nesting, and full E8 crash/resume remain `NOT_RUN`; exact-head specialist consensus and final GPT-PM approval are pending. No push or PR is authorized by this state. The project has not initialized a VST store instance as its phase-state authority, so this file remains the phase record until the explicit cutover described in the S2 plan.

## Artifacts

| Phase | Artifact path | Author agent/model | Head | Status |
|---|---|---|---|---|
| 2 - Backlog | `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` | Existing artifact; origin not verified | `6117ba24` | Entry criteria and backlog decisions reconciled with evidence |
| 3 - Design | `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` section 10 | `code-architect` / `gpt-6-luna` | `6117ba24` | Trust roots, signer boundary, external-anchor recovery, parser catalog, state cutover and compatibility recorded |
| 4 - Docs and test plan | S2 plan sections 4-10 | Coordinator / Codex | `6117ba24` | Requirements-derived acceptance and negative-input denominators recorded; test authorship belongs to test agents |
| 5 - Documentation review | S2 design review and source map in execution records | `code-architect`, `code-explorer` / `gpt-6-luna` | `6117ba24` | One review/fix pass completed; findings reconciled in the plan |
| 6 - Build | `tools/vst/` and `docs/SANDBOX_SPEC.md` | Implementation agents / `gpt-6-luna` | `280e2d0` | S2 code and reliability/security follow-ups committed; no source changes followed this code head (records 0047-0054) |
| 7 - Verify | `tests/vst/` and `docs/sdlc/evidence/` | `functional-test-reviewer`, `e2e-runner` / `gpt-6-luna` | Test HEAD `d70b6b7`; latest repository HEAD before this update `0f69d16` | Windows combined focused run: 144 passed, 22 skipped. Owned WSL runs: 95 passed, 11 skipped, plus 2 POSIX identity tests passed. Per-run E5 probe and actual `run_manifest_commands` WSL integration passed. Skips and blocked/unavailable scenarios remain NOT_RUN; specialist review and GPT-PM approval are pending |

## Open acceptance and backlog items

- Process-kill/kill-table scenarios are `NOT_RUN` because the active task prohibits those actions. Accountable owner: operator; executor: Codex. Next step: obtain authorization for those exact scenarios, then assign execution to `e2e-runner`.
- Nested Windows Job Object runtime behavior is `NOT_RUN`; WSL2 does not prove Windows nesting. A technical platform owner is not established in this repository. Next step: run the focused scenario in a dedicated Windows environment with recorded evidence, if available.
- Full E8 crash/resume bake-off is `NOT_RUN` because the lifecycle scenario invokes a child termination (`os._exit`) and process-kill acceptance is prohibited. Accountable owner: operator; executor: Codex. Next step: authorize the exact crash fixture or record a scoped waiver through the project gate.
- Exact-head specialist consensus and GPT-PM approval are pending. Owners: relevant specialist agents for reviews and GPT-PM for the gate; operator remains accountable for delegated S2. No push/PR until exact-head approval.
- External worker candidate remains out of scope; only the hand-written worker is authorized by `core/DECISION_LOG.md`.

## Decisions and evidence

- The operator explicitly selected `gpt-6-luna` for agents in this continuation. This run-specific choice does not edit global model configuration.
- S2 implementation contracts and waiver limits: [S2 plan](../S2_SANDBOX_WORKER_PLAN_2026-10-24.md#10-decisions-required-before-implementation) and [decision log](../../core/DECISION_LOG.md).
- Evidence index: `docs/sdlc/evidence/s2-e2e-platform-run.md`, `s2-e2e-acceptance-280e2d0.md`, `s2-runmanifest-wsl-280e2d0.md`, and `s2-e5-operator-attestation.json`; change records 0056-0063 record scope, results and provenance.
