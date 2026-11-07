# Change 0439: record exact-head S2 review regression results

## What changed

- Added exact-command E2E evidence for the four focused regressions on source/test HEAD `dc1741b`.
- Updated S2 backlog items VST-011, VST-012, and VST-017 and the canonical phase state to distinguish the newly passed code-level regressions from the still-open full S2 system gate.

## Why

The corrections in change 0436 cannot be accepted on source review alone. The designated E2E runner executed only their four new targeted selectors under the existing WSL runner identity/profile. The exact run, output, skipped-selector boundary, setup attempts, and environment need durable provenance.

## Affected paths

- `docs/sdlc/evidence/s2-review-regression-dc1741b-20261027.md`
- `core/BACKLOG.md`
- `docs/sdlc/STATE.md`
- `docs/changes/0439-record-s2-review-regression-results.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and acceptance

- Source/test HEAD: `dc1741bda127de5fc7af5544c984dd81cb4927aa`; source correction commit: `324f901`.
- `e2e-runner`, GPT-6 Luna, medium effort: 4 passed, 0 skipped, exit code 0 in WSL2 `Ubuntu-24.04`, UID/GID `vst-runner`, with ambient `CAP_SETUID`/`CAP_SETGID`. The capability regression observed all four capability sets empty and could not change to the signer UID. The anchor regression preserved a valid two-record JSONL chain. The two bounded-Git cleanup tests used a fake process.
- Exact command and WSL unit evidence: `docs/sdlc/evidence/s2-review-regression-dc1741b-20261027.md`; invocation ID `23d6730f34d94877849cd7bf177708a4`.
- Two pytest cache warnings resulted from the read-only archive path. A failed Windows command setup and an early-closed archive diagnostic launched no selectors; only the successful exact-archive command ran tests. The temporary archive was removed.
- No policy-excluded timeout/restart, process-kill, crash/resume, mutation, full suite, build, CI, or migration was run.
- Phase 8 remains `NOT APPROVED`; fresh exact-source specialist reviews and broader Windows/POSIX/system acceptance are still pending.

## Ordered next steps and owners

1. Codex: obtain fresh exact-source specialist re-reviews of the changes and focused evidence.
2. Operator: maintain or explicitly revise the policy for the remaining restricted selectors; current `NOT_RUN` results remain unchanged.
3. Codex: continue only permitted Windows/POSIX/system evidence collection and reconcile the remaining S2 denominator.
4. GPT-PM: review the exact final S2 head after the remaining evidence is ready; no push/PR before approval.

## Attribution

Change: 0439
Executor: Codex
