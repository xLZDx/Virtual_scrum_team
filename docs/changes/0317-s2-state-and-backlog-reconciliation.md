# Change 0317 — Reconcile S2 state and backlog with recorded evidence

## What changed

- Updated `docs/sdlc/STATE.md` to identify the canonical repository baseline at the start of this continuation (`a760cbe8e2664d71733570245274cf690065c9fc`), preserve S2 source/test provenance at `dc95915018b80f498d5cf775363712fb915fe04e`, and clarify that the pending S2 GPT-PM gate is separate from the S4 REJECT at `ece606584a7c0dd86e76ce475d6f6728c6804508`.
- Reconciled the S2 plan's status and sprint-name note with its later implementation/evidence and the already-corrected blueprint roadmap.
- Replaced blanket S2 specialist-review-pending labels in VST-009 through VST-012, VST-015, VST-016, VST-018 and VST-019 with the reviews evidenced in the phase record, while keeping exact-head GPT-PM approval and runtime/system acceptance open.
- Added this per-change record and the related decision and lesson entries.

## Why

The S2 status file contains the actual bounded Phase 7 results and specialist findings, while the S2 plan and backlog retained baseline-era statements. Keeping those statuses stale obscured completed source review and focused evidence; promoting them to complete would incorrectly erase the remaining `NOT_RUN` and `NOT_VERIFIED` criteria. The update preserves original evidence heads and the distinct S2 and S4 gates.

## Evidence and scope

- Baseline observed before edits: canonical checkout `D:\Repo\Virtual_scrum_team`, HEAD `a760cbe8e2664d71733570245274cf690065c9fc`; initial `git status --short` showed only the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`. No initial diff existed for the edited tracked paths.
- S2 source, test, reviewer and remaining-acceptance evidence is recorded in `docs/sdlc/STATE.md`, including source HEAD `dc95915018b80f498d5cf775363712fb915fe04e` and exact prior repository/test heads. This change does not rebind those artifacts.
- Blueprint section 10 already labels S2 `Isolated worker sandbox`; no blueprint edit was needed.
- The prior GPT-PM S4 exact-head response is a REJECT, recorded in change 0316; it does not constitute an S2 decision.
- Documentation-only change. No tests, checks, builds, runtime scenarios, or S2/S4 gate actions were run.

## Remaining acceptance and owners

- S2 exact-head Phase 8 decision remains pending. GPT-PM owns the approval decision; Codex owns preparing and submitting the narrowly S2-scoped review against the resulting committed repository HEAD. Operator remains accountable for delegated S2.
- Prohibited process-kill and full crash/resume scenarios remain `NOT_RUN`; operator owns any policy authorization, and `e2e-runner` may execute only after that gate changes.
- Production runtime limits and containment items remain `NOT_VERIFIED` or `NOT_RUN` as listed in `docs/sdlc/STATE.md`; Codex owns coordinating the required evidence and the operator owns any platform provisioning decision.

Change: 0317
Executor: Codex
