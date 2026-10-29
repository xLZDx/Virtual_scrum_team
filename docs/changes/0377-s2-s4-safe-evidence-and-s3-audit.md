# Change 0377: record safe S2 evidence, S4 reviews, and S3 pinned-source findings

## What changed

- Recorded current-head S2 safe Windows/WSL2 test results and the deliberate NOT_RUN denominator for prohibited child-process, process-cleanup, timeout, crash/resume, egress, and mutation scenarios.
- Recorded the S2 read-only code-gap audit; no new safe source fix was evidenced.
- Recorded fresh S4 code and security review results, preserving the AC-17 in-run integrity and 53 policy-selector limitations.
- Reconciled the S4 backlog/plan with the missing durable PM request state and current exact-candidate reports.
- Added primary-source S3 evidence for the narrow SDK/server compatibility fact and the current PyPI-attested SDK wheel publication; updated older `provenance=false` statements as historical observations superseded by current metadata.

## Why

The latest exact-candidate and current-head evidence had not yet been reconciled into durable acceptance records. The new S2 runs establish only bounded contracts and temporary-fixture behavior; the S4 reviews do not waive policy exclusions or replace GPT-PM's exact-head gate. A current PyPI page inspection changed the recorded state for SDK artifact provenance, but independent artifact verification still requires the separately gated acquisition step.

## Affected acceptance and paths

- S2 E1/E3/E6/E7 contract subsets: 74 Windows cases and 7 WSL2 cases passed at committed HEAD `6ca2ee00ef31ac621e7ff3231ac175646bbd3bb2`; the full 86-ID registry denominator was not exhausted. No code changed. E4 containment, child identity, E5 full host enforcement, timeout/cleanup, and E8 crash/resume remain `NOT_RUN` or `NOT_VERIFIED`.
- S4 source range `dd50fa5..3885d8a`: GPT-6 Luna code review (low) found no material finding; GPT-6 Luna security review (medium) found no reachable BLOCKER/MAJOR in its authorized local-operator scope. Runtime evidence remains tied to `bdc8e3b` and `621ddc01`; 53 policy selectors remain `NOT_RUN`, and AC-17 same-identity in-run change-and-restore remains `NOT_VERIFIED`.
- S3: official SDK 1.34.0 release notes support one specific behavior with Server >=1.32.0, satisfied by pinned Server 1.32.1. PyPI currently shows verified publication provenance for 8 SDK files, including Linux x86-64 wheel SHA-256 `540761f738bdfe5cb5bd7240b659e116a0b5094b94282aef09b8d8c2d66e9c52` linked to exact SDK source commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`. No artifact was downloaded or independently cryptographically verified. Server provenance, complete dependency closure, exact-version license/notice, full compatibility, and candidate runtime remain open.
- Updated `core/STATE.md`, `core/BACKLOG.md`, `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`, and `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`.
- Added `docs/sdlc/evidence/s2-safe-platform-subset-6ca2ee0-20261026.md`, `s2-safe-source-gap-audit-20261026.md`, `s4-specialist-reviews-3885d8a-20261026.md`, `s3-temporal-narrow-compatibility-audit-20261026.md`, and `s3-temporal-sdk-pypi-provenance-20261026.md`.

## Verification state

Required safe S2 test subsets were authored/executed by the designated `e2e-runner` on exact committed HEAD `6ca2ee00ef31ac621e7ff3231ac175646bbd3bb2`: Windows 74 passed; WSL2 Ubuntu 24.04 7 passed; 0 failed/skipped. The full 86-ID S2 registry denominator remains incomplete. The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` retained SHA-256 `1273679AC992268BB6FAAC4AC002EDCEDE5D884A7470325314D181E67F6B6B08` and was not edited or staged. S4 code/security agents ran no tests. S3 work was read-only; no package/candidate was acquired, built, installed, or executed. No source code changed in this commit.

## Decisions and owners

- Codex records evidence and coordinates the next exact-head gate; GPT-PM adjudicates S4/S3 contracts; operator remains accountable for any change to prohibited process/crash/mutation selectors and for legal/acquisition decisions.
- The prior S4 GPT-PM request has no durable job, receipt, or correlated exchange. A fresh exact-head request is required; no push/PR/merge follows from these reviews alone.
- Keep S3 Temporal provisional and read-only. PyPI provenance is partial evidence, not acquisition authorization.

## Next action

Generate the document registry and commit this coherent evidence/state change with its own record. Then submit one fresh GPT-PM exact-head S4 adversarial review with the code diff, exact report-bound runtime evidence, and both specialist reports. Continue safe S2 E1/E3/E6 evidence work where it adds new coverage; retain prohibited scenarios as `NOT_RUN`.
