# Decision log

Append-only. One dated entry per decision, piece of evidence or refusal.

## 2026-10-15 -- Team created from the operator's request

Operator asked for a virtual scrum team (BA, product owner, architect, UI designer, tester, developer,
PM, technical writer, reporting) following the SDLC from idea to delivery. Inventory of the existing 28
global agents and 31 skills found gaps: no BA, product owner or UI designer; weak PM, technical writer
and reporting roles. Decisions: create 5 agents and 7 skills; PM is the skill `sdlc-orchestrator` run
by the main session because subagents cannot launch other agents; reuse existing architect, developer
and tester agents; map operator aliases `adk-test-engineer` to `tdd-guide` (E2E: `e2e-runner`, test
assessment: `functional-test-reviewer`), `adk-data-engineer/perf-tuning` to `performance-optimizer`,
`adk-tune-sql-query` to `database-reviewer`. Concepts adapted from BMAD-METHOD, spec-kit and
claude-scrum-team (all inspected only through web search summaries; no text copied).
Evidence: global lint after installation reported MODEL_POLICY=PASS, 0 model violations, 0 unresolved routes;
router eval 15 of 15 fixtures passed.

## 2026-10-15 -- `functional-test-reviewer` made an author

The agent lacked Write, Edit and Bash although workflow rules require it to write and run per-epic
functional tests. Added the tools and an explicit default read-only review mode; author mode only on
the parent's request, document or test files only, never product code.

## 2026-10-15 -- Pilot lessons (RQDO G10-FEED-0)

- Turn limits of T1/T3 agents were too small for read-heavy tasks (see VST-001).
- Three independent reviewers (reliability, silent-failure, architect) found no BLOCKER but 9 MAJOR
  design defects before any code existed; GPT-PM then rejected the documentation gate with 2 BLOCKER
  and 7 MAJOR findings the internal reviewers had not found (tenant-bound identity, visibility-scoped
  removal). Lesson: internal review does not replace the GPT gate; include security-reviewer for
  trust-boundary designs when the operator allows it.

## 2026-10-15 -- Team fixes after the RQDO pilot (VST-001 done)

- Raised `maxTurns` of the agents that hit their limit in the pilot (see VST-001); `functional-test-reviewer` stays at the lint cap of 25. Snapshot of the previous definitions: `~/.claude/control-plane/snapshots/team-fixes-before-2026-10-15/`. After the change `agentctl.py --strict` shows only a pre-existing ERP CLAUDE.md size error and `run_eval.py --router` passes 15/15.
- Added a "Reporting discipline" section to `security-reviewer`, `silent-failure-hunter` and `reliability-reviewer`: the final message must contain full findings in the finding contract, never only titles, and the agent must report early when turns run out.
- Pilot lessons: (1) GPT-PM final review rejected a head whose evidence was only agent-reported with no retained run record: keep `docs/sdlc/evidence/` files (VST-007); (2) a security review must name the exact committed head, and a later source commit invalidates it (VST-008); (3) tests written from the plan and design found five real defects (DNS failure outcome, Retry-After shortening, missing source time, deadline precedence, tenant mismatch handling) and the GPT-PM review found three more that tests and three specialist reviews missed (rescan authority, terminal-path deadline, freshness aggregate consistency): keep the final GPT gate; (4) large multi-epic test authoring is better split per epic.

## 2026-10-15 -- License: MIT (VST-003 done)

The operator asked for a license to be set after MIT and Apache-2.0 were named as the usual options. MIT was chosen as the simplest permissive license; the copyright holder is the repository owner handle `xLZDx`. Change: add `LICENSE`. Reversible by a later relicense commit; earlier commits remain under the terms they were published with (none stated).

## 2026-10-23 -- Unified organization design: MODIFY after devil's-advocate review

