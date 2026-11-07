# S2-1 exact-head regression and review evidence — 2026-10-29

## Scope and provenance

- Repository: `D:\Repo\Virtual_scrum_team`.
- Exact committed HEAD: `2befed5515455c4dbf022cad68e839a8a2ce799c`.
- Current task: S2-1 only. No S2-2 implementation was started.
- Test ownership: actual `functional-test-reviewer` and `e2e-runner` agents executed the runs below. The coordinating session did not execute tests and neither agent edited project files.
- The local `docs/sdlc/verify-evidence.json` is an untracked AF input packet. The `.pm-review` attachment is generated review transport data, not project source; neither was staged.

## Exact-head tests

### S2-1 four-file WSL regression (`e2e-runner`)

Command, with the expected HEAD check set to the exact reviewed revision:

```powershell
wsl.exe -d Ubuntu-24.04 --user root -- sh -lc 'set -eu; if ! mountpoint -q /mnt/d; then mkdir -p /mnt/d; mount -t drvfs D: /mnt/d; fi; grep -F "D: /mnt/d " /proc/mounts; cd /mnt/d/Repo/Virtual_scrum_team; printf "HEAD="; git rev-parse HEAD; git rev-parse HEAD | grep -Fx 2befed5515455c4dbf022cad68e839a8a2ce799c; python3 --version; python3 -m pytest --version; sha256sum tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py; /usr/bin/time -f "DURATION_SEC=%e" python3 -m pytest -q tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py'
```

- Environment: Ubuntu 24.04 WSL, user `root`, Python 3.12.3, pytest 7.4.4; `/mnt/d` mounted from `D:`.
- Result: exit 0; 130 passed, 0 failed, 0 skipped. Pytest duration 5.95 seconds; wall duration 6.67 seconds.
- Test-file SHA-256 values reported by the runner:
  - `tests/vst/test_s2_signed_dispatch_instruction.py`: `13b436675383e98449520c15c640a87fcb84370ade534475b5ad2c63ece8b76f`
  - `tests/vst/test_s2_store_backed_pubsub.py`: `435262304ca08fef9ed371748fa8184086ada46a8f016b4751a997db37f228e7`
  - `tests/vst/test_s2_dispatch_owner_service.py`: `fc7e194cb45700446438c776281be789f8ad0551edc5c506887af35af020df71`
  - `tests/vst/test_s2_dispatch_owner_latch.py`: `dd747aa5c42cf4745197c77b0138c2e71bdd9690ed3d779d00969142382d35f1`
- The corrected fixture remains committed in `dcb5d63`; this run proves the four selected test files at `2befed5`, not installed runtime behavior or restricted process/crash/mutation acceptance.

### Adapter functional suite (`functional-test-reviewer`)

- Command: `node --test tests/vst/test_af_attachment_review.mjs`.
- Environment: Windows PowerShell, Node.js 24.13.1.
- Result: exit 0; 35 passed, 0 failed/cancelled/skipped/todo; duration 127.395 seconds (TAP: 127.267 seconds).
- Test Git blob: `6bacf543ec6971c5f1d421648140bdbf793fad9f`; executed-file SHA-256: `5f11eea71b36d96336f6301452ad559ece56c90889a6bc2cf9c137304e93b4a7`.
- Adapter Git blob at this HEAD: `f5743fd787417f0208d0bd6a211092a2d4b7f890`.

### Adapter E2E suite (`e2e-runner`)

- Command: `node --test tests/af/test_s2_attachment_adapter_e2e.mjs`.
- Environment: Windows PowerShell; Node version was not captured in the saved execution result.
- Result: exit 0; 2 passed, 0 failed/cancelled/skipped/todo; Node duration 13.643 seconds, wall duration 13.783 seconds.
- Test Git blob at this exact HEAD: `9ff2920587415a62390093e35319f01d3a4a0a9c`; executed-file SHA-256: `9cc0b44f6fca5b4a0ff7b9f843866b24f0f9e8178fee4575f405049f9c9ddd07`.
- Output included a fixture-only PM Bridge response; this is not a real GPT-PM review or approval.

## Exact-head GPT-PM review

- AF command: `python D:/Repo/Agentic_Framework/tools/af_cli.py pm-review --kind code --base origin/main`, using the project's documented `AF_PM_REVIEW_JS` adapter.
- Reviewed range: `6117ba24b08a260b42402db6da0bf767864e1c04...2befed5515455c4dbf022cad68e839a8a2ce799c`.
- Request: `ad64e813-a507-4b4a-8601-d9fa1a8276b9`; durable job: `9a75f58f-f517-4354-92c2-eae954f31c74`; correlated reply: `c46b1b10-9b56-5d7c-bcf9-9f4b950dfa69`.
- Attachment: 5,766,789 bytes, SHA-256 `833efc361a34266767e331ebf6a2724cecba3e03512e4443ddf6cd661d93311b`. GPT-PM confirmed the declared HEAD, attachment size, and hash.
- Verdict: `MAJOR`; exact-source approval `HOLD`; formal AF approval `NOT GRANTED`; S2 acceptance `NOT APPROVED`. No approval file was created and no push was attempted.
- `S2-REVIEW-01`: the attachment diff contains `[REDACTED]` substitutions in code expressions, including the attachment adapter and S2 authorization/key-related code. The committed parser builds an acknowledgement prefix from the current label and a colon at `tools/af_attachment_review.mjs:191`; its Git blob is `f5743fd787417f0208d0bd6a211092a2d4b7f890`. The attachment instead replaces the expression after `const token =` with `[REDACTED]` at line 67419.
- `S2-REVIEW-02`: because substitutions obscure code and security-sensitive expressions in the 87,222-line package, GPT-PM could not certify complete adversarial coverage. This is a review-evidence gap, not a confirmed source defect.
- The project adapter validates attachment size, hash, and UTF-8 before transport (`tools/af_attachment_review.mjs:42-49,325,376`). The redacted expression is already present in the prompt produced by the native review path, before attachment transport. The inspected native review dependency calls `redactSecrets(diff)` in `D:/Repo/pm-bridge/src/cli/review.js:157-160`; its redactor treats names containing `token` as secret-shaped in `D:/Repo/pm-bridge/src/secretRedaction.js:96-99`. This explains the safe acknowledgement-prefix false positive. Other redactions include key/authorization-related expressions and must not be bypassed.
- A read-only exact-base/HEAD comparison matched all 41 masked diff lines across 15 files to raw Git diff lines and recorded each exact HEAD blob without exposing the masked values. Eight shapes have duplicate candidates. Details and limits are in `docs/sdlc/evidence/s2-review-redaction-source-fidelity-2befed5-20261029.md`; this establishes blob identity but does not make the masked values inspectable to GPT-PM.

## Acceptance boundary

- S2-1 source/test acceptance is retained; task delivery remains OPEN until normal push succeeds.
- Installed runtime, systemd/kernel identity, production configuration, current E5, and restricted process-kill/crash/mutation/policy scenarios remain unproven or `NOT_RUN` as separately recorded.
- S2-2 was not started by this continuation. Do not start it before S2-1 has an acceptable exact-head review and its normal push succeeds.
