# Change 0202: Clarify S4 POSIX and report-bound status

## What changed and why

Clarified AC-10 in the bilingual S4 checkpoint report: three exact-head POSIX symlink selectors passed, while the report-bound WSL runner path remains `NOT_RUN`. This avoids describing all current-head POSIX evidence as absent and preserves the independent identity-transition gate.

## Affected contracts and paths

- `reports/S4_QA_AUTOMATION_2026-10-25.ru.html`
- `reports/S4_QA_AUTOMATION_2026-10-25.html`
- `core/DECISION_LOG.md` and `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Evidence and decisions

- Focused evidence is change 0201: exact S4 HEAD `1c97ee968e6c9f8ab133a3b6d7452e17a17ee600`, Ubuntu-24.04 WSL2, 3 passed / 0 failed / 0 skipped.
- Report-bound serialization, signer identity, runner-to-worker transition, receipt, authoritative gate, and aggregate regression remain unverified.
- No source or test code changed in this documentation correction.
- The report conformance tool refreshed both reports; the document registry was regenerated with `C:\Python314\python.exe tools/build_document_registry.py`.

## Verification state and ownership

The change is documentation-only and manually reviewed by `code-reviewer` (GPT-6 Luna, low effort); no new test run was performed. The operator remains accountable for the delegated sprint; Codex executed the correction. The technical QA service owner remains `UNKNOWN` in canonical project records.
