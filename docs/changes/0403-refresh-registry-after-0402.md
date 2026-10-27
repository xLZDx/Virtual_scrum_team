# Change 0403: refresh document registry after change 0402

## What changed

- Regenerated `governance/DOCUMENT_REGISTRY.md` from the complete post-0402 Git index so it includes change 0402 and the two new S3 GPT-PM evidence records.
- Preserved the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; it is outside this registry because the generator indexes tracked/staged Markdown only.
- No source code, tests, project checks, build, CI, migration, acquisition, installation, candidate execution, push, PR, or merge was performed.

## Why

The first change 0402 registry generation happened before its new change record and two evidence records were staged. The generator intentionally reads the Git index, so a post-commit check exposed three newly committed Markdown files missing from the generated registry. This follow-up refreshes the index without rewriting the completed 0402 commit.

## Affected paths

- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0403-refresh-registry-after-0402.md`

## Provenance and verification

- Parent commit: `91b6696fe14bc13039565ace3a12b3819dd2a3d7` (`docs: reconcile S3 profile with G07 (change 0402)`).
- `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (429 lines); the staged-index follow-up `--check` exited 0 with `DOCUMENT_REGISTRY.md is current`.
- Report conformance was checked after the 0402 report edits: `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py reports --check` exited 0 with `all reports carry the mandated block`.

## Ordered next step

1. Codex: stage this change record, regenerate and check the document registry from the staged index, then commit this registry-only correction locally.
