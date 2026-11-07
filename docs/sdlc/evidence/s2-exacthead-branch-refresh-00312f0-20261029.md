# S2 exact-head changed-code test refresh and PM review attempt — 2026-10-29

## Scope and identity

- Repository: `D:\Repo\Virtual_scrum_team`.
- Branch: `s2-canonical-continuation`.
- Review HEAD: `00312f0b845f5f914254eab33be2fa8224f53159`.
- Sprint review base: `origin/main` at `6117ba24b08a260b42402db6da0bf767864e1c04`.
- The refresh covered the committed code paths the AF gate identified as changed after its previous test packet at `62bb632`. It did not run restricted process/crash/mutation/policy selectors or claim installed-runtime, E5, or production evidence.

## Focused test executions

| Suite | Exact command | HEAD and environment | Result | Recorded scope |
|---|---|---|---|---|
| S2-1 recovery regression | `python3 -m pytest -q tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py` | Code HEAD `56cd816b1b03b39c3f4b4a70ecf00d96ef95d321`; Ubuntu 24.04 WSL; Python 3.12.3; pytest 7.4.4 | 130 passed, 0 failed; exit 0 | Exact command, four test-file hashes, initial failure and committed-blob verification are in `s2-cross-generation-outcome-recovery-rerun-56cd816-worktree-20261029.md` and `s2-1-current-regression-run-56cd816-20261029.md`. |
| AF attachment-review functional suite | `node --test tests/vst/test_af_attachment_review.mjs` | HEAD `00312f0b845f5f914254eab33be2fa8224f53159`; Windows; Node.js v24.13.1 | 35 passed, 0 failed, 0 skipped; exit 0; 178.55 seconds | Actual `functional-test-reviewer` execution. Covers AFAT-01–12; no live GPT-PM verdict. Test SHA-256: `1c42e35d6ae8b790e5c722f44217620b53f018b82809f7d6fea99f5450243c5d`; source SHA-256: `9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e`. |
| AF attachment-adapter E2E suite | `node --test tests/af/test_s2_attachment_adapter_e2e.mjs` | HEAD `00312f0b845f5f914254eab33be2fa8224f53159`; Windows; Node.js v24.13.1 | 2 passed, 0 failed; exit 0; about 19.6 seconds | Actual `e2e-runner` execution. Covers authenticated loopback transport, durable receipt handling and dump-only prompt generation. Test SHA-256: `9cc0b44f6fca5b4a0ff7b9f843866b24f0f9e8178fee4575f405049f9c9ddd07`; adapter source SHA-256 as above. |

The two Node test agents made no file changes. Their executed files match the Git blobs at the recorded HEAD. The S2-1 Python run is bound to commit `dcb5d63c19eeb63f2f17fce0add510937688e819`: its stored test-file SHA-256 matches the test blob read back from Git.

## Exact-head review transport and outcome

- Command: `$env:AF_PM_REVIEW_JS='D:\Repo\Virtual_scrum_team\tools\af_attachment_review.mjs'; python D:/Repo/Agentic_Framework/tools/af_cli.py pm-review --kind code --base origin/main`.
- The native inline attempt previously exceeded the PM Bridge 4 MiB JSON body limit. With the documented project-owned `AF_PM_REVIEW_JS` override, the exact 5,753,229-byte canonical prompt was sent as one file attachment. Its SHA-256 was `42c2621ae9382d2870cb231a25a96e8d758871520d6ed786efe824ba5ff406fb`.
- Correlated request ID: `d2492272-ed6c-4eb7-9584-6bfe44af868e`; durable job ID: `0396e9f8-6cdc-45e7-a769-f6c9e806f7f2`; user turn ID: `44287481-997b-4555-8ed7-4003ba640b03`; reply ID: `60978efd-accd-52a3-a4be-e5049ae4cf68`.
- Durable PM Bridge status: `succeeded`, `sendPhase=sent`, `correlated=true`. AF review result: `NOT_APPROVED`, parser verdict `UNRECOGNIZED`, no approval written.
- The correlated GPT reply states `VERDICT: NOT REVIEWED — EXECUTION ENVIRONMENT UNAVAILABLE`: it could not access or inspect the attached packet and did not conduct an adversarial code review. This is an infrastructure limitation, not a source-code finding or approval.
- A narrower review base `56cd816` was refused by AF because it is after sprint baseline `20fda2cbf26274192652a1c829a19f6b1844e9c4` and would omit sprint changes. No base or approval gate was bypassed.

## Disposition and next action

S2-1 source/test work is committed and its focused regression passes. Delivery remains OPEN because exact-head GPT-PM approval and normal push are still required. The current reply is not approval. Owner for coordination and retry: Codex; owner for the actual review verdict: GPT-PM. Retry the same full-range packet through the documented attachment adapter when GPT-PM has a usable execution environment. Do not begin S2-2 before the normal push succeeds.
