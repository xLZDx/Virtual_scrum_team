# Decision log

Append-only. One dated entry per decision, piece of evidence or refusal.

## 2026-10-24 -- Restrict WSL queries to the named project distribution

While validating the user-selected `Ubuntu-24.04` sandbox, Codex ran `wsl --list --verbose`, which enumerated distribution names outside the project environment. No other distribution was accessed or modified. Decision: use only direct `wsl --distribution Ubuntu-24.04` commands for further work; do not inspect unrelated WSL environments. Recorded in change record 0061.

## 2026-10-24 -- Keep S4 primary-category and regression membership separate

Documentation review of `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` found AC-1 assigned each test ID to exactly one category while S4.5.1 defined regression as a union of IDs from four other categories. Decision: each test ID has exactly one `primary_category`; regression is a separate aggregate manifest that references the category IDs without reassigning them. This preserves one primary denominator and an explicit regression denominator. S5 plan review also found a broader mandatory-rule interpretation than blueprint section 13.3 allows. Decision: only rule IDs linked to committed seeded-defect evidence are required for S5; S4's fixture catalog is a prerequisite. The S2 provisioning guide's current step 5 already lists all six trust roots, so no edit was needed for that review note. Implemented in documentation change record 0055.

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

## 2026-10-24 -- S1 specialist review: unanimous MODIFY, remediation package decided

Four read-only reviewers (silent-failure-hunter, security-reviewer, reliability-reviewer, architect) on head 63e0e35 all returned MODIFY. Coordinator re-checked in the code: no manifest hash and no role_sha256 comparison in the gate, unsigned waiver without task/epoch binding, `store.py` never verifies signatures, artifact check skipped when no resolver is passed (`gate.py:160`), `INSERT OR REPLACE` on leases (`store.py:427`), retry_cap not checked at lease acquisition. Decisions for the remediation package: (1) one chain definition shared by store and gate - supervisor markers live in the reserved slot `__supervisor__` with their own chain, older-epoch receipts are history findings, the latest attempt of a slot decides and must be in the current epoch; (2) manifest gains author_principal, required_tests, allowed_commands, required_rules and a recomputed manifest_sha256 carried by every receipt; (3) artifact check and waiver are default-deny (waiver signed with an operator key and bound to task, epoch, head, manifest, expiry); (4) store verifies signatures, requires a live lease and a task-to-story link on append, keeps lease history and enforces retry_cap at lease acquisition; (5) runner gets bounded output, tree kill, overall deadline, minimal environment and artifact path containment; (6) separate keys for runner, supervisor and operator with a minimum length and a domain label. Deferred to S2 with the sandbox specification: runner-derived candidate_head and isolating the signing key from the process that runs the commands. No final independent review yet.

## 2026-10-24 -- S1 remediation implemented; focused tests green; review pending

Both remediation parts are written (change records 0015 and 0016) and the test agents updated and ran the complete sets on the working tree over 63e0e35: E1-E4 1105 passed and 2 skipped, E5 38 passed, no product bug found. Decisions taken while implementing, recorded because they were not in the package above: terminal markers (`BUDGET_EXCEEDED`, `RETRY_EXHAUSTED`) block regardless of epoch and are never waivable; review findings are listed but do not block APPROVE by themselves; truncated command output is recorded as exit -3 (FAIL); existing databases of the older layout are refused, not migrated; the README limit on event-chain truncation was rewritten (keyed anchor detects tail deletion, whole-database rollback is not detected). Not verified: POSIX permission bits and process-group kill (Windows host), a symlink made by a child command, mutation checks (NOT_RUN by operator decision). Next: commit, specialist reviewers on the exact committed head, fixes, then the operator's independent review.

## 2026-10-24 -- S1 remediation committed (3e27720); status report checkpoint

Remediation committed locally as 3e27720; four specialist reviewers (silent-failure-hunter, security-reviewer, reliability-reviewer, architect) launched on that exact head. The report-due rule fired, so a status report (RU and EN, change record 0018) was written as a checkpoint while the re-review runs; it states the re-review and the independent review are pending. Nothing is pushed.

## 2026-10-24 -- S1 re-review of 3e27720: four MODIFY, second remediation package decided

All four reviewers returned MODIFY; all four independently found the same MAJOR defect, which the coordinator confirmed by reading `tools/vst/gate.py:200-207`: the gate rejects every receipt whose `candidate_head` differs from the current head as a hard reason, including older attempts and `WORKER_LOST` markers (the store stamps markers with the newest receipt head or `base_head`), so a fix-and-retry on a new commit can never reach APPROVE; slice scenarios used one head everywhere. Decisions: (1) head and artifact-digest checks apply only to the deciding (latest) attempt of each slot, older attempts are history checked for signature, binding and chain links, supervisor markers are exempt from the head check and terminal markers are never dropped (architect option b, same treatment as older epochs); (2) `retry_cap` counts worker-attributed failures (FAIL, INCONCLUSIVE, WORKER_LOST), not fenced leases that wrote nothing, and the rule is documented; (3) budget row is seeded from the manifest `cost_cap`, `acquire_lease` and `append_receipt` refuse when spent >= cap or an exceeded event exists, and `charge` commits the BUDGET_EXCEEDED marker itself; (4) the event anchor is verified (MAC, count equals row count, head equals last hash) before every event append, no silent fallback, with a snapshot read for verification; (5) gate returns NO_GO when the worker, supervisor and operator keys are not pairwise distinct; (6) minor: remove `OPERATOR_ACTION` from caller event kinds, reject `extra_env` keys that shadow the allowlist or loader variables, validate artifact digest keys as repo-relative paths, NFKC plus printable check in `normalize_principal`, kill the process tree after a normal exit on Windows, record an event for a lease that wrote some receipts and then died; (7) documentation: align `reporting-analyst`, `sdlc-metrics`, `sprint-ceremonies`, `core/STATE.md` and the cutover trigger wording with the store authority; exit artifacts are recorded as Documentation receipts or marked deferred. Scenarios must include a retry across a head change and a WORKER_LOST marker at a head different from the base.

## 2026-10-24 -- S1 second remediation round implemented and retested

Implemented per the package above (change records 0019, 0020, 0021, 0022). Test agents ran their complete sets on the working tree over 5a749ee: E1+E2 813 passed; E3+E4 506 passed and 2 skipped; E5 52 passed (rerun after the last runner change). The tests found one real product defect (Windows post-exit descendant kill: `taskkill` on an exited pid); fixed with a Windows Job Object in `tools/vst/runner.py` (a larger change than the original package, decided because a best-effort `taskkill` cannot reach descendants once the root has exited). Contract choices pinned by tests and open to reversal: control and format characters in a principal are rejected before stripping (a trailing newline is an error, not trimmed); a stale-head receipt with an invalid signature is treated as invalid, not stale (a set of only such receipts gives MODIFY, not NO_GO); the rule `spent >= cap` refuses a worker that spends exactly its cap before its final receipts (revisit to a strict `>` if a review shows a real worker hitting it). Not verified: POSIX behaviour, Job Object nesting under a parent job, mutation checks (NOT_RUN by operator decision). Next: commit, third specialist review on the exact committed head, then the operator's independent review.

## 2026-10-24 -- S1 third review of f1956e2: four MODIFY, third remediation package decided

Four reviewers on f1956e2 returned MODIFY. Two findings were made independently by two or more reviewers and are accepted as MAJOR: (A) the budget boundary - `charge` allows `spent == cap` while `append_receipt` and `acquire_lease` refuse at `spent >= cap` (the coordinator confirmed the `>=` rule at `tools/vst/store.py:995`), so a worker that spends its whole cap cannot record its result and nothing is persisted; (B) the slot-chain bound `attempt <= retry_cap + 1` counts attempts of earlier epochs while the gate requires a current-epoch attempt per slot, so a takeover after a full PASS set can leave a slot unsatisfiable without any terminal marker. Decisions: (A) `append_receipt` refuses only when `spent > cap` or a BUDGET_EXCEEDED event or marker exists; `acquire_lease` keeps `spent >= cap` but commits the signed BUDGET_EXCEEDED marker before raising, as it does for RETRY_EXHAUSTED; (B) the slot-chain bound counts only attempts within the current epoch (attempt numbers stay globally consecutive); the same rule in `runner._prepare`; (C) `failed_attempts` counts every non-PASS worker result (FAIL, INCONCLUSIVE, NOT_RUN, BLOCKED) and RELEASED leases that wrote nothing; (D) `acquire_epoch` reaps expired leases before fencing, `heartbeat` refuses after a terminal marker or exceeded budget, the BUDGET_EXCEEDED event is written once; (E) `extra_env` becomes an allowlist (names `VST_[A-Z0-9_]+` only); the capture reader marks any exception as incomplete; a root that survives the kill gives exit -4; the process group is killed and pipes are closed in `finally`; thread-start failure cleans up; (F) the store checks the worker key differs from event_key and supervisor_key (kind 'key'), and `receipts_for_task` cross-checks the RECEIPT_APPENDED event shas against the rows (kind 'integrity') so a truncated tail is not silently fed to the gate; (G) `normalize_principal` also rejects Mn invisible characters, variation selectors and Lo filler characters; (H) documents: `CLAUDE.md`, `docs/SDLC_PROCESS.md`, `core/STATE.md` status, baseline BD-2 wording (labels, resolver). Deferred to S2 and recorded as such: an authenticated reviewer key (IndependentReview receipts are signed with the worker key, so reviewer independence is a self-asserted label and an APPROVE does not prove an independent review), plus the earlier S2 items. Retry cap in the store counting only worker-attributed outcomes stays as decided in the second round.