Evidence: six read-only reviewer agents (architecture, security, reliability, test strategy, silent-failure, consistency) all returned MODIFY DESIGN for the proposed integration blueprint. Decision: keep the architectural boundaries (Virtual Scrum Team as the single SDLC authority, workers never self-approve, PM Bridge only at closure, `NOT_RUN` never becomes `PASS`) and withdraw the earlier "DESIGN GO" wording. Six items (signed receipts, a total gate verdict function, a fenced state store, append-only receipts with terminal failure states, an ADR for test order / CI / mutation policy, enforced concurrency and cost limits) are required before the worker pilot S3. Open operator decisions: whether private repository names stay in this public repo (O-1), whether more than two agents may author tests (O-2), whether any CI outside phase 7 is allowed (O-3). Details: blueprint section 13, dossier section 11, change record `docs/changes/0004-unified-organization-blueprint-and-review-amendments.md`. Reversible: documentation only.

## 2026-10-23 -- Round 3 record corrections; public history kept

Evidence: Round 3 read-only verification of `da22d2a` (self-check by the authoring session, not independent). `git ls-remote origin` shows `origin/main` at `d4aefb5`, so `core/STATE.md` was wrong to say nothing was pushed; `0a5821b` on `origin/main` contains a local absolute path in `core/STATE.md`. Decisions by the operator: keep git history unrewritten (no force push); correct the records in a separate local commit. Correction: the earlier entry "Unified organization design: MODIFY after devil's-advocate review" and change record 0004 imply the operator directed the amendments; in fact the "fix and commit" answer was accepted automatically by the question policy while the operator was silent, and the operator has not accepted the design. Design verdict remains MODIFY DESIGN with no blocker closed. Change record: `docs/changes/0005-round3-records-correction.md`.

## 2026-10-24 -- ADR-0001: test authority, reviewer models, CI, NOT_RUN

Four operator answers (given directly, not auto-accepted): (1) only `functional-test-reviewer` and `e2e-runner` author and run required tests; `tdd-guide` and `performance-optimizer` are advisory; (2) the operator's global contract governs reviewer models (Sonnet 5.5 medium or GPT-5.6 Luna low/medium); (3) no CI; (4) `NOT_RUN` never yields an ordinary APPROVE, the separate verdict `APPROVED_WITH_WAIVER` needs a named operator record. Record: `docs/ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md`, change record `docs/changes/0006-adr-0001-operator-policy-decisions.md`. Not changed: workspace `AGENTS.md` model default, the operator's global contract (four test writers), installed copy of the roster. Design verdict remains MODIFY DESIGN.

## 2026-10-24 -- Blueprint consistency after ADR-0001

An external verification of `e4be280` reported four inconsistencies; all four were confirmed in the file and fixed (waiver verdict in the gate contract, stale tdd-guide sentence, contradictory C-1 line, CI wording). Record: `docs/changes/0007-blueprint-consistency-after-adr-0001.md`. Design verdict remains MODIFY DESIGN; independent review of the new head is still required.

## 2026-10-24 -- Design baseline 1.0, S1 plan, push ordered by the operator

The operator instructed: assemble the final design and plan, commit, push, start development. Done: baseline decisions BD-1..BD-7 and the S1 plan in `docs/DESIGN_BASELINE_AND_IMPLEMENTATION_PLAN_2026-10-24.md`; GitHub URLs of four private repositories (checked with `gh repo view`) removed from the public blueprint before the push. Limit: the baseline is explicitly not independently reviewed and does not close the review blockers; they are S1 work items. The push of the documentation commits to `main` was ordered by the operator and made without a final independent approval; this is a single named waiver of that gate and does not extend to the S1 sprint pull request, which still needs the final independent approval on its exact head.

## 2026-10-24 -- Report committed on the sprint branch

The report-due hook required a report for the review and baseline commits. It was written and committed on `s1-control-plane-core` (not `main`) because switching branches would disturb the running S1 implementation work in the same checkout. Record: `docs/changes/0010-review-and-baseline-report.md`.

## 2026-10-24 -- S1 E1/E2 code: contracts, signing and gate (written, untested)

