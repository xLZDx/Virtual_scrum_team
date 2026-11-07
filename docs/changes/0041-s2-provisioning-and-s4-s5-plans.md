# 0041 S2 operator provisioning guide and S4/S5 sprint plans

## What

- Added `docs/S2_SANDBOX_PROVISIONING_GUIDE.md` with the operator-owned setup sequence and evidence checklist for a dedicated WSL2 distribution or VM.
- Added `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` for category-specific native QA runs, exact test-ID accounting, reproducible artifacts, and truthful `UNSUPPORTED`/`NOT_RUN` states.
- Added `docs/S5_AEVE_GATE_PLAN_2026-10-24.md` for bounded, exact-head AEVE evidence, explicit supported/unsupported rule coverage, provenance and stale-head rejection.
- Reconciled findings from one read-only document review: S5 now specifies a new v3 contract while preserving v1/v2 signed bodies, and the sandbox guide enumerates all six distinct S2 trust roots and separates the runner OS identity from the signer key.

## Why

S2 platform acceptance requires host provisioning that only the operator may perform. S4 and S5 are part of the authorized S2–S5 continuation and their plans are prepared before their implementation sprints. The S5 source identity and runtime are not established in this repository, so the plan records them as unknown rather than claiming integration availability.

## Affected contracts and paths

- S2 E5 operator provisioning; no host setup or probe was performed by this change.
- S4 QA category accounting, native test execution, dependency pinning, regression denominator and evidence artifact requirements.
- S5 bounded static-analysis evidence, independent provenance, supported/unsupported rule status, and exact-head VST gate behavior.
- Planning only: no product source or test file changed.

## Decisions

- The sandbox remains unaccepted until the operator provisions the environment and provides a real signed, fresh, run-bound probe inventory. Synthetic evidence cannot substitute.
- S4 treats the Python API as the existing API surface. A network/API lane remains `UNSUPPORTED` unless a transport route exists and is evidenced.
- S5 does not inspect or execute a neighboring AEVE checkout. Analyzer identity, source revision, license, transport and supported-rule inventory remain `UNKNOWN / NOT_VERIFIED` until supplied by an authorized in-scope source.
- New S5 provenance must use an explicit v3 manifest/receipt contract with a distinct signature domain; v1 and v2 bodies, hashes and validators remain unchanged.
- Test authorship/execution remains restricted to `functional-test-reviewer` and `e2e-runner`; the plans do not authorize tests during coding.

## Review and verification state

- A `code-reviewer` on `gpt-6-luna` medium reviewed the four planning/provisioning documents. It reported one MAJOR ambiguity in the S5 receipt versioning and one MINOR omission of supervisor/signer roots in the provisioning guide. Both were corrected in the documents before this commit.
- No tests, checks, builds, CI, migrations, sandbox provisioning or probe execution were performed for this documentation commit.
- S4 and S5 are `PREPARED / NOT STARTED`; this record does not claim their implementation or acceptance.

## Ownership and next action

- Accountable continuation owner: operator. Codex coordinates and authors these repository documents. Actual host sandbox provisioning belongs to the operator; no canonical technical provisioning service owner is identified.
- Next: finish S2 runtime testing/review and record the real sandbox dependency as `NOT_RUN` until the operator completes the guide's steps; begin S3 only after its entry criteria are met, then reconcile S4/S5 plans at their sprint starts.

Agent-Attribution: planner, code-architect, code-reviewer (gpt-6-luna); Codex executor
