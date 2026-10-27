# Change 0386: reconcile continuation audit and process records

## What changed

- Updated `core/STATE.md` with the current 2026-10-27 S2–S5 portfolio state, verified `origin/main` baseline, and exact current-turn evidence limits.
- Added decision and lesson records for the S2 read-only system/firewall inventory and for the omission of required logs/registry refreshes from changes 0383–0385.
- Regenerated `governance/DOCUMENT_REGISTRY.md` after staging the Markdown records.

## Why

The original continuation instructions require current portfolio state, decision/lesson entries, and a generated registry. Re-reading the named original task attachment revealed the process requirements had not been followed by three preceding local documentation commits. This follow-up documents the shortcoming without rewriting local history.

## Affected paths

- `core/STATE.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Verified branch `s4-canonical-continuation`, baseline `199c35320026dced7f4acf9b85aa4cbee1cad145`, protected untracked file, and `origin/main` SHA `6117ba24b08a260b42402db6da0bf767864e1c04`.
- `origin/main` contains S0/S1 merge `d5cd7f5` and follow-ups `c5a8eb1`, `61412e2`; it is an ancestor of the working branch.
- Confirmed S4 named wheelhouse has six wheel files and WSL GCC is 13.3.0; did not install packages or run tests/builds.
- No source code, tests, branches, remotes, or other checkouts were changed or inspected.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was left untouched and unstaged.

## Decision

Do not rewrite the three earlier local commits. Preserve their original artifacts and record the procedural shortcoming; apply the full per-commit logging and registry sequence to all subsequent commits.
