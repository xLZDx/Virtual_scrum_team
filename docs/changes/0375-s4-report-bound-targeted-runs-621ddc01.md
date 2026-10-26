# Change 0375: Record exact-head S4 report-bound targeted runs

## What changed

Added the focused evidence record `docs/sdlc/evidence/s4-report-bound-targeted-621ddc01-20261026.md` and committed the generated QA report/stdout/stderr artifacts plus WSL setup provenance for the permitted Windows seeded-failure, WSL identity, and WSL seeded-failure runs.

## Why

Compiler and trusted offline wheelhouse prerequisites are provisioned. The S4 acceptance requires exact-head report-bound seeded failure and worker identity evidence before GPT-PM adjudication. A prior WSL helper was bound to an older candidate, so the previously authorized narrow helper was rotated using the immutable installer from the exact candidate. The old helper was preserved with setuid disabled.

## Verified outcomes

- Candidate HEAD: `621ddc01d1b5bbf701ccced7bb073c26e89c8c07`; registry SHA-256 `7b03dd4ac32b671a5e9a9a95a04c717dd6af2628dfda5d485d712788a4f2dd7a`.
- Windows AC-12 seeded-failure: 3/3 PASS, exit 0; report row SHA-256 `18ed4fa2f4f3c0e18de2310df2116a34772269568317817b76db013d5e9c8df1`.
- WSL AC-16 identity: 1/1 PASS, exit 0; row SHA-256 `dc34f2b945d211271165cdc2a37b9335d018351c3ea9f73b1afe3b53e29e7f89`.
- WSL AC-12 seeded-failure: 3/3 PASS, exit 0; row SHA-256 `ab911c4b1028506dec8e07f4cc85a8b743306b82e944dc813fa497ab5a1fff6e`.
- Each row binds the exact candidate and registry and verifies locked dependency contents before and after execution. WSL identity is UID/GID 997:988, empty supplementary groups, and no Windows drive mounts. `dependency_execution_integrity` remains `NOT_VERIFIED` for all rows.
- The separate Windows regression at code-identical candidate `bdc8e3be7d74ca20a380ecade6acd4e277e9c4dd` included `test_s4_runner_reports_post_execution_dependency_mutation` and passed it; this synthetic persistent-change check does not prove AC-17 same-identity change-and-restore during actual pytest execution.
- The 53 policy exclusions remain `NOT_RUN`. No policy selector was executed in these targeted runs.
- Exact commands, row/full-file hashes, target hashes, helper lifecycle, and relevant setup failures are in the evidence document. No source/test edits were made by these runs.

## Next action

Codex completes evidence/status reconciliation and requests actual specialist review on the exact final code head. GPT-PM then adjudicates the exact-head gate, including whether AC-17 execution integrity must be implemented or remains an explicit acceptance blocker. No push/PR/merge occurs without correlated approval for the exact code.

## Ownership

Accountable task owner: operator under delegated sprint work. Evidence coordination and local Git: Codex. Runtime execution: designated E2E runner. Exact-head gate: GPT-PM.