## 2026-10-24 -- S1 third remediation round implemented and retested

Implemented per decisions A-H above (change records 0023, 0024; code in `tools/vst/store.py`, `runner.py`, `slice.py`, `contracts.py`). Test agents ran their complete sets on the working tree over f1956e2: E1+E2 863 passed; E3+E4 593 passed and 2 skipped; E5 64 passed (19 slice scenarios). No product bug was found by the tests this round. One deliberate removal: the attempt bound in `runner._prepare` was dropped because attempt numbers are global across epochs; the store now enforces the per-epoch slot bound. Pinned contract edges: the error message of `normalize_principal` names the NFKC-normalized code point (U+3164 and U+FFA0 report as U+1160); other invisible characters outside the closed list (for example U+2800) are not rejected; heartbeat refusal for `spent > cap` is untestable through the public API because `charge` writes the marker instead of exceeding the cap. Not verified: POSIX behaviour, Job Object nesting under a parent job, naturally unkillable processes (failure injected by monkeypatch), mutation checks (NOT_RUN by operator decision). The module docstring of `store.py` was updated by the coordinator to the new rules (documentation only). Next: commit, fourth specialist check on the exact committed head, then the operator's independent review.

## 2026-10-24 -- S1 fourth check of 176a095: one regression fixed, review rounds stop here

Two reviewers (reliability with silent failures; security with architecture and documents) checked 176a095 for BLOCKER/MAJOR only. Both previous MAJORs (budget boundary, slot bound after takeover) and the `extra_env` finding are confirmed closed. One new MAJOR, confirmed by the coordinator at `tools/vst/store.py:1030`: the strict budget check made a task with `cost_cap` 0 unstartable (a terminal BUDGET_EXCEEDED marker on the first lease). Fix: the strict check requires `spent > 0`; tests replaced the test that pinned the old behaviour. Minor items fixed: README slot-bound rule, `normalize_principal` list (U+2800 added), BD-2 wording, `core/STATE.md` status. Focused tests after the fixes: E1+E2+E3+E5 files 1205 passed and 1 skipped (E4 unaffected by these fixes, last full run 593 with E3). Decision: review rounds on S1 stop here; the specialist reviewers have no open BLOCKER/MAJOR, and the next gate is the operator's independent review on an allowed model. Deferred to S2 (recorded): authenticated reviewer key, runner-derived candidate_head, signing-key isolation, whole-database rollback detection, POSIX and Job Object nesting verification.

## 2026-10-24 -- Independent review request added to the repository

The request text for the operator's independent review is stored as `docs/sdlc/INDEPENDENT_REVIEW_REQUEST_S1.md` (change record 0026) because the earlier copy lived in a temporary session folder. No code changed; the independent review itself, the push and the pull request remain operator-owned.

## 2026-10-24 -- Full project status report written

On the operator's request a detailed status report of the whole project was written (`reports/PROJECT_STATUS_FULL_2026-10-24`, change record 0027). Facts recorded there: no background agents are running; commit 45653fc (review request stored in the repository) was not made by this session and appears to come from a parallel session or the operator; process rule v4 item 7 (prepare next-sprint documentation while the current sprint is tested) was not done; `core/BACKLOG.md` (VST-007, VST-008) and `core/STATE.md` (the zero-cap fix wording) are stale and were deliberately not edited in this step because the operator asked for a report only. Next step is the operator's choice among the options listed in the report (independent review then push and PR is recommended).

## 2026-10-24 -- S1 independent review: MODIFY, store fixes decided

The independent review of S1 returned MODIFY with two MAJOR findings in `tools/vst/store.py`, found by a fresh reviewer and missed by four specialist rounds and the scenarios (`retry_across_head_change` had only two heads; `takeover_after_full_pass_set` used retry_cap 0 and cost below the cap). Decisions: (1) the per-epoch slot bound counts only non-PASS receipts of the slot in the current epoch (refuse at retry_cap + 1), so PASS re-attestation is never blocked; (2) the budget blocks only at spent > cap or an existing BUDGET_EXCEEDED event, the strict `spent >= cap` rule in `acquire_lease` is removed (this supersedes the earlier decision to keep `spent >= cap` there), `charge` keeps committing the marker when a charge would exceed the cap; (3) worker receipt ids with the reserved prefix `sup-` are rejected (kind 'validation'). Deferred to S2 and recorded (S2 plan section 9, backlog VST-025, VST-026): manifest-listed mandatory commands per slot checked by the gate (the test result parser is caller-supplied and the gate does not verify every allowed command ran), and the scope of a signed waiver (currently covers a latest-attempt FAIL and reviewer MODIFY or NO_GO; operator decides to restrict or to document in ADR_0001). `gate.py` is unchanged. Tests have not been run for this change; change record 0031.

## 2026-10-24 -- S0 and S1 closed locally; push and merge decision

Operator authorization of 2026-10-24 (finish S0 and S1 autonomously, push and merge allowed). State: S0 inventory documents written (`docs/sdlc/s0/`, change record 0028); S1 store fixes from the independent review re-tested (E1+E2+E3 1193 passed, E4 289 passed, E5 72 passed; 2 skips are platform limits). S2 plan, backlog and retrospective committed (records 0029, 0030, 0031). Decisions: (1) S0 and S1 ship in ONE pull request on branch `s1-control-plane-core`; (2) the operator's private global contract and the workspace `AGENTS.md` are not edited (model default drift is recorded in the S0 documents as an operator-owned item); (3) the GPT-PM gate is requested for the exact final head through PM Bridge; the first two attempts to create the project chat timed out on chatgpt.com (EXTERNAL, shared browser daemon), the third succeeded; if the gate cannot return, the closed specialist rounds, the fresh independent review and the green tests are the recorded evidence and the operator is told that the GPT-PM gate was not obtained.

## 2026-10-24 -- S0 and S1 approved by GPT-PM and merged

GPT-PM returned APPROVE for the exact head abc0d50 (request 50828a0d-f780-405b-b49c-30de58c5bd52; no new in-scope BLOCKER or MAJOR; deferred S2 items acknowledged; the reviewer ran no tests on the head). Branch `s1-control-plane-core` was pushed, pull request 1 opened and merged into `main` (d5cd7f5) on the operator's authorization of 2026-10-24. Evidence is recorded here and in change record 0032 after the merge because a new commit would have invalidated the approval. The first GPT-PM send failed without reaching the chat (PM Bridge daemon restarted while MCP servers reconnected, no receipt written) and was resent once.

## 2026-10-24 -- S0 and S1 closure report written

Closure report added (change record 0033). It states that the tests were run by agents on the working tree before the final commit and not re-run on the approved head, and lists the deferred S2 items and the open operator decisions (waiver scope, model-default drift).

## 2026-10-24 -- Autonomous continuation prompt for S2 to S5

Added `docs/sdlc/AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md` (change record 0034) on the operator's request. Decisions encoded in it: sprint names follow the baseline plan (S2 isolated worker sandbox) over the stale blueprint table; one pull request per sprint with a GPT-PM gate on the exact head; the sandbox provisioning step stays operator-only and independent work continues while it is pending; the prompt is committed in English as repository text.

## 2026-10-24 -- S2 execution resumed with operator-selected agent model

The operator explicitly selected `gpt-6-luna` for agents in this continuation. The agent platform rejected the requested `sonnet` alias with the exact error `Unknown model 'sonnet' for spawn_agent`; the available list omitted Sonnet and included `gpt-6-luna`. Two read-only S2 agents then ran on `gpt-6-luna`: `code-architect` (design review and interface design) and `code-explorer` (source map). This is a run-specific operator choice; it does not alter ADR-0001 or global configuration. Their review and map found the S2 entry criteria stale, confirmed S1 test evidence was not collected on the approved head, and identified missing trust-boundary, crash-recovery, parser, state-authority and sandbox-egress details. The S2 plan now records binding decisions before implementation.

