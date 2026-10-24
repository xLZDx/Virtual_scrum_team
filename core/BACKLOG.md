# Backlog

| ID | Item | State | Notes |
|---|---|---|---|
| VST-001 | Raise `maxTurns` or split tasks for read-heavy design/explore agents | done 2026-10-15 | Raised in the global agents: code-explorer 8->16, code-architect 16->20, tdd-guide 16->24, e2e-runner 16->24, functional-test-reviewer 20->25 (lint cap), security-reviewer 16->24, doc-updater 8->12. Pilot evidence: test, security and design agents each hit their limit and needed a resume. Large multi-epic authoring tasks should still be split per epic |
| VST-002 | Let design agents save their own document | open | `code-architect` is read-only; the coordinator saved `design.md`. Decide: add Write for a docs path or keep the technical-writer hand-off |
| VST-003 | Choose a license for the public repository | done 2026-10-15 | Operator delegated the choice; MIT selected (permissive; recommended in chat). `LICENSE` added |
| VST-004 | Decide whether `security-reviewer` runs in every SDLC pilot sprint | open (pilot data: it found no BLOCKER/MAJOR twice, GPT-PM still required exact-head correlation) | Routing makes it opt-in only; GPT-PM asked for an independent security review in the pilot |
| VST-005 | Add a project template (`docs/sdlc/` skeleton with STATE.md) installable into a new project | open | Currently created by the orchestrator at first use |
| VST-006 | Resolve role alias `adk-tune-sql-query` with a dedicated SQL-tuning agent if `database-reviewer` proves too broad | open | Mapped to `database-reviewer` on 2026-10-15 |
| VST-007 | Keep the exact verification record of the final test run in the repo (command, collected list, head) | closed in effect 2026-10-24 | Retained evidence files under `docs/sdlc/evidence/` record command, head and counts. Origin: pilot, GPT-PM rejected the first final review because the run record and head were not retained |
| VST-008 | Put the exact-head rule into `sdlc-orchestrator`: run the security review and GPT-PM on one committed head, avoid source commits afterwards | partly done 2026-10-24 | The exact-head rule is enforced in code by `tools/vst/gate.py` (stale head gives non-approval). Open sub-item (small): add the wording to the `sdlc-orchestrator` skill. Origin: pilot cost one extra GPT round |
| VST-009 | S2 E1: authenticated reviewer key, distinct from the worker key; verify IndependentReview receipts with it | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Deferred out of S1: reviewer independence is currently a self-asserted label |
| VST-010 | S2 E2: runner-derived `candidate_head` | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Deferred out of S1 |
| VST-011 | S2 E2: isolate the signing key from the process that runs commands | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Deferred out of S1 |
| VST-012 | S2 E3: whole-database rollback detection through an externally anchored event head | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Deferred out of S1 (Known limits in `tools/vst/schemas/README.md`) |
| VST-013 | S2 E4: verify POSIX permissions and process-group behavior; verify Job Object nesting | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Not verified in S1 |
| VST-014 | S2 E5: sandbox specification (dedicated WSL distro or VM, automount and interop off, no container socket, default-deny egress, non-root, per-run secrets) and pre-flight probe | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Blueprint 13.4 |
| VST-015 | S2 E6: deterministic diff gate and read-only reviewer credential | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Blueprint 13.4 |
| VST-016 | S2 E7: STOP and rollback transition table | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Blueprint 13.4 |
| VST-017 | S2 E7: idempotency keys for push, pull request and receipts | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Blueprint 13.4 |
| VST-018 | S2 E7: circuit breaker with a paused-provider state and manual-override record | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Blueprint 13.4 |
| VST-019 | S2 E7: startup reconciliation after restart | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Blueprint 13.4 |
| VST-020 | S2 E8: isolated worker bake-off on one crash/resume fixture | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md). Needs the operator-provisioned sandbox |
| VST-021 | Operator: align the workspace `AGENTS.md` model default with ADR-0001 | open (operator-owned) | Outside this repository |
| VST-022 | Operator: align the global contract's list of test-writing agents with ADR-0001 | open (operator-owned) | Outside this repository |
| VST-023 | Operator: re-install the changed roster and skills into `~/.claude` with a snapshot first, then run the global lint | open (operator-owned) | Do after S1 closes |
| VST-024 | Operator decision O-1: keep, generalize or move the private repository names in this public repository | open (operator-owned) | Blueprint section 13.6 |
| VST-025 | S2: mandatory commands per slot listed in the manifest and checked by the gate; pin the test result parser | planned (S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md) section 9 (S2.D1). Found by the S1 independent review |
| VST-026 | S2 decision: restrict waivable results to NOT_RUN/INCONCLUSIVE/BLOCKED, or record in ADR_0001 that a FAIL may be waived | open (operator decision, S2) | [S2 plan](../docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md) section 9 (S2.D2) |
