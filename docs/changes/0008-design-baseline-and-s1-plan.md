# Change record 0008: design baseline 1.0 and S1 implementation plan

## What changed
- New `docs/DESIGN_BASELINE_AND_IMPLEMENTATION_PLAN_2026-10-24.md`: binding decisions in force, baseline decisions BD-1..BD-7 (SQLite state authority, HMAC runner-signed receipts, typed closed-enum receipts, pure gate verdict function, append-only attempts, store-enforced limits, public-repository hygiene) and the six-epic S1 plan.
- Blueprint: GitHub URLs of four private repositories withheld; one risk-posture phrase generalised.
- `docs/INDEX.md`: row for the baseline.

## Why
The operator instructed on 2026-10-24 to assemble the final design and implementation plan, commit, push and start development. The review findings are converted into S1 work items rather than declared closed.

## Affected contracts and paths
Documentation only. No agent, skill, hook or policy changed. `sdlc-orchestrator/SKILL.md` step 1 will change in S1 epic E6.

## Verification state
No tests run; documentation only. Not independently reviewed. Private-repository visibility was checked with `gh repo view` (four private, four public). The push of this and the three earlier local commits was ordered by the operator without a prior final independent review; that is recorded in the decision log.
