# Change 0451: record exhausted safe S2 selector denominator

## What changed

- Added the `e2e-runner` read-only audit showing no further non-duplicative S2 selector can run under the active restrictions.
- Updated S2 phase state and backlog to distinguish five unique regression selectors from seven executions across exact source/test heads `dc1741b` and `79155fd`.

## Why

After the constructor test and two reader-failure reruns passed on corrected code, the remaining allowed local test opportunities needed a current-denominator audit. The audit confirms no safe selector remains without repeating already accepted evidence.

## Affected paths

- `docs/sdlc/evidence/s2-safe-selector-denominator-20261027.md`
- `core/BACKLOG.md`
- `docs/sdlc/STATE.md`
- `docs/changes/0451-record-s2-safe-selector-denominator.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and verification

- Audit target repository HEAD: `2954c3f`; exact current source/test head: `79155fdf9f1f4a7ba71358592ccd54c669a76291`.
- Audit was read-only; no tests or checks were run. It found no additional permitted, non-duplicative selector.
- Five unique new regressions have seven executions across two exact heads: four at `dc1741b`, three at `79155fd`. Exact run evidence is linked in the denominator audit.
- Remaining real process, crash, mutation and timeout selectors remain `NOT_RUN`; system-level acceptance remains open. Phase 8 is NOT APPROVED.

## Ordered next steps and owners

1. Operator: decide whether to maintain restrictions or provide a scoped authorization/waiver path for real process-boundary scenarios; if maintained, those scenarios stay `NOT_RUN` and S2 cannot close on evidence alone.
2. Operator: provide/attest the real environment needed for Windows Job Object, persistent deployment, workspace/direct-writer, resource enforcement and full egress acceptance.
3. Codex: collect the named system evidence only within the authorized boundary and keep records tied to exact heads.
4. GPT-PM: adjudicate the final exact S2 submission after the required denominator is satisfied or valid waivers are provided.

## Attribution

Change: 0451
Executor: Codex; audit by `e2e-runner`
