# 0181 — Reconcile missing S4 API-batch governance entries

## What changed

Added decision-log entries for each of the ten S4 commits covering change records 0170–0180, plus one failure lesson describing the missing governance layer and the corrective rule. The commits all have linked change records, but the range audit showed that none included the required contemporaneous entries in `core/DECISION_LOG.md` and `core/LESSONS_LOG.md`; their commit messages also lacked an attribution footer. This reconciliation records the facts without rewriting history.

## Why

The project workflow requires every commit to include its own change record, decision-log entry, and lesson-log entry. The recent API denominator batch included its per-commit change records but omitted both canonical logs. The gap was detected after the commits, so an append-only correction is the safe audit action.

## Affected contracts and commits

This reconciliation covers ten commits and eleven numbered change records:

| Commit | Change record(s) | Scope |
|---|---|---|
| `c310b6098754036eacbe74ea09062cca929163f6` | 0170 | Add representative API selectors |
| `f057020c62211b7787de368f300929b7a35b9838` | 0171 | Remove a duplicate primary-category selector |
| `6300457964e35b80ff86e9edfb73ba9e8c68bb26` | 0172 | Record focused API/seeded evidence |
| `7b1b0027cf07a33a8325017de08dd74c81fb0681` | 0173 | Map signature rejection selector |
| `b4f44f1f9c1e4a15ed9a7c30cb8ad699fced7d31` | 0174, 0175 | Record test evidence and API inventory |
| `1a8d61aa3455b4e202a2d18b753063f362d85b24` | 0176 | Add API entrypoint falsifiers |
| `3df219e4b4cd1700e80b282c0d08fba8205006f5` | 0177 | Map the complete API callable inventory |
| `d06e92b1d5460ee892754aa08916abb2179874e0` | 0178 | Correct test fixture epoch precondition |
| `d00985f52e30342350a420f20ad96317be9227e1` | 0179 | Bind category provenance to final selectors |
| `bd0712674c3ba73702064300c0b343818124e766` | 0180 | Record exact API and seeded run result |

## Decision and lesson

The historical commits are preserved. This commit records one decision entry for each commit and one explicit `FAILURE` lesson with the root cause, missed/catching layers, and the rule for future commits. Future work must stage the change record and both logs before commit and include the required attribution footer.

## Verification state

The reconciliation is based on `git log --name-only` for the range from `11cdba225a7eaa4a9c89c16cd990b74a5bda4a47` through `bd0712674c3ba73702064300c0b343818124e766`, which showed the missing log paths for all ten commits. Their exact change records and commit messages were inspected. No tests or product checks were run for this documentation-only correction. `governance/DOCUMENT_REGISTRY.md` is regenerated in this commit.
