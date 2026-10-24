# SDLC state

Project: Virtual Scrum Team   Sprint: S2   Phase: 7 - Verify   Base HEAD: code commit created with change record 0036   Updated: 2026-10-24

The S2 branch is `s2-isolated-worker-sandbox`. The base HEAD `6117ba24` was verified against `origin/main` before the branch was created. The S2 code is committed with change record 0036; test-agent execution is the next phase action. The project has not initialized a VST store instance as its phase-state authority, so this file is authoritative until the explicit cutover described in the S2 plan.

## Artifacts

| Phase | Artifact path | Author agent/model | Head | Status |
|---|---|---|---|---|
| 2 - Backlog | `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` | Existing artifact; origin not verified | `6117ba24` | Present; entry criteria and backlog decisions reconciled with current evidence |
| 3 - Design | `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` section 10 | `code-architect` / `gpt-6-luna` | `6117ba24` | Interface design incorporated; trust roots, signer boundary, external-anchor recovery, parser catalog, state cutover and compatibility recorded |
| 4 - Docs and test plan | `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` sections 4-10 | Coordinator / Codex | `6117ba24` | Requirements-derived acceptance and negative-input denominators present; detailed test scripts await code completion and test-agent authorship |
| 5 - Documentation review | S2 design review and code map in current execution record | `code-architect`, `code-explorer` / `gpt-6-luna` | `6117ba24` | One review/fix pass completed; findings were reconciled in the plan; no tests or checks run |
| 6 - Build | `tools/vst/` and `docs/SANDBOX_SPEC.md` | Three `implementation-engineer` agents / `gpt-6-luna` | Code commit with change record 0036 | Code reported complete across E1-E8 support; no tests/checks or runtime evidence; two accidental `git diff --check` invocations are recorded in change records 0035 and 0036 |
| 7 - Verify | `tests/vst/` and `docs/sdlc/evidence/` | `functional-test-reviewer`, `e2e-runner` / `gpt-6-luna` | Initial code commit `b2b168e`; parser fix follows in record 0037 | In progress. First functional run reported 30 passed / 3 failed for untrusted parser pins; fix is committed separately and must be rerun. E2E runs are underway. Mutation, process-kill/kill-table and CI runs are prohibited by the S2 continuation instructions |

## Open questions / backlog items (owner)

- Sandbox provisioning for E5 and dependent E4/E6-E8 acceptance — operator-owned action; the technical service owner for host provisioning is not established in this repository. Codex will finish independent work before asking at the E5 provisioning step.
- Exact POSIX and nested Windows Job Object behavior — runtime evidence required from the provisioned sandbox/platform; test agents own execution after sprint coding. Any prohibited process-kill/kill-table scenario remains `NOT_RUN`.
- External worker candidate — not authorized for this run; hand-written worker only, by decision in `core/DECISION_LOG.md`.

## Decisions

- [ADR-0001](../ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md) remains the recorded project decision for test ownership, CI, waivers and model policy. The operator explicitly selected `gpt-6-luna` for this continuation; this run-specific instruction is recorded in `core/DECISION_LOG.md` and does not edit global model configuration.
- S2 implementation contracts and waiver limits: [S2 plan](../S2_SANDBOX_WORKER_PLAN_2026-10-24.md#10-decisions-required-before-implementation) and [decision log](../../core/DECISION_LOG.md).
