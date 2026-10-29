# Change 0335 — Record exact-head S2-M01 remediation evidence

## What changed

- Recorded the exact `f0bbac8` test rerun and independent security/code reviews for the ordinary-untracked DiffGate correction.
- Prepared a new complete S2 source diff and scope for GPT-PM re-review after the prior correlated MAJOR finding.
- Updated S2 state/backlog and generated the document registry.

## Why

GPT-PM found that `_diff_paths()` omitted ordinary non-ignored untracked files from the signed DiffGate inventory. Change 0334 fixes the collector. The corrected code must be tested and reviewed at one exact committed head, then returned to GPT-PM with the actual full S2 diff.

## Evidence and verification

- Prior correlated GPT-PM request `172f1abb-0023-48b8-ab8b-57b6b5b1f528`, reply `da8c2bb2-56f9-5c3b-923a-a0674163ba9c`, found MAJOR S2-M01.
- Corrected exact source/test HEAD: `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`.
- Designated `e2e-runner`: 5 new focused cases, 22 full DiffGate cases, 5 gate contract cases, and 7 runner provenance selectors all passed at exact HEAD.
- Fresh GPT-6 Luna medium-effort security and code reviewers at the same HEAD found no actionable issue.
- S2 diff patch: `docs/sdlc/evidence/s2-gptpm-source-diff-6117ba24-to-f0bbac8.patch`, SHA-256 `d139cdb80884bb7612bc7b2abbfa7d66cc58cb20b28914c73f5bd43a4dae6e5c`, 480,076 bytes. Scope: 24 S2 plan/spec, implementation/schema and S2 test paths.
- Exact commands, counts, durations, warnings and review evidence: `docs/sdlc/evidence/s2-diffgate-untracked-fix-tests-f0bbac8.md`.
- No source/test code changed in this evidence commit; no tests/checks/builds/migrations were run in this commit.

## Remaining acceptance and owners

- GPT-PM owns the corrected exact-head S2 gate decision; Codex owns safe submission/correlation.
- S2 remains NOT APPROVED until re-review and mandatory runtime/policy criteria are resolved. This record does not authorize prohibited process-kill/mutation scenarios or platform provisioning.
- Operator remains accountable for S2; Codex coordinates implementation/evidence; designated test/reviewer roles own their assigned work.
- No push, PR, or merge is authorized by this record.

Change: 0335  
Executor: Codex
