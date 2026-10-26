# Change 0376: Reconcile S2–S5 state with current S4 evidence

## What changed

- Added the latest exact-head S4 regression and targeted report-bound outcomes to `core/STATE.md`.
- Updated backlog items VST-032, VST-036, VST-038, VST-040 and VST-041 with the current registry denominator, Windows/WSL seeded-failure runs, WSL identity result, AC-17 limit and S5 blockers.
- Added the current evidence and reviewer disposition to `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` without rewriting the earlier historical continuation entries.

## Why

The prior state described candidate `b3fb7bc`, treated WSL setup as blocked, and listed 52 policy rows. Current exact-head reports supersede those statuses: the allowed full Windows regression and targeted Windows/WSL S4 slices now have fresh evidence, and one timeout-cleanup selector was added to policy `NOT_RUN` to match the user's execution boundary. S2, S3, S5 and delivery gates remain open for independent reasons.

## Evidence reflected

- Current code/test policy source: `3885d8a143d4cfa95cd3f0c0e5c840a6ed72dfda`.
- Latest targeted runtime candidate: `621ddc01d1b5bbf701ccced7bb073c26e89c8c07`; registry SHA-256 `7b03dd4ac32b671a5e9a9a95a04c717dd6af2628dfda5d485d712788a4f2dd7a`.
- Windows regression at code-identical candidate `bdc8e3be7d74ca20a380ecade6acd4e277e9c4dd`: 897/897 expected selector IDs passed, 1,845 concrete nodes passed, 39 deselected, zero failed; non-approving `INCONCLUSIVE` because 53 policy selectors remain `NOT_RUN`. Five prior S2 failures passed; no flake claim is made.
- Current Windows seeded-failure 3/3, WSL seeded-failure 3/3, and WSL AC-16 identity 1/1 passed at exact candidate `621ddc01`.
- AC-17's specified before/after locked-content and persistent post-execution mutation checks have evidence. Same-identity change-and-restore during real pytest execution remains `NOT_VERIFIED` by design and evidence.
- Fresh code review of `dd50fa5..3885d8a`: no material finding (GPT-6 Luna, low). Fresh security review of helper/installer/dependency boundary: no reachable BLOCKER/MAJOR in authorized local-operator scope (GPT-6 Luna, medium).
- S2 Phase 8 is still NOT APPROVED; S3 acquisition/build/execution are still NOT APPROVED; S5 still depends on S2/S4 and in-scope AEVE provenance. Exact-head GPT-PM S4 gate and push/PR/merge remain pending.

## Verification

Documentation and ownership mappings were reconciled against the committed evidence and PM Bridge/project records. `git diff --check` passed. No tests or runtime selectors were run for this documentation update.

## Ownership and next action

Accountable task owner: operator under delegated S2–S5 work. State/backlog reconciliation and local Git: Codex. Next: attach the exact code diff, bound reports and specialist findings to a fresh GPT-PM adversarial sweep for the current exact repository HEAD; reconcile its verdict before any delivery action.
