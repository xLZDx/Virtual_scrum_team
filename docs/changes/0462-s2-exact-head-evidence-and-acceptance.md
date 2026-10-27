# Change 0462: Reconcile S2 exact-head evidence and task acceptance

## What changed

- Add exact test and POSIX runtime evidence for code/test HEAD `4c1692d61ee04e945fc0ccdd44db71869ccd5468`.
- Preserve the exact S2 code/test delta from previously reviewed S2 baseline `f0bbac8` to code/test HEAD `4c1692d` as a review attachment.
- Record a task-by-task S2 acceptance matrix for VST-009 through VST-020 and S2.D1/D2, with the exact remaining `NOT_RUN`, unverified boundaries, dependencies, owners and next actions.
- Update the S2 backlog checkpoint, phase/repository state, decision log, lessons log, and schema known limits to distinguish synthetic fixture negatives from mutation testing and temporary timeout injection from process kill/crash behavior.
- Preserve the protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; it was not edited or staged.

## Why

The 0461 absolute-deadline change required current-head evidence. Earlier exact-head inventories also incorrectly grouped some temporary-fixture negative tests with prohibited mutation/crash/process-kill scenarios. Direct source/test audit showed the local Git timeout selector raises `TimeoutExpired` before child creation, and the selected anchor corruption tests touch only disposable temporary fixtures. Those permitted selectors were then run by the designated roles under the existing WSL boundary. Prohibited kill, crash/recovery, policy and mutation-testing scenarios remain `NOT_RUN`.

## Affected paths and contracts

- `docs/sdlc/evidence/s2-safe-functional-exact-4c1692d-20261027.md`
- `docs/sdlc/evidence/s2-specialist-review-4c1692d-20261027.md`
- `docs/sdlc/evidence/s2-task-acceptance-4c1692d-20261027.md`
- `docs/sdlc/evidence/s2-code-diff-f0bbac8-to-4c1692d.patch` (superseded by change 0463; current exact seven-file patch SHA-256 recorded there)
- `core/BACKLOG.md`, `core/STATE.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`
- `docs/sdlc/STATE.md`
- `tools/vst/schemas/README.md` (Known limits)
- `governance/DOCUMENT_REGISTRY.md` (generated)
- Contracts: S2 E1-E8 and S2.D1/D2 evidence authority, platform denominator, exact-head provenance, and truthful `NOT_RUN` handling.

## Verification state

- On code/test HEAD `4c1692d61ee04e945fc0ccdd44db71869ccd5468`, 178 focused Windows selectors passed. Of 209 IDs collected across six S2 modules, 8 additional POSIX E3 temporary-anchor selectors, the VST-011 capability-drop selector, and 2 POSIX identity-boundary selectors also passed; total 189/209 passed, 20 remain `NOT_RUN`.
- A separate bounded WSL E4.1 cross-UID descendant cleanup selector passed 1/1 outside the six-module denominator. Exact commands, Python/pytest versions, unit identities, archive SHA-256 values, profiles and limitations are retained in the evidence file.
- Architect, security, reliability and silent-failure reviewers assessed the 0461 code at exact code HEAD `4c1692d` using GPT-6 Luna, medium effort; none reported an actionable BLOCKER/MAJOR in their stated review scope. These findings are not sprint approval.
- No source changed during these test/review runs. No CI, build, mutation-testing, process-kill, crash/recovery, E8 bake-off, policy selector, push, PR or merge was run.
- Exact repository HEAD after this documentation commit will differ from the code/test HEAD above; documentation does not change the tested code. The exact-head GPT-PM gate is still required and is not implied by this record.

## Decision and ownership

- Decision: classify each candidate by actual effects. Synthetic malformed-anchor inputs are not mutation-testing runs; an injected timeout before process creation is not a process kill or crash. Do not broaden these determinations to interruption, cleanup, kill, system-mutation or E8 scenarios.
- Code/test source changes are already recorded in prior changes through 0461; this record changes documentation/evidence only.
- Test execution: designated `functional-test-reviewer` and `e2e-runner`; reviews: architect, security, reliability and silent-failure roles. Coordination, evidence and local Git: Codex. Exact-head sprint adjudication: GPT-PM. Any required operator signature or environment provisioning: operator.
- S2 remains NOT APPROVED. S3 work, push, PR and merge are excluded until all required acceptance and the exact-head approval are satisfied.