Implementation agent wrote `tools/vst/contracts.py`, `signing.py`, `gate.py` and the schema README under the S1 plan; no tests have run by design (build phase). Known design gap found in its report: `derive_result` makes a supervisor-written BLOCKED/INCONCLUSIVE receipt (needed for WORKER_LOST, decision BD-5) invalid for non-Documentation types; to be fixed together with E3 by accepting non-approving results (BLOCKED, INCONCLUSIVE, NOT_RUN) as given, since they can never produce an approval. Record: `docs/changes/0009-s1-e1-e2-contracts-and-gate.md`.

## 2026-10-24 -- S1 E6: single state authority with a transitional rule

Resolves review finding VEO-R2-B01 at documentation level: `sdlc-orchestrator/SKILL.md` and the Definition of Done now say the state store becomes the only authority once accepted and `STATE.md` its generated view; until then `STATE.md` stays authoritative, so there is never more than one authority. Record: `docs/changes/0012-s1-e6-state-authority-alignment.md`. Installed skill copy not re-installed.

## 2026-10-24 -- S1 E3/E4 code: state store and runner (written, untested)

Implementation agent wrote `tools/vst/store.py` (SQLite, epoch compare-and-swap, leases and slots in one transaction, append-only receipts and hash-chained events via triggers, budget ledger, supervisor receipts for lost workers, generated STATE view) and `tools/vst/runner.py` (no-shell command execution, signed TestRun receipt, artifact hashes), and fixed `derive_result` so non-approving results (BLOCKED, INCONCLUSIVE, NOT_RUN) are accepted as given. Resolved ambiguities are listed in `docs/changes/0011-s1-e3-e4-store-and-runner.md` and the agent report: story ownership has a TTL (`stories.owner_expires_at`), the supervisor uses the first Documentation slot, and a new attempt is refused while a reaped attempt has no supervisor receipt. Known gaps to close before tests: no BLOCKED(budget) receipt writer, trigger violations surface as raw `sqlite3.IntegrityError`, no owner renewal (not needed for S1 drills). No tests have run.

## 2026-10-24 -- S1 E5 code and store gap fixes; sprint code complete (untested)

Implementation agent wrote `tools/vst/slice.py` (synthetic vertical-slice driver with ten named scenarios) and closed three store gaps: trigger violations raise `StoreError(kind='append_only')`, `Store.mark_budget_exceeded` writes a signed BLOCKED receipt, and `renew_epoch`/`release_epoch` exist. With this commit all six S1 epics have code; no test has run. Next by the operator workflow: `functional-test-reviewer` and `e2e-runner` write and run focused tests per epic, then specialist reviewers on the exact head, then the final independent review and one pull request. Record: `docs/changes/0013-s1-e5-slice-harness-and-gap-fixes.md`.

## 2026-10-24 -- S1 test phase: defects fixed, focused tests green

First full run of the test agents' sets: E1-E4 522 of 523 passed, E5 18 of 18. The failure was a real defect (`run_and_sign` with a missing cwd raised NotADirectoryError instead of recording exit -2). The tests also exposed an acceptance gap (no artifact binding for 'modified artifact rejected') and an ordering fault (commands ran before inputs were validated). Fixes (change record `docs/changes/0014-s1-test-phase-defect-fixes.md`): OSError mapping to -2, input validation before any command, required `artifact_digests` in TestRun receipts with an optional `artifact_resolver` in the gate. After the fixes: E1-E4 603 of 603, E5 18 of 18, no skips, no xfail (evidence `docs/sdlc/evidence/s1-e1-e4-test-run.md`, `s1-e5-test-run.md`). The fixed code was tested as a working-tree state on top of c786755 and is committed unchanged in this commit. Known limits recorded: event-chain tail truncation undetectable, HMAC proves origin not honesty, mutation runs NOT_RUN by operator decision. Next: specialist reviewers on the exact committed head, fixes, final independent review, one pull request.