Decisions: (1) use the hand-written worker only; no external candidate is authorized; (2) only `NOT_RUN`, `INCONCLUSIVE` and `BLOCKED` evidence may receive a named, scoped waiver; `FAIL`, `MODIFY` and `NO_GO` cannot be waived; (3) until a VST store is initialized for this repository, `docs/sdlc/STATE.md` records phase state, then becomes a generated read-only view of the store; (4) reviewer registry trust is rooted in the operator key, and its version/digest is bound by the manifest; (5) command execution, trusted runner and signer have separate OS/IPC boundaries; (6) anchor recovery may append only the single valid event immediately after the checkpoint and remains write-locked on every other mismatch; (7) mandatory parsers are selected from a trusted catalog by id/version/digest; (8) the positive sandbox probe uses only a sandbox-local loopback canary while external egress remains denied; (9) push/PR idempotency is supervisor-only and worker credentials do not permit those operations. Evidence: `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` sections 3-10 and `docs/sdlc/STATE.md`; no tests or code checks were run.

## 2026-10-24 -- S2 parser-pin test defect and fix

The functional-test agent's first focused run at code HEAD `b2b168e71000323443882988cd24af2cdbabf4df` reported 30 passed and 3 failed in v2 parser-pin rejection cases. Exact command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py`; the test working tree was dirty with newly authored files. `validate_task_manifest` accepted parser id/version/digest values absent from `TRUSTED_PARSER_CATALOG`. An `implementation-engineer` on `gpt-6-luna` low effort added fail-closed validation in `tools/vst/contracts.py`; its diff leaves the v1 branch unchanged. The fix has not yet been rerun by a test agent and is not runtime-verified.

## 2026-10-24 -- S2 test authority and S3 preparation

S2 test authors completed the focused contract, diff-gate, runner/lifecycle, store/anchor, and sandbox-probe modules. The suite includes public-gate receipt authority routing for five receipt/slot routes across six trust-root key kinds, wrong-key rejection, and pairwise key distinctness. The E2E agent's final collect-only on the completed authored files returned exit 0 with 126 IDs (55 functional and 71 E2E). No runtime test result is claimed by this entry. The S3 worker-pilot plan was also prepared while S2 verification proceeds. Source: `docs/changes/0038-s2-test-suite-and-s3-preparation.md`, the five `tests/vst/test_s2_*.py` files, and `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`.

## 2026-10-24 -- S2 collision test oracle and signer-route defect

On exact HEAD `d7d2e02de56d2388c6bba4160959a432e7f4a43d`, the contract/gate batch reported 5 failed and 33 passed; the failures were five reviewer-key collision assertions that expected `NO_GO`, although the gate returned non-approving `MODIFY` with its explicit reviewer-collision reason. The test agent corrected the oracle to require non-approval and the correct reason. Separately, the runner/lifecycle batch found a real product `NameError` on the valid v2 signer/TestRun route (`signer_key` was not passed to `_check_latest`); the fix is in `9d612c98b81fdf7b38c61eda235771b1f8011bc7`. Both corrected tests and product code await runtime rerun at a new committed exact head. Change record `docs/changes/0040-s2-correct-key-collision-test-oracle.md`.

## 2026-10-24 -- S2 provisioning guide and S4/S5 plans

Prepared an operator guide for the dedicated WSL2/VM boundary and full S4 QA/S5 AEVE sprint plans. The guide is not evidence of provisioning. S4's current API lane is the documented Python API; no network API is asserted. S5 analyzer identity, revision, license, transport and supported-rule catalog remain `UNKNOWN / NOT_VERIFIED` in this repository. A read-only code review found and the coordinator corrected S5's ambiguous provenance versioning (new v3 contract; v1/v2 immutable) and the guide's incomplete list of S2 trust roots. No tests, checks or host provisioning were performed. Sources: `docs/changes/0041-s2-provisioning-and-s4-s5-plans.md` and the four named documents.

## 2026-10-24 -- S2 TestRun signer-key wiring fix

The first committed-head runner/lifecycle batch on `d7d2e02de56d2388c6bba4160959a432e7f4a43d` exposed a `NameError` on the valid v2 TestRun route: `_check_latest` verified the diff-gate and runner attestation with `signer_key` but did not accept the variable, and its sole caller did not pass it. The helper now receives the optional signer key validated by `evaluate`; the signature checks remain inside the v2 receipt path, leaving v1 behavior unchanged. The E2E batch reported 44 passed, 1 failed, 5 skipped. Fix is not yet runtime-verified. Source: `tools/vst/gate.py`, `docs/changes/0039-s2-test-run-signature-authority-fix.md`, and `docs/sdlc/evidence/s2-e2e-platform-run.md` (historical runs only; does not contain the new committed-head batch).

## 2026-10-24 -- S2 anchor serialization and suffix recovery

The database review on code HEAD `d779d55ea0cbb5f391a1f028cbab0345cab7e155` found that one transaction can commit multiple event rows while the external anchor accepted only one-count successors, and that concurrent Store processes/read snapshots could be mistaken for anchor tampering. Source inspection confirmed both paths. The store now serializes anchored writes and authoritative reads with a cross-process sidecar lock; it verifies the complete event chain and resumes a missing anchor suffix only when the existing signed checkpoint is an exact prefix. Anchor-ahead, missing-for-nonempty, forked or malformed state remains locked. No tests/checks were run for this fix; required test-agent scenarios are recorded in change 0043. This supersedes the earlier one-event-only recovery rule in the S2 plan. Source: `docs/changes/0043-s2-external-anchor-concurrency-and-recovery.md`.

## 2026-10-24 -- S2 egress policy proof requires operator attestation

The reserved-address connection probe is only a smoke probe and cannot establish that outbound traffic is denied. Worker start now requires an operator-root-signed network-policy attestation bound to run ID, spec digest, and fresh nonce, with environment identity, policy/evidence digests, empty external allowlist, no-container-socket, and no-unapproved-host-path evidence. The supervisor verifies this independently of the runner's inventory signature. Container socket discovery spans system endpoints, numeric per-user runtime directories, and `/proc/net/unix`; incomplete enumeration fails closed. All six trust roots remain distinct, and the operator key is not exposed to the worker/analyzer. Implemented without tests/checks/runtime probing under task restriction; record 0044.

## 2026-10-24 -- S2 socket inventory metadata errors fail closed

Follow-up review of `tools/vst/preflight.py` found that `Path.exists()`/`os.path.exists()` could suppress permission errors and turn an inaccessible socket candidate into apparent absence. The inventory now uses `lstat`, refuses symlinked runtime roots/UID directories/engine directories, and clears its completeness flag on access or enumeration errors. The operator attestation contract is unchanged. No tests/checks were run; record 0045.

## 2026-10-24 -- S2 strict Windows process starts inside its Job Object

Reliability review found the strict runner's Popen-then-assign ordering allowed command code to spawn a descendant before Job Object membership. Strict Windows launches now use documented `CREATE_SUSPENDED`, assign the process to the configured kill-on-close Job Object, and resume the primary thread through documented Toolhelp/OpenThread/ResumeThread APIs. Any setup, assignment, discovery, or resume failure terminates/refuses the command; there is no unsuspended fallback in strict mode. Non-strict behavior remains compatible. Pinned Python 3.14 source inspection confirmed Popen accepts creation flags but closes its primary-thread handle, which is why the implementation uses documented OS APIs instead of CPython private handles. No tests/checks or Windows runtime proof were performed; change record 0046.

## 2026-10-24 -- S2 supervisor state is derived from durable control events

Reliability MAJORs on code HEAD `e67b9ac0c09b1c2dff334dd34d65d67d8c71bf3a`: Supervisor construction reset provider failure count and breaker state, and lifecycle callback intent/outcome existed only in memory. Decision: persist threshold/policy, stable-ID provider outcomes, override records, and lifecycle intent/completion/unknown/reconciliation as reserved typed payloads inside the existing hash-chained `NOTE` event stream; avoid a schema migration. Replay verified controls before any action. A duplicate outcome ID is idempotent; a different breaker policy fails closed. An intent without a confirmed terminal outcome blocks lifecycle work after callback failure or restart. An explicit reconciliation record must include an evidence reference; completion advances state without effect replay, and confirmed non-completion permits only same-ID continuation. Generic caller events cannot emit the reserved marker. Implemented in change record 0047. No tests, builds, CI, migrations or runtime probes were run. A prohibited `git diff --cached --check` was accidentally invoked; it returned empty output and no exit code was provided, so it is not treated as passing. Designated test agents must establish behavior on the exact final head.

