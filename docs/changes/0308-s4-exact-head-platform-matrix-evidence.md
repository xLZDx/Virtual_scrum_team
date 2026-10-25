# 0308 S4 exact-head platform matrix evidence

**Date:** 2026-10-25  
**Executor:** Codex  
**Tested code candidate:** `05b18450176109aafc108020bc2fafb7136a43d6`  
**Registry source:** `26b959f53e8398b7b4b736b66e4c5a406369705b`

## What changed

- Preserved the designated agents' exact-head Windows, WSL user, and WSL restricted-root category reports, stdout/stderr artifacts, and platform matrix under `docs/sdlc/evidence/qa/`.
- Added the sanitized run/artifact manifest `s4-05b1845-platform-matrix-manifest.json`; no machine-local absolute paths or personal names are included.
- Reconciled this current-state checkpoint and S4 backlog rows VST-032–037 with the final candidate matrix.
- Development remained in the canonical `D:\Repo\Virtual_scrum_team` checkout. Test snapshots in system temporary locations were test inputs, not development worktrees. The pre-existing untracked S2 functional evidence file was not touched.

## Why

S4 acceptance requires a reproducible exact-head matrix across Windows, WSL user, and restricted-root WSL profiles, including report-bound artifacts and a truthful non-approving outcome for every required selector that remains `NOT_RUN`.

## Exact-head evidence

- Focused Windows suite at candidate `05b1845`: 110 passed, zero failed/skipped, one pytest-asyncio deprecation warning. It included the safe outer `NOT_RUN` contract and native collection assertions; the underlying sandbox-dependent selector was not invoked.
- Focused WSL suite at candidate `05b1845`: 7 passed, zero failed/skipped. It covered native collection/repeatability, outer `NOT_RUN` preservation, uncollected/duplicate/skipped/xfail handling, and output truncation. No policy-excluded selector was invoked.
- Windows native QA categories: functional 90/90 `PASS`; integration 41/41, API 688/688, E2E 55/55, and regression 874/874 executed selectors passed, with category results `INCONCLUSIVE` due respectively 37, 14, 1, and 52 policy `NOT_RUN` selectors; seeded-failure 3/3 `PASS`.
- WSL user native QA categories: functional 90/90 `PASS`; integration 46/46, API 690/690, E2E 55/55, and regression 881/881 executed selectors passed, with category results `INCONCLUSIVE` due 37, 14, 1, and 52 policy exclusions; seeded-failure 3/3 `PASS`.
- Restricted-root WSL report-bound categories: integration 1/1, API 1/1, regression 2/2 assigned selectors passed. Each category remains `INCONCLUSIVE` due its policy exclusions. The helper identifies the preflight authority as local/non-authoritative; these reports are not an S2 receipt or independent approval.
- Final matrix run `s4-05b1845-platform-matrix-20261025-r2` resolved all 15 required report references: 6 Windows, 6 WSL user, 3 WSL root. It returned `FAIL` with 4 category reports `PASS` and 11 `FAIL` because their category status is `INCONCLUSIVE`. Its 126 reasons derive only from 52 unique explicit policy `NOT_RUN` selectors; no failed, skipped, xfailed, uncollected, or executed/NOT_RUN-overlap selector was reported.
- The earlier matrix attempt is retained as `BLOCKED`: 14 references were supplied before the required root-harness regression report was available. The final 15-reference matrix is the current result.
- Matrix row SHA-256: `2bba5f4dbf90defba9024132e10496c5cf0ad1fae0c61f3fcea59dac8e8a295a` (1,625,581 bytes). Full matrix JSONL SHA-256: `bf8c3d5cc8916a6bd4490ddaa208d8e47966ef97a8d4d69b8c0e483b4fb99fb6` (1,633,785 bytes). Normalized matrix SHA-256: `b82f325f408a2ba7f06693d80b467274597e7291171884e5ceeb4bd4ea54ceab`.
- Sanitized manifest SHA-256: `11fe8a2c2ab9854c87d85b2e5281994cc60bcf6f0709be639b8a1452feb04a9c`. The manifest records 15 source report rows, candidate/registry identities, source archive hashes, verified source/output chunk ranges, and all 19 combined artifact hashes and byte sizes.
- The matrix validator was run by the designated E2E agent. No tests or checks ran in the primary session during this documentation/evidence reconciliation.

## Reviews

Fresh read-only reviews at candidate `05b18450176109aafc108020bc2fafb7136a43d6` found no actionable findings in the changed S4 scope. The Python review reported GPT-6 Luna / low effort; the code review reported GPT-6 Luna / medium effort. The security review reported GPT-6 Luna, but the exact effort was `NOT_VERIFIED` by that agent. Reviewers did not run tests.

## Acceptance and next

The matrix is valid and complete as an evidence envelope, but S4 is not approved or closed: the 52 policy selectors are mandatory for the current Definition of Done and remain `NOT_RUN`. Do not execute them under the current explicit process-kill/timeout/death/mutation/sandbox restrictions. The next dependent action is an explicit policy/scope decision or accepted signed operator waiver, after which the affected tests and exact-head matrix must be rerun. The non-approving matrix does not authorize a push, pull request, or merge.
