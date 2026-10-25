# Change 0159: Record a fresh S4 WSL2 transfer and mapped E2E run

## What changed

Recorded a fresh correlated transfer of exact S4 HEAD `56dce67e508ccf452b2b7b39ed7f33c863081269` into a newly provisioned run-specific WSL2 snapshot, the verified worker read-only boundary, seven mapped POSIX E2E selectors, and the clean post-run state. Updated the S4 plan, backlog, decision log, lesson log, and generated document registry.

## Why

The previous S4 transfer attempt returned no run ID, so its destination could not be safely inspected. A new unique snapshot root was created under the already selected dedicated Ubuntu-24.04 WSL2 environment. This run returned correlated metadata, allowing only that new run to be verified without inspecting or retrying the unidentified prior destination.

## Evidence

- New run ID `f3ad62c94bc0429987bc24277103d5b4`, exact source/head match, bundle SHA-256 `d842a5770c4b6b4c0e69eafc00d61e3b6460e0c7868b3ea05664677b2a943a6e`, `1,105,578` bytes.
- Runner-side source/Git metadata permission audit passed; worker read access passed, append-open was denied, and the repository directory was not writable.
- Seven mapped WSL selectors: 7 passed, 0 skipped/failures in 3.62 seconds on CPython 3.12.3 / pytest 7.4.4.
- Post-run exact HEAD matched and porcelain status measured 0 bytes.
- Full evidence: `docs/sdlc/evidence/s4-wsl-transfer-56dce67.md`.
- One initial inline Python preflight was malformed by literal newline escaping and failed with `SyntaxError` before assertions. Corrected independent probes passed; this setup error is retained, not classified as product failure.

## Affected paths

- `docs/sdlc/evidence/s4-wsl-transfer-56dce67.md`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `reports/S4_QA_AUTOMATION_2026-10-25.ru.html`
- `reports/S4_QA_AUTOMATION_2026-10-25.html`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

Transfer, worker-boundary, and mapped-selector acceptance passed for this exact identified run only. The bilingual status checkpoint was refreshed to reflect the new run while preserving the prior unknown destination as untouched. `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py --check reports\S4_QA_AUTOMATION_2026-10-25.ru.html reports\S4_QA_AUTOMATION_2026-10-25.html` exited 0 (`all reports carry the mandated block`). `C:\Python314\python.exe tools\build_document_registry.py --check` exited 0 (`DOCUMENT_REGISTRY.md is current`). Signer, report-bound runner, receipt, authoritative gate, full category coverage, and broader sandbox conditions remain unverified.

## Provenance

Executed and recorded by the designated E2E runner agent on the exact clean source head above. Private snapshot path and numeric identities are omitted from public files. No other destination was inspected or modified.