## 2026-10-24 -- S2 lifecycle intent admission is atomic

Follow-up reliability review found that separate Supervisor instances could hold stale `READY` state and both run callbacks after appending distinct intents. Decision: Store derives the current lifecycle state and unresolved actions under its serialized write transaction, verifies the event chain and external checkpoint, validates the requested predecessor state, and appends the intent before releasing the transaction. The rule covers start, stop termination/cleanup, rollback effect/cleanup, and resume. Implemented in change record 0048. No tests/checks/builds/CI/migrations/runtime probes were run; the two-instance regression belongs to the E2E test agent.

## 2026-10-24 -- S2 atomic breaker, authenticated reconciliation and Windows anchor unlock

E2E diagnostics on HEAD `43d0a87f73ef94cbe5bc34aed04921bbe31cf716` found a valid manual override rejected by lifecycle admission and Windows anchored-store startup/anchor-sync races entering integrity lock. Reliability review additionally found breaker state was checked only from Supervisor memory and an unsigned `completed=False` resolution could authorize a non-idempotent retry. Decision: admit `manual_override` as a serialized supervisor action; check durable breaker state in the same Store transaction that admits `start`; require the operator signature over the exact resolution/action/attempt/outcome/evidence-digest record and reverify it during Store replay/admission. Source inspection traced the Windows failure to unlocking the anchor-file byte range at EOF after append; unlock now seeks to byte zero. `Store` preserves the original startup reconciliation error for diagnosis. Implemented in change record 0049. No tests/checks/builds/CI/migrations/runtime probes were run; reruns belong to the E2E test agent.

The E2E agent reran the focused suite on HEAD `8df8db70649f3f45e75f34c9f717b060d292497b` and reported 75 passed, 2 failed, 21 skipped; both failures were Windows external-anchor `Permission denied` during genesis/concurrent writer activity. The offset correction in 0049 did not resolve it. Decision: serialize every public `FileExternalAnchor.compare_and_append()` through the existing cross-process sidecar coordinator lock and remove the second byte lock on the JSONL file. Skip POSIX-mode chmod calls on Windows. Normalize sidecar lock acquisition errors and close the SQLite handle when constructor setup cannot acquire the coordinator. Implemented in change record 0050. No verification was run for this change; E2E rerun is required.

Reliability re-review on `bf58c1b` found parent-directory creation and sidecar initialization writes/flushes were outside the OSError normalization boundary, potentially bypassing Store constructor cleanup. Decision: cover all coordinator setup operations through lock acquisition with one `AnchorError` boundary; let `finally` close any opened stream and release the local path mutex. Store constructor closes SQLite for this typed startup failure. Implemented in change record 0051. No tests/checks/builds/CI/migrations/runtime probes were run.

Two independent reliability reviews on `8eed294` found coordinator teardown could skip file close and local mutex release if OS unlock or close raised. Decision: attempt unlock, close and mutex release in nested cleanup; normalize unlock/close OSError only when no protected-operation exception is already active. Implemented in change record 0052. No tests/checks/builds/CI/migrations/runtime probes were run.

WSL diagnostic evidence on HEAD `c470542dbedf992b785804e421b1ff52e142003c` showed preflight automount detection treated all `/mnt/` targets as Windows drives, causing `/mnt/wslg` to fail a valid no-drive configuration. Decision: classify mounts with Windows drive-root sources as Windows drives only when their filesystem is `drvfs` or WSL `9p` marked `aname=drvfs`, record them explicitly, and add `/mnt/wslg` versus `/mnt/c` to the S2 acceptance contract. Implemented in change record 0053. No tests/checks or signed WSL probes were run; the E2E agent owns regression testing.

Security review on HEAD `19fb0088e2d4b237de6f0c7beb7aab2c648b66aa` found manual provider override accepted an unauthenticated operator record. Follow-up identified replay risk across separate breaker pauses. Decision: require a distinct operator HMAC binding stable record ID, action, paused state, threshold-crossing event ID, breaker config event ID, non-APPROVE verdict, and lowercase evidence digest. Store verifies signature/current pause episode under atomic action admission before callback and rechecks at atomic breaker-clear append; stale duplicate override cannot clear a later episode. Implemented in change record 0054. No tests/checks/builds/CI/migrations/runtime probes were run; E2E owns unsigned, tampered, valid and stale-replay cases.

The focused functional run on source HEAD `280e2d0a613a0b70252c13ce7afe85f22734f7d1` passed contract/gate, mandatory parser pin, waiver-scope and diff-gate coverage. Added explicit gate-consumption cases for absent, stale-manifest, stale-head, failing and invalidly signed diff evidence under change record 0056. Result: 60 passed, 0 skipped, one pytest-asyncio deprecation warning; this is partial evidence and does not replace the final exact-head S2 rerun or POSIX reviewer-identity runtime proof.

Functional regressions for bounded idempotent backend operations and breaker replay were run on final code HEAD `c0e7e9ce15958b6c6de7811bcaf1020119ba169d`. The combined operation-recovery, runner-lifecycle, and store-lifecycle modules passed: 76 passed, 14 skipped, 1 warning. The first run on `14bd1e85459d97c9caa90a62b117a41020200b9a` exposed a pending-operation verification defect, fixed in change 0067; an intermediate run also exposed E2E-fixture and synthetic source-repository issues, fixed before the final run. The 14 platform/prohibited scenarios remain NOT_RUN; see change 0070 and evidence `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md`.

## 2026-10-24 -- S2 final E5 inventory attested under delegated autonomous task

The final reserved correlation `s2-280e2d0a613a0b70252c13ce7afe85f22734f7d1-e5-final-0681fa0a871c4e40a2746c5c1c1d2eb4` / nonce `8024493e38ba44df96ee5f127a24b338` / spec digest `7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997` was collected and signed once. The runner's `collect_inventory` and `sign_inventory_with_service` calls ran in the verified scoped WSL unit. The result was PASS; all seven checked properties were true; socket enumeration was complete with zero paths; Windows-drive source count was zero. The primary coordinator verified `verify_fresh_probe` and `verify_network_policy_attestation` as true. Codex performed the host-mount review and used operator-root signing authority under the user's delegated autonomous WSL task; no independent human approval is claimed. The raw signed inventory remains root-only in the named WSL distro and is not committed. The exact public attestation and sanitized evidence are in `docs/sdlc/evidence/s2-e5-operator-attestation.json` and `docs/sdlc/evidence/s2-e5-runmanifest-wsl-280e2d0.md`; change record 0063.

## 2026-10-24 -- S2 acceptance state reconciled to committed evidence

Updated the authoritative S2 phase state, backlog, control-plane schema limits, WSL provisioning guide, and blueprint sprint name from records 0056-0063 and the saved functional/E2E/runtime evidence. Statuses distinguish implemented code, focused test results, per-run WSL acceptance, `NOT_RUN` scenarios, and pending specialist/GPT-PM gates. E5 is accepted only for its exact recorded run; persistent production deployment is not claimed. Process-kill/kill-table scenarios, Windows Job Object nesting, and full E8 crash/resume remain open. The untracked `docs/sdlc/evidence/s2-functional-test-run.md` present before these changes was preserved and not incorporated. Documentation review and commit are recorded in change 0064.

## 2026-10-24 -- S2 idempotent backend operation remediation

Reliability review found that simulated push/pull-request callbacks were executed inside a Store write transaction, retaining the cross-process anchor lock, and that subprocess calls had no timeout. It also found completed manual-override retries did not compare the signed payload with the original durable intent. Decision: use a durable `PENDING` idempotency result in the existing operations table, commit intent before invoking the backend, bound each synthetic Git subprocess, complete the row in a later transaction, and retry only with the same key/payload against the backend's own durable idempotency binding. Keep receipt insertion on its atomic in-Store path. On completed manual override replay, compare canonical payload bytes and reject mismatch. Do not migrate schema or change receipt versions. Full design and verification plan: change record 0065.

Implemented in change record 0066. No runtime verification is claimed; designated test agents must exercise intent/pending/retry/completion, timeout and crash windows, lock release during callback, changed manual-override replay, and backward-compatible reads of prior completed operation rows.

