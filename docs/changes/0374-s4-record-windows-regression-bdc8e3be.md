# Change 0374: Record S4 Windows regression at exact candidate bdc8e3b

## What changed

Added `docs/sdlc/evidence/s4-windows-regression-report-bound-bdc8e3be-20261026.md` with exact candidate, registry, command, selector accounting, target provenance, report artifacts, and outcome limitations.

## Why

The fixture-contract and policy updates needed a fresh exact-head report-bound regression before S4 status could be updated. The previous wide run reported failures and one timeout selector was not explicitly excluded; this run validates the corrected selector policy and reconciles the five prior S2 lifecycle results.

## Evidence and outcome

- Candidate HEAD: `bdc8e3be7d74ca20a380ecade6acd4e277e9c4dd`; registry SHA-256 `7b03dd4ac32b671a5e9a9a95a04c717dd6af2628dfda5d485d712788a4f2dd7a`.
- Report-bound run ID: `s4-regression-20261026-win-bdc8e3b-r1`; exact command and raw artifacts are linked in the evidence document and preserved under `D:\Temp\vst-s4-regression-evidence-20261026-bdc8e3b`.
- 897/897 expected Windows regression selector IDs passed; 1,845 concrete pytest nodes passed, 39 deselected, zero failed. All five previously failed S2 lifecycle selectors passed in this run; no flake classification is made.
- The 53 exact policy `NOT_RUN` rows matched the registry. The forbidden timeout cleanup selector was absent from both expected and executed IDs. The report row is `INCONCLUSIVE` solely because policy selectors remain `NOT_RUN`; the CLI exit is 1 despite report-row `exit_code=0`.
- Fresh target SHA-256 before and after: `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84`; no unexpected candidate source changes.

## Acceptance limit and next action

This is Windows regression evidence only. It does not close S4, prove AC-17 resistance to same-identity mutation-and-restore during pytest, provide WSL AC-16 identity evidence at this candidate, or approve release. The designated E2E runner must next run the permitted report-bound seeded-failure selectors and the allowed WSL identity check if the environment permits. Specialist review and exact-head GPT-PM adjudication remain pending.

## Ownership

Accountable task owner: operator under delegated sprint work. Evidence coordination and local Git: Codex. Test execution: designated E2E runner. Exact-head gate: GPT-PM.
