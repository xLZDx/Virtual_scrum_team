# Change 0449: rerun bounded-Git reader cleanup regressions on current source

## What changed

- Added exact-head evidence for rerunning the reader-start and pipe-read failure selectors after the bounded-Git cleanup correction in `f95ceb1`.
- Updated S2 backlog and phase state to distinguish four earlier selectors at `dc1741b` from three current-head selectors at `79155fd`.

## Why

The source cleanup path changed after the two reader failure tests first passed. A current-head rerun was needed to show those synthetic failure paths still trigger child cleanup and pipe closure under the revised guard.

## Affected paths

- `docs/sdlc/evidence/s2-vst017-reader-reruns-79155fd-20261027.md`
- `core/BACKLOG.md`
- `docs/sdlc/STATE.md`
- `docs/changes/0449-rerun-s2-bounded-git-reader-regressions.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and verification

- Exact source/test HEAD: `79155fdf9f1f4a7ba71358592ccd54c669a76291`.
- Two selectors, 2 passed, 0 failed, 0 skipped; invocation `609f49b815db436bb1b2c73c9551432d`.
- Both use a fake process. They do not execute real process-kill behavior.
- A first setup attempt exited before selectors with CHDIR permission denied; the successful retry used a fresh temporary archive and removed it afterward.
- The constructor-failure selector also passed at `79155fd`; the four earlier regressions are still scoped to `dc1741b`.
- No other selector was run. Restricted process-kill, crash/resume, mutation, timeout/restart and policy selectors remain `NOT_RUN`.

## Ordered next steps and owners

1. Codex: preserve the exact-head distinction and current S2 evidence.
2. Codex: continue only additional permitted S2 acceptance work; keep prohibited cases `NOT_RUN`.
3. Operator: owns any authorization/policy change for restricted live-process scenarios and real environment/deployment evidence.
4. GPT-PM: adjudicates the exact final S2 head after required system evidence is complete.

## Attribution

Change: 0449
Executor: Codex; tests run by `e2e-runner`