The first designated-agent run against `14bd1e85459d97c9caa90a62b117a41020200b9a` exposed that anchor-history verification accepted only legacy `SUPERVISOR_OPERATION` rows. The new external-operation table intent therefore failed verification on the first anchored transaction and on restart retry. Change record 0067 updates the consistency check to match pending rows to append-only intent events and validates completion/unknown bindings and completion-result digests. Post-fix test rerun remains pending.

The next S2 E2E run found a separate E8 harness defect: the synthetic backend received only the target bare repository while candidate commits were held in the worker source repository. Decision: pass an explicit source repository to the trusted synthetic backend and perform bounded local Git pushes of exact candidate heads into the bare target for branch and pull-request refs. Preserve supervisor-only push authority and idempotency checks; do not add object-copy plumbing or any real remote. Design is recorded in change 0068.

Implemented in change record 0069. Initial E2E evidence and the post-fix source/test heads will remain distinct; no result from the initial failing run is upgraded to a pass.

Fresh security review of source head `c0e7e9ce15958b6c6de7811bcaf1020119ba169d` found the source-repository `git push` could execute a worker-controlled pre-push hook with runner identity and signer-socket access (S2 S7.2/VST-017, MAJOR). Decision: supersede the direct push design with bounded `pack-objects`/`index-pack` plus target-side guarded `update-ref`, avoiding push hooks and remote helpers. Full design is change record 0072; no new source code has been tested yet.

Implemented in change record 0073. A hostile source-hook regression and exact-head security re-review are pending; earlier green test results at `c0e7e9c` do not verify this change.

Source review before runtime verification found that target-side fast-forward ancestry was checked before importing a source-only candidate commit. Change record 0074 moves object import before ancestry validation; no runtime result is claimed for the superseded order.

After the hook-free source publication changes and the object-import ordering correction, the designated functional recovery module was rerun on HEAD `202e0680e8e1b4fb30dcbe9659bf550d06443d90`: 4 passed, 0 skipped, 1 pytest-asyncio deprecation warning. This confirms the Store-level intent, retry, legacy-result, and signed-override replay contracts only; the new pack-transfer security surface remains owned by the separate E2E suite. See change record 0075 and `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md`.

Following the cumulative pack-storage resource cap, the same isolated functional module passed on source HEAD `1ef3fee07d5743dc8e42c632e1dc3100601116a7`: 4 passed, 0 skipped, 1 pytest-asyncio deprecation warning. This remains Store-level evidence only; hook-free pack-transfer and resource-limit acceptance belongs to the E2E exact-head run. See change record 0078 and the recovery evidence file.

E2E verification on source HEAD `1ef3fee07d5743dc8e42c632e1dc3100601116a7` passed hook-free source pack transfer, pinned Git config/environment, source-only object transfer, branch/PR ref conflict handling, cumulative storage preflight, and safe PENDING/restart retry: the Windows runner/store modules reported 76 passed and 14 platform skips; the selected WSL2 `vst-runner` POSIX lock test reported 1 passed. Overflow cleanup and process-kill behavior remain `NOT_RUN`. Evidence and detailed test record: 0079.

On source HEAD `dc95915018b80f498d5cf775363712fb915fe04e`, the functional-owned `test_s2_operation_recovery.py` module passed 4 tests with no skips and one pytest-asyncio deprecation warning. This independently confirms only Store operation recovery and signed override replay; E2E publication/snapshot contracts remain in the separate E2E record. See change record 0085 and `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md`.

On source HEAD `ed531264d0344c67e948e126c420e60f5272226c`, the Windows lifecycle/store E2E run exposed three publication failures at the source object snapshot file-identity guard; this red result remains diagnostic history. After the Windows handle-identity fix at `dc95915018b80f498d5cf775363712fb915fe04e`, the exact focused Windows modules passed 80 tests, skipped 14, and emitted one deprecation warning; the selected WSL `vst-runner` POSIX lock test passed. Process-kill/kill-table and post-start overflow cleanup remain `NOT_RUN`. See change 0083 and `docs/sdlc/evidence/s2-e2e-bounded-snapshot-ed531.md`.

The E2E-owned lifecycle/store modules passed on source HEAD `c0e7e9ce15958b6c6de7811bcaf1020119ba169d`: 72 passed, 14 platform/prohibition skips, one pytest-asyncio deprecation warning. The callback regression verified an independent Store write during the backend callback; the bounded timeout regression verified durable PENDING, restart retry, same-key backend idempotency, and conflicting payload rejection. Evidence and detailed test change record: 0071. The real-child timeout termination path and four E4 process-containment scenarios remain `NOT_RUN` under the process-kill prohibition/platform dependency.

2026-10-25 — S3's in-repository pilot uses Store-owned exact-payload idempotency for budget charge, stop fencing, and epoch acquire/resume. The handwritten effect uses a stable commit marker so an application-level returned checkpoint can replay the same synthetic change. Probe signatures are verified before a resume epoch mutation; the Supervisor remains responsible for one-time probe consumption. Worker output creates no acceptance receipts, and cleanup after timeout/STOP remains unverified. Implementation details are in change record 0088; functional/E2E verification is pending.
## 2026-10-25 -- Register S3 acceptance IDs and split readiness gates

Register S3 work under unique canonical backlog IDs VST-027 through VST-031, preserving existing unrelated VST-021 through VST-024 items. Split Definition of Ready by work boundary: contract and in-repository synthetic code preparation may proceed without acquiring or executing a candidate; candidate comparison remains gated on audit plus operator authorization; sandbox worker execution requires a fresh run-bound signed probe. This resolves the inconsistency found by the read-only S3 document review (GPT-6 Luna, low effort). Process correction: the coordinator inadvertently ran `git diff --check` before S3 code completion; its empty output/exit 0 is not verification evidence and is recorded as a FAILURE in `core/LESSONS_LOG.md`.

## 2026-10-25 -- Refresh BMad Loop public release pin

Updated VST-028 from the historical BMad Loop v0.10.0 reference to latest audited release v0.11.0, exact tag SHA `3e8f1e2ba7be39d99a3e88a00cd63c8cb2c7899d`. This metadata refresh does not transfer the v0.10 behavior review to v0.11, approve security/compatibility, or authorize acquisition. Complete the pinned source audit and retain the operator acquisition gate. See change record 0089.

## 2026-10-25 -- Add S3 focused adapter and pilot coverage

Added functional-owned and E2E-owned tests for the locally implementable S3 adapter contract, Store recovery, synthetic pilot scope, checkpoint resume, and STOP fencing. Reported runs are not yet accepted as exact-head evidence: the E2E rerun did not capture its precise checkout HEAD, so both files must be rerun after this test commit. Sandbox/WSL-boundary and OS process cleanup remain `NOT_RUN`. See change record 0090.

## 2026-10-25 -- Accept only exact-head S3 synthetic test evidence

The functional adapter tests reported 8 passed and synthetic pilot E2E reported 5 passed on exact HEAD `58088c804ee3d444919ec433b656c80ec3106f37`; each runner captured the same HEAD immediately before and after its command. This verifies only locally implemented synthetic paths. Sandbox probe/WSL boundary and OS cleanup remain `NOT_RUN`; see evidence `docs/sdlc/evidence/s3-focused-tests-58088.md` and change record 0092.

## 2026-10-25 -- Bind S4 QA reports through existing TestRun v2

Use validated VST task-manifest TestRun slots as the canonical category registry and require the trusted QA runner to produce an ordinary v2 `TestRun` receipt with the canonical QA report included among signed artifact digests. The exact-head gate and artifact resolver remain authoritative. Do not add fields to v1/v2 or repurpose S5's planned v3. The gate verifies receipt/artifact integrity; the runner/parser remains trusted to construct report content. See technical design and change record 0093.

## 2026-10-25 -- Use the observed named WSL runtime for S4 QA

The v2 signer runner is POSIX-only, and the approved named environment inventory reports Ubuntu-24.04, CPython 3.12.3, pytest 7.4.4, and runtime dependencies iniconfig 1.1.1, packaging 24.0, and pluggy 1.4.0. Pin that observed runtime and required dependency set; do not install packages or silently fall back to Windows. The static category inventory is `docs/qa/categories.json`; each tracked run-specific v2 task manifest must project its supported slots, exact IDs, and selectors. See S4 technical design and change record 0094.

## 2026-10-25 -- Keep QA event permissions private and disable ambient pytest plugins

