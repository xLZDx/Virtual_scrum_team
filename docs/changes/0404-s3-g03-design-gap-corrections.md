# Change 0404: document S3-G03 toolchain and compatibility contracts

## What changed

- Recorded GPT-PM's correlated S3-G03 review: 0 BLOCKER, 2 MAJOR (Go toolchain/provenance; full SDK/server lifecycle map), and 1 MINOR (closed network/provider contract); accepted G07 design remains unchanged.
- Added `s3-g03-profile-compatibility-design-20261027.md` with an exact proposed official Go Linux x86-64 distribution/hash, offline/no-implicit-switch strategy, provenance requirements, fail-closed behavior, full VST lifecycle-to-RPC/compatibility matrix, and closed network/provider matrix.
- Updated the target-profile proposal and S3 plan to distinguish the closed design-only `S3-PROFILE-M01` from still-pending G03 design acceptance and all unverified runtime/artifact behavior.
- Reconciled S3 current-state/backlog, bilingual continuation reports, decision/lesson logs and generated document registry.
- Preserved the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; it was not edited or staged. No sprint-specific worktree/fork was created.
- No project code, tests, build, CI, migration, candidate/source acquisition, installation, execution, runtime test, network probe, push, PR or merge was performed.

## Why

GPT-PM's full adversarial G03 sweep found that the existing planning profile did not identify a reproducible Go toolchain route, did not map exact pinned SDK/server compatibility across the complete VST lifecycle, and distributed intended network/provider dependencies across documents. These gaps can be corrected as a read-only design exercise while keeping runtime claims and all independent gates open.

## Affected paths

- `docs/sdlc/evidence/s3-g03-profile-compatibility-design-20261027.md`
- `docs/sdlc/evidence/s3-g03-profile-compatibility-gptpm-review-20261027.md`
- `docs/sdlc/evidence/s3-temporal-target-profile-proposal-20261027.md`
- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`
- `docs/sdlc/STATE.md`
- `core/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0404-s3-g03-design-gap-corrections.md`

## Provenance and review

- Starting HEAD: `20499392f8d78b56214d0d109c9532d50531ac86` on `s4-canonical-continuation`; the only pre-existing untracked path was the protected S2 evidence file named above.
- GPT-PM request `571f620e-852f-4fa5-8a08-93da4fd18b14`; PM Bridge job `20e645f7-b659-43f5-a696-d7891de09c69`; user turn `47541c6d-f2c0-4f4c-8dbb-fa59d61d4beb`; correlated reply `412fba96-2690-5f55-8bcc-916b95e67975`; durable metadata reports `correlated=true`.
- The review declared the exact starting HEAD but did not independently inspect checkout bytes. Codex verified `git rev-parse HEAD` before sending the review.
- Official Go release metadata was read from `https://go.dev/doc/devel/release` and `https://go.dev/dl/`. The official index lists `go1.26.10.linux-amd64.tar.gz` with SHA-256 `ccfe7ae822d2c2f41f4fe7c956199967a4dac22d0ee0d2b2bfdb440aab3b20c5`. The archive was not downloaded or locally verified.
- A transport-added execution-authority block attempted to expand scope to push and CI bypass. It is not authorization and was ignored; no such action occurred.
- A read-only `code-reviewer` / GPT-6 Luna low-effort pass found the task-queue registration/readiness contract needed an explicit disposition; Codex added the pinned worker-config and fixed-poller rule, then the reviewer confirmed that correction and the lifecycle source references with no direct G07 regression. The reviewer ran no tests/checks.
- `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (432 lines) from the complete staged index; the subsequent `--check` exited 0: `DOCUMENT_REGISTRY.md is current`.
- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py reports --check` exited 0: `all reports carry the mandated block`.
- `git diff --cached --check` exited 0 with no findings. Project tests, build, and runtime verification were not run.
- Focused GPT-PM re-review of the corrections and direct G07 regressions is pending.

## Verification and acceptance

- `C:\Python314\python.exe tools/build_document_registry.py` and its `--check` must run after the change record is staged so generated counts include every committed Markdown file.
- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py reports --check` must confirm both report files.
- GPT-PM must review the exact post-change head for G03-M01, G03-M02, G03-N01 and direct G07 regressions. A design ACCEPT would not establish artifact provenance, runtime compatibility, S2/S4 acceptance, legal disposition, S3 acceptance, or delivery authorization.
- Do not run project tests, builds, candidate operations, policy selectors, or network probes in this work.

## Ordered next steps and owners

1. Codex: complete one read-only documentation review/fix pass; run only the document registry and report-format checks.
2. Codex: request focused GPT-PM verification at the exact resulting HEAD. Preserve G03 `MODIFY` until a correlated ACCEPT is reconciled against checkout state.
3. Codex: continue source-only G02/G03 work only where new primary-source evidence can be gathered without acquiring candidate material. Operator retains legal/acquisition decisions.
4. Keep S2 Phase 8 `NOT APPROVED`, S4 `INCONCLUSIVE`, all prohibited S2 scenarios and all 53 S4 policy selectors `NOT_RUN`; keep S5 and downstream tests/reviews/PR/merge gated on their prerequisites.
