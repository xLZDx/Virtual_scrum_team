# 0140 S4 exact-head registry path functional evidence

## What changed

- Recorded the exact clean-head functional run for the newly registered source-path regressions and the existing focused S4 registry module.
- Preserved both observations: initial bounded Git `HEAD` subprocess timeout and one successful same-head rerun.
- Recorded the Windows symlink-privilege skip, test-to-acceptance mapping, environment, command, revisions and limits in `docs/sdlc/evidence/s4-registry-path-functional-d5d2de8.md`.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Why

The source path confinement implementation and registered selectors need exact-head behavioral evidence. Retaining the transient first-run failure alongside the successful repeat avoids presenting the pass as the only observed result.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-registry-path-functional-d5d2de8.md`: durable execution evidence.
- `core/DECISION_LOG.md`: dated acceptance evidence and platform limitation.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory.

## Verification state

- At exact clean run HEAD `d5d2de80a4abaa18166dd595cf268759064b0c53`, focused result after one same-head repeat: 13 passed, 1 skipped, 0 failed.
- The skip is exact and environmental: Windows WinError 1314 prevents creating symlinks without an unavailable privilege. Symlink behavior is therefore not runtime-proven on this host.
- First invocation at the same HEAD had 12 passed, 1 skipped, 1 failure from a 5-second Git subprocess timeout in `_current_candidate_head`; the repeat passed without code changes.

## Decisions and ownership

- Do not increase the subprocess timeout based on one transient observation. Keep the failure visible and rely on the successful single retry as current focused suite evidence.
- No registry product code was changed by the test owner. The technical owner for the registry trust boundary is not separately named in canonical ownership records.
- Accountable task owner: operator under delegated S4 work. Executor: Codex.

## Next steps

1. Treat canonical traversal/repeated-separator/backslash rejection as functionally verified at the recorded exact HEAD.
2. Keep symlink path behavior `NOT_RUN` on this Windows host; exercise it in the existing POSIX/WSL acceptance lane when that lane is available.
3. Continue independent S4 acceptance gates; this record does not claim signer, report, gate or full sandbox acceptance.
