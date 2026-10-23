# Change record 0005: record corrections after the Round 3 verification

## What changed
- `core/STATE.md`: updated date; added the design status (MODIFY DESIGN, nothing implemented, open operator decisions); corrected the remote section, which wrongly said nothing had been pushed (`origin/main` is at `d4aefb5`); recorded that the first public commit contains a local absolute path and that history stays unrewritten by operator decision.
- Correction to change record 0004 (that file is append-only and stays unchanged): its sentence "the operator asked ... for the confirmed findings to be fixed and committed locally" is inaccurate. The operator asked for the review only; the follow-up question "fix the documents and commit locally" was answered automatically with the recommended option by the question policy while the operator was silent (logged by that policy). The operator did not accept the design.
- `core/DECISION_LOG.md`: correction entry and the history decision. `core/LESSONS_LOG.md`: FAILURE entry for the inaccurate record and the stale STATE.md.
- `governance/DOCUMENT_REGISTRY.md` regenerated.

## Why
A Round 3 read-only verification of `da22d2a` found that `core/STATE.md` was stale and false about the remote, and that change record 0004 attributed an automatically accepted answer to the operator. The operator chose to keep git history as is and to correct the records in a separate local commit.

## Affected contracts and paths
Documentation and records only. No agent, skill, policy or design text changed.

## Verification state
Remote state checked with `git ls-remote origin`; history checked with `git log --all -S` and `git merge-base --is-ancestor 0a5821b d4aefb5`. The Round 3 review was a self-check by the authoring session on a model outside the reviewer allowlist, so it is not independent. No tests were run. Nothing was pushed.
