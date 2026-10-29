# Change 0465: Record exact-head S2 restart-fence evidence

## What changed

- Record the exact `a6ea0dc` safe Windows and bounded WSL test results, runtime-directory state, cross-process lock observation, empty stale-scope fixture, archive/file hashes, command profiles and limitations.
- Add a refreshed S2 task-by-task acceptance matrix and reconcile `core/STATE.md`, `core/BACKLOG.md`, `docs/sdlc/STATE.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, the schema README and generated document registry.
- Record four fresh exact-head specialist reviews and preserve the outstanding deployment finding rather than calling S2 accepted.

## Why

Change 0464 fixed a code-level restart-latch gap. Evidence at the exact resulting source/test head is required to distinguish the implemented lock/reconciliation behavior from persistent service acceptance. The bounded WSL unit proved real `flock` serialization and only an empty stale-scope cleanup; it did not simulate a runner crash or contain a populated orphan.

## Affected contracts and paths

- `docs/sdlc/evidence/s2-restart-fence-exact-a6ea0dc-20261027.md`
- `docs/sdlc/evidence/s2-task-acceptance-a6ea0dc-20261027.md`
- `docs/sdlc/evidence/s2-code-diff-f0bbac8-to-a6ea0dc.patch`
- `docs/sdlc/evidence/s2-gptpm-final-review-scope-a6ea0dc.md`
- `tools/vst/schemas/README.md`
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/STATE.md`
- `docs/sdlc/STATE.md`, `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Exact code/test commit assessed: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`.
- Designated agents passed 188 safe Windows and 11 safe WSL selector IDs. Four fresh GPT-6 Luna medium-effort specialists reviewed the exact restart-fence diff. Full exact commands, runtime profile, review outcomes, hashes and limitations are in the evidence file.
- The new docs/state/registry commit itself has no source or test changes; no tests/checks/build/CI/migration were run for this documentation update.
- Twenty restricted or unavailable selectors remain `NOT_RUN`. No populated stale cgroup, live process kill, runner crash/recovery, mutation, E8, or policy selector was run.
- GPT-PM exact-head adjudication is pending. Reliability review retains a MAJOR deployment condition: no persistent runner service configuration/stable delegated-parent replacement evidence is available in the repository or this bounded runtime record. Fresh signed E5 inventory, Windows ACL/nested Job Object runtime, and operator waiver status also remain incomplete.

## Decision and ownership

- Decision: keep S2 `NOT APPROVED`; do not infer persistent deployment, populated-scope crash recovery, or waiver from the bounded evidence.
- Evidence/doc/local Git reconciliation: Codex. Test execution: functional-test-reviewer and e2e-runner. Stable persistent service/subtree provisioning and any operator signature/waiver: operator. Final adjudication: GPT-PM.
- No S3 source work, push, PR, or merge is authorized by this record. Exact GPT-PM approval on the final code does not waive any missing platform or signed evidence.
