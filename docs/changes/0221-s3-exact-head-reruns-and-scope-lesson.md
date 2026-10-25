# Change 0221 — S3 exact repository-head reruns and scope lesson

Date: 2026-10-25
Executor: Codex

## What changed

- Recorded exact repository-head functional and E2E reruns for S3's committed focused modules in `docs/sdlc/evidence/s3-exact-head-reruns-2c4e9fd.md`.
- Updated both S3 handover reports to distinguish those reruns at `2c4e9fd` from the narrower GPT-PM approval at `7f1aa35`; corrected the STOP-first evidence row and removed a duplicate English evidence bullet.
- Appended the decision and lesson records, including a correction for an out-of-scope host-wide process enumeration during progress inspection.
- Updated the generated document registry for the new evidence and this change record.

## Why

The exact-head reruns replace the earlier source-equivalent-only evidence for the local synthetic S3 test modules. The GPT-PM approval remains scoped to the local synthetic adapter at its reviewed HEAD and does not approve the full sprint. Recording the process-list scope mistake establishes a concrete prevention rule without accessing the unrelated checkout.

## Affected contracts and paths

- S3 focused functional and E2E modules, as executed by their designated test-agent roles.
- S3 acceptance/report provenance and process-inspection scope lesson.
- Paths: `core/STATE.md`, `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `governance/DOCUMENT_REGISTRY.md`, both S3 reports, this record, and `docs/sdlc/evidence/s3-exact-head-reruns-2c4e9fd.md`.

## Decisions and limits

- Test evidence is literal exact-repository-HEAD evidence at `2c4e9fd0d546d26212dcffa8348fe5349386e2d3`: functional 9 passed, E2E 9 passed; each had 0 failures and 0 skips.
- The S3 GPT-PM approval remains only for local synthetic scope at `7f1aa356ee79b24fb70ba04f06be054b4790c486` (request `e4f16fdc-6175-43f1-97a1-74d50e173970`, reply `7d317e5b-bff9-485f-bce5-d09390f000f3`). No full S3 approval, push, PR, or merge is claimed.
- External candidate execution, fresh S2-bound sandbox evidence, egress/replay, cross-process STOP, and operating-system process cleanup remain open or unverified.
- The coordinator's host-wide `Get-Process -Name python` output incidentally exposed an unrelated executable path under `D:\Repo\ERP_MCP`; no files there were read/opened and no process was changed/terminated. Future checks must target a previously identified PID. No further out-of-scope inspection was performed.

## Verification state

- Functional: `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_adapter.py` — 9 passed, 0 failed, 0 skipped at exact repository HEAD `2c4e9fd0d546d26212dcffa8348fe5349386e2d3`.
- E2E: `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_pilot_e2e.py` — 9 passed, 0 failed, 0 skipped at the same exact HEAD.
- Both runs used Python 3.14.3 and pytest 8.4.2; E2E emitted one pytest-asyncio deprecation warning. Full records and agent roles are in the evidence file.
- Documentation checks in this turn: `report_conform.py` refreshed both S3 reports; `report_conform.py reports --check` exited 0; `tools/build_document_registry.py` exited 0 and wrote 208 lines; `git diff --check` exited 0. No product tests were run by the coordinator in this documentation update.