The report-bound QA worker writes its bounded event record inside a runner-owned mode-0730 directory. Set only the event file to mode 0644 so the distinct runner identity can read it after worker exit; users outside the runner owner and worker group cannot traverse the parent. Set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` only for report-bound QA commands so installed entry-point plugins cannot alter a manifest-pinned run. Record and reconcile the source commits 217bd2b and a914213 without rewriting history; their change records exist, while this record and regenerated document registry are added in follow-up change 0096. No runtime verification is claimed.

## 2026-10-25 -- Reject QA category provenance outside candidate history

The category registry's top-level provenance head and every supported category source head must be ancestors of the candidate's current Git HEAD. Existence alone is insufficient because an unreachable or side-branch commit can name stale test IDs. A bounded `git merge-base --is-ancestor` refusal or timeout fails closed. The v2 receipt and authoritative gate still bind the run to its exact candidate HEAD. See change record 0097; no runtime verification is claimed.

## 2026-10-25 -- Bind seeded-failure observations to the committed fixture catalog

Seeded-failure fixtures live in a bounded tracked catalog with canonical input hashes, expected rejection codes, and one-to-one test IDs. The QA plugin records observed rejection codes only while the linked pytest node is executing. The report runner compares the complete observation set with the catalog and binds the catalog as a signed artifact; an absent or mismatched observation cannot yield a passing report. Keep the catalog `NOT_RUN` and empty until designated test owners supply real unchanged-product input records and tests. See change record 0098; no tests or runtime proof are claimed.

## 2026-10-25 -- Validate seeded-failure catalog at the report-bound runner boundary

The report-bound runner independently validates the catalog's exact root fields and coherent `NOT_RUN`/`SUPPORTED` state; it does not rely only on the higher-level CLI loader. Duplicate JSON object keys are rejected by both catalog loading paths. Before any category command starts, seeded-fixture test IDs must equal the complete required-ID set for that manifest slot. Exact pytest argv disables the cache provider, and report-bound child processes suppress `.pyc` writes so the worker respects the read-only source snapshot. See change record 0099; no runtime proof is claimed.

## 2026-10-25 -- Validate fixture metadata before direct-runner comparisons

Perform seeded fixture-to-manifest ID comparison only after report metadata has passed schema/type validation, so malformed direct calls yield `ContractError`. Enforce the same 16 KiB canonical input ceiling at the signing boundary as in the CLI loader. See change record 0100; no tests or runtime proof are claimed.

## 2026-10-25 -- Confine QA registry source selectors to tests

The final S4 code review found that checking a raw `tests/` prefix did not prove the resolved tracked source remained in repository `tests/`. Require canonical forward-slash paths, reject traversal/noncanonical spellings and symlink components, and resolve the AST source under the resolved tests directory. The code fix is in change 0137; functional regression and exact-head reruns are pending.

## 2026-10-25 -- Create the WSL run root with its inherited worker-group mode

The transfer at clean HEAD `3ba2f35b724da8f2ea5429d781710bbed6612af3` returned before metadata with `snapshot run directory did not receive mode 2710`. Source inspection found that post-creation `chmod` requested the SGID bit from an unprivileged runner outside the worker group; Linux may clear that bit. Set the process umask before creation, request mode 2710 in `mkdir` beneath the already validated SGID root, and verify the resulting mode without changing it afterward. The exact runtime cause is not independently observed. See change record 0121; fresh transfer remains required.

## 2026-10-25 -- Preserve bounded WSL receiver diagnostics on a broken pipe

A second transfer returned `Broken pipe` without a receiver reason or run metadata. On a bounded broken-pipe path, stop only the bundle producer, close receiver stdin, wait for the receiver to exit, and retain its capped stderr diagnostic after redacting the private snapshot root, runner account, and worker GID. Keep timeout handling fail-closed. Do not inspect or clean an unidentified partial destination. See change record 0118; the enhanced failure path needs one fresh exact-head transfer to verify.

## 2026-10-25 -- Preserve WSL snapshot group inheritance and set an explicit WSL working directory

The first bounded S4 transfer at `ea008c9ecfdf93dc689614ace957d6dfb7693627` returned no metadata: WSL reported `chdir(/nonexistent) failed`, then the receiver rejected the snapshot owner/group. Source review found that the receiver cleared setgid on the run root before Git cloned descendants; this is a plausible explanation, not a reproduced cause. Keep mode 2710 on the per-run root so newly created clone paths inherit the provisioned worker group, and use WSL `--cd /` so an unavailable runner home cannot prevent process startup. See change record 0116. A fresh transfer and permission probe are still required.

## 2026-10-25 -- Stream exact S4 source snapshots into the isolated WSL destination

Use a self-contained Git bundle over the Windows-to-WSL stdin boundary; do not depend on drive automount, host path mounts, network access, or an archive without Git provenance. Require a clean named branch, exact SHA equality after clone, sender/receiver bundle-digest equality, a pre-provisioned runner-owned mode-2710 root shared only for worker traversal, and a runner-owned, worker-readable/nonwritable clone. The transfer command does not provision the distro or signer and has not been executed. See change record 0101; source-transfer acceptance remains `NOT_RUN`.

## 2026-10-25 -- Verify corrected S4 native E2E on an identified read-only snapshot

At clean source HEAD `452c8ea8da5545bdce0f584a6b51662b93a33abf`, one bounded transfer returned run `e8b68c59c17a449eb2e30803021a37ae`, with exact HEAD, bundle digest and size. Run-scoped ownership/mode checks and worker read/write-denial checks passed. The corrected seven mapped E2E selectors passed under the read-only worker; a first invocation from `/` failed during plugin import before test collection and was rerun from the identified snapshot repository. Post-run status was empty at the exact same HEAD. Signer, report, receipt, gate and full sandbox acceptance remain `NOT_RUN`. See separate transfer/native evidence and change record 0134.

## 2026-10-25 -- Resolve registry test IDs against source definitions

Every supported QA registry test ID must resolve to a statically named pytest function or a method on a top-level `Test*` class in its tracked source file. A tracked file by itself does not prove that a declared node exists. Reject runtime-generated parametrized selectors until a deterministic source-level mapping is designed; do not import test modules or run collection from the registry trust boundary. See change record 0104; runtime regression acceptance is pending the designated test owner's rerun.

## 2026-10-25 -- Cache registry provenance queries per load

Resolve tracked-file, commit-existence, and ancestry facts once per unique path/revision while validating one registry. The initial real-registry run exposed a tracked-file false negative under repeated Git subprocess checks; this was consistent with the helper's bounded timeout collapsing to `False`, and the repository independently confirmed the file was tracked. Keep errors fail-closed, but avoid repeating the same query for each test ID. Pin category provenance to the S4 ancestor containing the committed node definitions. See change record 0111; final clean-head test rerun remains pending.

## 2026-10-25 -- Provision an S4-private snapshot destination in named WSL2

Following the operator's WSL2 selection, prepare a separate S4 snapshot root in the named `Ubuntu-24.04` distribution, owned by the non-root runner and worker group with mode 2710; keep the older protected S2 root untouched and do not publish private POSIX identity/path values. The observed distro configuration has automount and interop disabled and nftables input/output default-drop with loopback allowed, but this inventory is not a fresh signed probe or proof of resource limits. Source transfer and signer acceptance are still `NOT_RUN`. See change record 0114.


## 2026-10-25 -- Keep current-head Windows E2E separate from WSL acceptance

At clean S4 source HEAD `c5289cae2255b51e165ec8e65a322c752be0e99a`, the seven mapped S4/S3 selectors passed on the Windows host (7 passed, 0 failed, 0 skipped). This does not upgrade the earlier WSL transfer/native run at `452c8ea`. The current-head WSL transfer wrapper returned no correlated result to the test agent because its nested session handle was not retained; keep transfer and POSIX behavior `RESULT_NOT_CAPTURED` / `NOT_RUN` and do not inspect or retry an unidentified destination. See change 0141 and the current-head evidence file.

## 2026-10-25 -- Bound QA registry source parsing

The S4 code reviewer found that node resolution read tracked test files without a size ceiling and did not convert AST recursion failure into a closed refusal. Read at most 1 MiB plus one sentinel byte, reject oversized input before decoding, and return non-resolving for `RecursionError`. Preserve existing path confinement and do not parse source through imports or pytest collection. Implemented in change record 0142; focused regression is pending.

## 2026-10-25 -- Use one bounded Git query for QA provenance

The exact-head functional module at `64b8bb1` failed twice because a separate `git cat-file` helper returned false for valid source-head SHAs, while direct Git inspection later confirmed the objects existed. Keep syntactic lowercase-SHA validation, then use only bounded `git merge-base --is-ancestor` to prove both object presence and candidate-history membership. Report valid-but-missing/stale/out-of-history provenance as such; an operational timeout must not be mislabeled as malformed SHA. Retain the private existence helper only for test monkeypatch compatibility, not live validation. Implemented in change 0146; functional rerun remains pending.

## 2026-10-25 -- Verify ancestry-only QA provenance validation

At clean exact HEAD `56a58a72c337c7c712ce2efb72e99efc179552bd`, the focused registry module passed 15 cases with one Windows symlink-privilege skip and no failures. The committed-registry loader now accepts the valid provenance sources after removal of the duplicate Git existence query. A stale expected-message assertion was corrected in test-only change 0147 without weakening the negative provenance check. Symlink runtime remains `NOT_RUN` on this host. See change 0149 and evidence `docs/sdlc/evidence/s4-provenance-rerun-56a58a7.md`.

## 2026-10-25 -- Re-run the seven mapped S4 selectors at current HEAD

At clean `s4-native-qa-runner` HEAD `cbdce020fbd8030e7518285526831c2932f879a2`, the seven registered mapped selectors passed on the Windows host: 7 passed, 0 failed, 0 skipped. HEAD and worktree status were unchanged before and after. This result is Windows-only; the earlier WSL transfer remains `RESULT_NOT_CAPTURED`, and no WSL destination was inspected or retried. See change 0150.

## 2026-10-25 -- Bound aggregate QA registry source indexing

Fresh independent reviews at `e52ec7f63fa7285ad0bb3910e8bfd31a9707f31e` found that per-file caps and same-file AST caching did not bound many distinct source files or retained AST memory. Replace retained AST modules with compact node-name sets and enforce explicit per-load limits of 2,048 test IDs and 4 MiB aggregate source bytes, preserving the existing per-file cap and path checks. Implemented in change 0155; functional revalidation is pending.

## 2026-10-25 -- Cache QA test-source ASTs for one registry load

The fresh S4 security review at `2ffc8f7c59156d882f9d69729bc0337439e3705c` found candidate-controlled repeated parsing of one test source per registry ID. Cache each validated resolved source's AST (including closed failures) for the duration of one `load_registry` call, while repeating path/symlink/containment checks for each ID. This limits same-file parsing amplification without retaining cross-run state. Implemented in change 0151; designated functional regression and fresh security re-review remain pending.

## 2026-10-25 -- Retry intermittent read-only Git lookup timeouts once

Change 0152 records three focused-module runs that intermittently exceeded the five-second bound in `git rev-parse --verify HEAD` and, once, `git ls-files`; calls fail closed and direct lookup outside pytest succeeded. The evidence does not establish the underlying cause. Add one retry only for `TimeoutExpired`, retaining a five-second per-attempt limit and a ten-second maximum per lookup; second timeout, nonzero result, and OS error still fail closed. Implemented in change 0153; full module rerun pending.

## 2026-10-25 -- Verify registry source AST caching

The designated functional reviewer at code HEAD `93cd3c334c66683a379ca594215eaa3f5507bfd8` added two cases. The targeted AST-cache command passed 2/2. The full focused module returned 16 passed, 1 symlink skip, and 1 failure because the committed-registry integration case's bounded `git rev-parse --verify HEAD` timed out after five seconds; retain this as `NOT_PASS`, not green. See change 0152 and evidence `docs/sdlc/evidence/s4-ast-cache-functional-93cd3c3.md`.

## 2026-10-25 -- Re-run S4 registry tests after one bounded timeout retry

At clean exact code HEAD `08b82e07bceb1bd928a5a02ac6ee9479854caf16`, Python 3.14.3 / pytest 8.4.2, the focused registry module passed: 17 passed, 1 skipped, 0 failed. The skip is Windows symlink creation privilege (`WinError 1314`); POSIX symlink execution remains unverified. No Git timeout recurred. See change 0154 and evidence `docs/sdlc/evidence/s4-registry-module-retry-08b82e0.md`.

## 2026-10-25 -- Verify compact registry indexes and aggregate resource limits

At clean code HEAD `6903b7bf3e3dd4fc1281412c173fb82db9924d11`, the designated focused tests passed: 3 targeted cases; full registry module 19 passed, 1 Windows symlink skip, 0 failed. Tests prove one read/parse for three nodes in one source, explicit rejection after five controlled 900 KiB sources cross the 4 MiB aggregate budget, and rejection of 2,049 IDs before node resolution. See change 0156 and evidence `docs/sdlc/evidence/s4-registry-resource-budgets-6903b7b.md`.

## 2026-10-25 -- Verify mapped functional and integration categories at current HEAD

At clean exact HEAD `b741dc205a111e56bb984c59a63af2801870e4fc`, all eight currently mapped functional IDs passed and the single mapped integration ID passed on Windows. Each category ran separately under Python 3.14.3 / pytest 8.4.2. No skips or failures; one pytest-asyncio deprecation warning per command. See change 0160 and evidence `docs/sdlc/evidence/s4-functional-integration-mapped-views-b741dc2.md`.
## 2026-10-25 -- Re-run S4 mapped Windows selectors after registry source changes

At clean exact code/test HEAD `2dc6947e416b61103548285ec279d787c1027d8b`, the seven accepted mapped E2E selectors passed on Windows: 7 passed, 0 failed, 0 skipped, in 25.47 seconds with one pytest-asyncio deprecation warning. CPython was 3.14.3. HEAD and status were unchanged before and after. This does not exercise WSL/POSIX, signer, report, receipt, or authoritative gate behavior. The prior WSL transfer remains `RESULT_NOT_CAPTURED` and was not inspected or retried. See change 0157 and its evidence file.

## 2026-10-25 -- Verify current mapped functional and integration categories

At clean code HEAD `b741dc205a111e56bb984c59a63af2801870e4fc`, the designated functional test owner ran exactly the eight functional IDs and one integration ID in `docs/qa/categories.json`. Functional: 8 passed, 0 skipped/failures. Integration: 1 passed, 0 skipped/failures. Runtime was Windows, Python 3.14.3, pytest 8.4.2; each command emitted one pytest-asyncio deprecation warning. This is exact mapped-selector evidence, not full category breadth or the aggregate report-bound runner. See change 0160 and its evidence file.

## 2026-10-25 -- Reconcile S4 API-denominator commit 0170

Commit `c310b6098754036eacbe74ea09062cca929163f6` added five existing API selectors and retained `PARTIAL` coverage. Its change record is 0170. The commit omitted the required decision/lesson-log entries; this reconciliation preserves the commit and records its decision here rather than rewriting history.

## 2026-10-25 -- Reconcile S4 API-denominator commit 0171

Commit `f057020c62211b7787de368f300929b7a35b9838` replaced an API selector that duplicated the integration ID. The uniqueness validator correctly rejected the overlap. Its change record is 0171; the required contemporaneous log entries were omitted and are reconciled here.

## 2026-10-25 -- Reconcile S4 API evidence commit 0172

Commit `6300457964e35b80ff86e9edfb73ba9e8c68bb26` recorded the focused API/seeded result of 21 passed, 1 Windows symlink skip, and 0 failures at `f057020c62211b7787de368f300929b7a35b9838`. The change record is 0172; its required decision/lesson entries were omitted and are reconciled here.

## 2026-10-25 -- Reconcile S4 signature-selector commit 0173

Commit `7b1b0027cf07a33a8325017de08dd74c81fb0681` mapped a forged unsigned-receipt selector to cover the API signature-rejection path. Its change record is 0173; required log entries were omitted and are reconciled here.

## 2026-10-25 -- Reconcile S4 API evidence and inventory commit 0174/0175

Commit `b4f44f1f9c1e4a15ed9a7c30cb8ad699fced7d31` recorded evidence and the first finite Python API inventory (change records 0174 and 0175). It retained partial API coverage. The commit omitted the required decision/lesson entries; this single reconciliation entry covers both records in that commit.

## 2026-10-25 -- Reconcile S4 API entrypoint-test commit 0176

Commit `1a8d61aa3455b4e202a2d18b753063f362d85b24` added focused API falsifiers for previously unmapped entrypoints (change record 0176). Required decision/lesson entries were omitted and are reconciled here.

## 2026-10-25 -- Reconcile S4 complete API-mapping commit 0177

Commit `3df219e4b4cd1700e80b282c0d08fba8205006f5` mapped the 79-entry inventory to a unique API category and set its coverage mapping to complete (change record 0177). Runtime acceptance remained pending at that point. Required log entries were omitted and are reconciled here.

## 2026-10-25 -- Reconcile S4 API fixture correction commit 0178

Commit `d06e92b1d5460ee892754aa08916abb2179874e0` corrected a new test's live-owner precondition using the public epoch-release API (change record 0178). This was a test-fixture correction, not a product defect. Required log entries were omitted and are reconciled here.

## 2026-10-25 -- Reconcile S4 API provenance commit 0179

Commit `d00985f52e30342350a420f20ad96317be9227e1` updated API category provenance to the final test mapping (change record 0179). The exact mapped run followed at this code/test head. Required log entries were omitted and are reconciled here.

## 2026-10-25 -- Reconcile S4 API test-evidence commit 0180

Commit `bd0712674c3ba73702064300c0b343818124e766` recorded the exact API and seeded-failure run: 93 passed, 1 skipped, 0 failed, with the Windows symlink privilege limitation (change record 0180). Required log entries were omitted and are reconciled here; the run is not POSIX or signed report/gate evidence.

## 2026-10-25 -- Correlate a fresh S4 WSL snapshot and native run

Using a newly provisioned, unique snapshot root, a clean S4 source HEAD `56dce67e508ccf452b2b7b39ed7f33c863081269` transferred successfully as run `f3ad62c94bc0429987bc24277103d5b4` with exact bundle hash and size. The runner-side permission audit passed; the read-only worker ran seven mapped selectors with 7 passed, 0 skipped/failures and left the snapshot at the same HEAD with zero porcelain bytes. The earlier unknown transfer destination remains uninspected and unmodified. Evidence, S4 plan/backlog, and bilingual report updates are in change 0159. Signer/report/receipt/gate and broader category acceptance remain separate.

## 2026-10-25 -- Close S4 review findings and record partial sprint acceptance

Fresh S4 reviews found two resource risks in sequence: repeated same-file AST parsing, then aggregate CPU/memory use across distinct files. Changes 0151 and 0155 cache one compact node index per path and cap each source at 1 MiB, aggregate unique source bytes at 4 MiB, and IDs at 2,048. Change 0153 retries one transient timeout for tracked-file and candidate-HEAD lookups, bounded to 10 seconds per call and fail-closed afterward. Functional evidence 0156 passed 19 tests with one Windows symlink-privilege skip; mapped Windows E2E evidence 0157 passed seven selectors. Fresh code/security/reliability reviews at `2dc6947e416b61103548285ec279d787c1027d8b` found no open BLOCKER/MAJOR. Full WSL/signer/report/receipt/gate and complete category acceptance remain incomplete; see report change 0158.


### 2026-10-25 — S4 local acceptance lanes and seeded failure observations

For the test-owner follow-up, keep category IDs primary-unique and derive functional selectors from AC-7 without reusing API IDs. Integration selections may compose existing local store, runner/gate, and synthetic repository selectors; trusted signer socket/report runtime remains a separate `NOT_RUN` evidence state. Seeded fixtures are accepted only when their canonical input is loaded, unchanged product behavior is invoked, the exact rejection is asserted, and one current pytest node records the observation. See change records 0182 and 0183.


## 2026-10-25 -- Map S4 functional, integration, and seeded-failure denominators

The test-owner follow-up added six AC-7 functional selectors without reassigning any API-primary test ID, five local integration selectors to complement the existing signed runner path, and six unchanged-product AC-12 seeded fixtures with canonical input hashes and one exact node ID per fixture. The integration selector denominator is COMPLETE for six accepted local selectors. Trusted OS signer identity and report-bound runner runtime remain a separate NOT_RUN evidence state and do not reduce selector-mapping completeness. The seeded catalog's COMPLETE status is bounded to its seven declared fixtures and does not imply exhaustive failure coverage or a mutation score. Source code is unchanged. See change record 0183; runtime remains pending the mapped exact-head run.


## 2026-10-25 -- Correct S4 mapped-selector fixtures after exact-head run

The focused run at `126b67f3a969a067ac1643bebab2ac669a821eaa` produced 24 passed and 3 failed. Two failures were authored-test contract mismatches: the prior invalid-manifest seeded test narrowed the category list while the committed catalog now contains seven fixtures, and the stale-head seed used epoch 1 while its signed receipts were at epoch 2, causing an epoch rejection before the intended stale-head rejection. The third reported failure attempted a registry load for the out-of-scope fixture and reported E2E provenance outside candidate history; a direct ancestry check at the same HEAD found the recorded E2E source commit is an ancestor, so this transient discrepancy is retained for rerun rather than attributed to a product defect. The corrections use the committed category/catalog and align current epoch with signed fixture receipts. No product code changed. See change record 0184; exact rerun pending.


## 2026-10-25 -- Preserve S4 mapped-run NOT_PASS evidence

The 27-selector functional/integration/seeded run at `126b67f3a969a067ac1643bebab2ac669a821eaa` returned 24 passed and 3 failed in 82.62 seconds. Two test/catalog mismatches were corrected in commit `8b5178b`; the third failure is a registry E2E-source ancestry rejection conflicting with a direct `git merge-base --is-ancestor` exit 0. Its root cause is unverified. Per coordinator direction, do not rerun the affected denominator until implementation engineering investigates the bounded ancestry path. See change record 0185.

## 2026-10-25 -- Bound retry for registry ancestry provenance

The ancestry helper now uses the existing one-retry wrapper, with five seconds per attempt. This allows one transient `git merge-base --is-ancestor` timeout to recover while retaining fail-closed behavior after retry. The mapped-run discrepancy at `126b67f` is consistent with a transient timeout, but its root cause was not reproduced. See change 0186; exact-head test-owner rerun is required.


## 2026-10-25 -- Pass S4 mapped functional, integration, and seeded denominator

At candidate HEAD `97c39000331c96b0184b1fb18d9ac2ba65c5658d`, both targeted registry-ancestry regressions passed (2/2), then the complete mapped denominator passed (27/27: functional 14, integration 6, seeded-failure 7) on Windows PowerShell with Python 3.14.3. The prior E2E source ancestry rejection did not recur. This exact-head evidence does not cover API/E2E selectors or trusted signer/report/sandbox/POSIX runtime. See change record 0187.

## 2026-10-25 -- Bound local S4 E2E evidence to existing runner and gate fixtures

Add E2E-primary selectors for committed native pytest discovery and local `run_and_sign` → artifact resolver → authoritative gate journeys. The category remains partial until a selector exercises the separate `tools.qa.run` report serialization and v2 authenticated signer path. The local HMAC fixtures are not evidence of the deployed S4 signer, WSL source transfer, or sandbox runtime. See change record 0189; exact-head execution is pending.

## 2026-10-25 — Keep report-bound E2E gap visible after fixture selector mapping

Map the five selectors from change 0189 while keeping E2E and aggregate regression coverage PARTIAL: no selector drives tools.qa.run report serialization with v2 signed artifacts. Treat exact-head local selector execution, trusted signer deployment, WSL transfer, and sandbox runtime as separate evidence. Selector mapping completeness does not imply runtime PASS. See change 0190; selector execution is pending.

## 2026-10-25 — Record exact-head bounded local S4 E2E run

The five local E2E fixture selectors passed 5/5 at exact source HEAD 7d14e43d1e9568dddd5366ed979a187457c507b9 on Windows Python 3.14.3/pytest 8.4.2. This proves discovery and v1 local runner/gate artifact cases only; report-bound tools.qa.run/v2, trusted signer, POSIX transfer, and sandbox remain outside this run. See change 0191.


## 2026-10-25 -- Record S4 API and local category exact-head runs

At source HEAD `c8bb027cf3df93755b17f33b3ddfb129e837d124`, the 73-selector API category expanded to 93 pytest cases: 92 passed, one symlink case skipped because Windows returned WinError 1314, and zero failed. The separate 27-selector functional/integration/seeded run passed 27/27. Both used Windows NT 10.0.26300.0, Python 3.14.3 and pytest 8.4.2. E2E and trusted signer/report/sandbox runtime were not part of these runs. See change record 0192.

## 2026-10-25 — Record all mapped E2E selectors passing at exact S4 head

All twelve currently mapped E2E selectors passed together at exact source HEAD 47918f9c0a229b4dac0ea095763775eb20eb6755 on Windows Python 3.14.3/pytest 8.4.2. One pytest-asyncio deprecation warning was emitted. This is not POSIX/WSL, trusted signer, report-bound v2, or sandbox evidence; report-bound selector coverage remains partial. See change 0193.

## 2026-10-25 -- Reconcile S4 reports to recorded exact-head evidence

Refresh the bilingual S4 report, plan status, and VST-032–037 backlog against changes 0186–0193. Keep E2E coverage PARTIAL until a report-bound `tools.qa.run`/v2 selector exists; keep trusted signer, run-specific manifest, current-head WSL/POSIX sandbox, report/receipt/authoritative gate, and mutation/red-green states explicit and non-approving. The prior WSL run at `56dce67` is not current-head evidence. See change 0194.
