# Change 0212: Record S2 exact-head GPT-PM MODIFY findings

## What changed and why

Recorded the correlated GPT-PM review response for S2 branch HEAD `12758c9410276e58591f879b34a2a5b0b39c8b30`. The verdict is `MAJOR — MODIFY`; it identifies unclosed acceptance evidence, not a newly demonstrated source vulnerability. The current backlog, state and bilingual checkpoint now distinguish these findings from code defects.

## Affected acceptance and paths

- S2 E4: POSIX/process containment and Windows Job Object nesting.
- S2 E5: binding the signed run inventory to actual worker environment/workspace and enforcing OS-level resources.
- S2 E8: full isolated crash/resume bake-off.
- `docs/sdlc/evidence/s2-gptpm-final-review-12758c9.json`
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `docs/sdlc/STATE.md`
- Bilingual `reports/S2_ISOLATED_WORKER_SANDBOX_2026-10-25.*.html`
- `governance/DOCUMENT_REGISTRY.md`

## Correlation and findings

- Request ID: `460d72c5-e4a7-4b92-b5e4-9f6a16221a9d`.
- Reply ID: `2c5bfa37-3502-46e6-8092-dcd77904f5e4`.
- Input hash: `b51609ec03d37bf0b45961d1ac794894ac37ecec99e8cc6ea2f31575b19397a6`.
- Transport returned `RAN`, `correlated: true`, verdict `MAJOR`; no APPROVE was returned.
- M01: E8 crash/resume acceptance is unverified; prohibited process-kill/mutation scenarios must not be run to force a green result.
- M02: E4 platform proof is incomplete; some cleanup scenarios are prohibited and Windows nesting needs its target host.
- M03: signed preflight is run/spec/nonce-bound but does not prove the worker callback uses the same environment/workspace or enforce OS memory/storage/process quotas; the synthetic object cap is not a disk quota and cooperating locks do not exclude bypass writers.
- The exact correlated response is preserved in the evidence JSON. GPT-PM reported no newly demonstrated exploit/source defect beyond these acceptance boundaries.

## Verification state and ownership

`code-explorer` (GPT-6 Luna, medium effort) independently mapped M03 to the source and evidence and found no safe standalone source change that could close it without a real deployment launcher and runtime identity/quota data. No source or tests changed for this record. Operator is accountable for delegated S2 work; Codex executed the audit. The technical platform/service owner remains `UNKNOWN` in repository records. Do not push or open a PR without resolution/approved scoped disposition and a fresh exact-head APPROVE.

## Documentation verification

- C:\Python314\python.exe tools/build_document_registry.py exited 0 and regenerated the Markdown registry (186 lines).
- The project report conformance utility exited 0 and refreshed both bilingual HTML checkpoint reports.
- No tests, product checks, builds, migrations, runtime probes, or source edits were performed for this record.
