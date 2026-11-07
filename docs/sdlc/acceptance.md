# Sprint S2 acceptance disposition

As of 2026-11-06, exact code candidate `96a8da7bf5af5c9d5b37e56287c48472cb239254` is pushed to `origin/s2-canonical-continuation` and updates the existing Sprint S2 PR #2.

## Decision

**S2 bounded source/test acceptance through S2-4D and S2-5: ACCEPTED.** This is not full Sprint S2 closure. The operator's 2026-11-06 scope decision removed the WSL inventory/configuration-apply/qualification QA harness and its Git-source checks from active acceptance. A separate Windows-local Owner-to-Runner task, S2-4E, is now required before S3.

**E5/live-runtime/production acceptance: NOT ACCEPTED / NOT_RUN.** Current run-bound E5 and production identity/configuration were not produced. These are separate from S2-4E: the Windows-local task below does not require E5, production credentials, WSL, or a VPS, and does not claim production readiness or activation.

## Acceptance matrix

| Task / requirement | State | Evidence | Remaining scope | Owner / next action |
|---|---|---|---|---|
| S2-1 — signed instruction, Store admission, recovery (REQ-001/002/004) | ACCEPTED — bounded source/test | Pushed commit `e332ec4`; GPT-PM request `f92b750e`; evidence and limitations in `docs/sdlc/backlog.md` and `docs/sdlc/verify-evidence.md`. | Installed runtime and production evidence were not established by this task. | Codex: preserve recorded limits; no reopen without a concrete regression or changed requirement. |
| S2-2 — authenticated owner transport (REQ-002/003) | ACCEPTED — bounded source/test | Pushed commit `e987a24`; GPT-PM request `b0f60d46`; delivery record 0588. | Production systemd identity and live Runner journey remain unproven. | Codex: preserve runtime limitation; no duplicate test run. |
| S2-3 — immutable bundle, inactive stage-only preparation | ACCEPTED — bounded preparation/source-test | Pushed commit `ae07f87`; GPT-PM request `ac2d25a2`; accepted post-stage manifest evidence. | Does not establish active services, production dispatch, E5, or live Runner behavior. | Codex: no activation or runtime claim. |
| S2-4A — issuer and verifier source/test | ACCEPTED | Exact-source approval `c978360` (request `8fc2e0ba`) and V2 verification slice `aa349632` / `e09c78b`. | No production signing key or live issuer is claimed. | Codex: retain accepted baseline. |
| S2-4B — bounded preparation and stage-only source | ACCEPTED | Pushed evidence through `19338ba`; focused test/review records are linked from the S2 backlog. | No live Runner or production readiness is implied. | Codex: retain accepted baseline. |
| S2-4C — preparation/qualification source hardening | ACCEPTED — source/test | GPT-PM exact-byte approval and pushed commit `67361bb`; recorded focused tests/reviews. | WSL collector and Git-source qualification are retired from active scope; old records remain history. | Codex: do not rerun retired workflow. |
| S2-4D / REQ-003 — persisted Store handoff and removal of retired WSL QA harness | ACCEPTED — bounded source/test; pushed | Commit `96a8da7`. Windows selector: 1 passed. Bundle contract module: 11 passed. GPT-PM request `a2c98c0f-a741-4ad6-8330-8cbde5bc3571`, correlated reply `f981ea40-d56c-58aa-8c5e-87631a900140`: APPROVE, 0 BLOCKER / 0 MAJOR. Internal `code-reviewer` and `code-explorer` reported no product-path finding. | The selector proves persisted Store handoff equality only; it does not prove live Runner, E5, or production. | Codex: delivered to S2 PR #2; keep runtime status separate. |
| S2-4E — Windows-local Owner→Runner functional path | IN_PROGRESS — Windows source accepted; end-to-end runtime NOT_RUN | Commit `c4558a8` adds the Windows SCM service path and Store admission changes; GPT-PM request `e4f0bb3a-75a2-4f87-b58a-7a5e53d11588` accepted that exact source delta. Assigned functional-test-reviewer reports Store contract 5/5 and receipt contract 4/4 passed. | The Owner-route functional module remains `NOT_RUN` (its current pytest/POSIX-root fixture cannot run under the active test restrictions). The standalone Windows process E2E remains `NOT_RUN` until the six VST services, protected `%ProgramData%\VST\runtime.json`, existing signed instruction, and in-repository manifest are provisioned. The harness consumes these inputs and does not install/start services or create keys. | Codex coordinates; functional-test-reviewer and e2e-runner own the remaining task-mapped tests; operator owns any required elevated host provisioning. E5/production remains separate and `NOT_RUN`. |
| S2-5 / REQ-006 — exact-head code review and S2 code disposition | ACCEPTED — bounded source/test scope | Same exact candidate `96a8da7`; GPT-PM approval above; pushed successfully; no code change after review. | Runtime/E5/production remain NOT_RUN as stated above. | Codex: preserve this acceptance; do not reopen on a documentation-only or HEAD-only change. |

## Verification boundaries

- The 2026-11-06 test attempts ran on the Windows project checkout. Their exact commands, source/test hashes, stdout/stderr hashes, and the corrected initial bundle-test failure are in `docs/sdlc/evidence/s2-4d-req003-windows-selector-20261106-02.attempt.json` and `docs/sdlc/evidence/s2-4d-runtime-config-bundle-windows-20261106-01.attempt.json` / `...-02.attempt.json`.
- The REQ-003 selector is a local Store-level test, not an end-to-end Windows Runner test. The focused bundle tests verify the repository bundle contract only.
- The correlated GPT-PM verdict approves the exact bounded code candidate; it is not an E5 attestation or runtime/production approval.
- There is no project `evidence.py` or documented equivalent command in this repository. The named attempt records and raw outputs were used as bounded evidence; no broader evidence-tool result is claimed.
- E5, production qualification, and runtime/production operations remain `NOT_RUN`; they are not part of the current Windows-local S2-4E criterion.
