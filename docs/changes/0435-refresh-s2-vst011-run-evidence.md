# Change 0435: bind S2 VST-011 to the fresh signer run

## What changed

- Updated S2 backlog item VST-011 to point to the run-bound signer-isolation evidence at exact source/test head `f0bbac8`.
- Kept the older `280e2d0` run explicitly historical and retained the limitation that a per-run result is not persistent production deployment evidence.

## Why

The S2 backlog still cited only an older signer run, while the exact-head E5 attestation records the runner/signer boundary and signing outcome for `f0bbac8`. The reference should identify the strongest current evidence without implying broader deployment acceptance.

## Affected paths

- `core/BACKLOG.md`
- `docs/changes/0435-refresh-s2-vst011-run-evidence.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and review

- Starting repository HEAD: `99dd3e560737844eda38456c2e66c8d76930a981`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.
- Source evidence: `docs/sdlc/evidence/s2-e5-runmanifest-wsl-f0bbac8-20261026.md`, change 0339. Its run-bound account records distinct runner/signer identities and successful signature verification.
- This is a documentation-only correction. No source/test code, tests, runtime scenarios, builds, CI, or migrations were run.

## Acceptance and next steps

- VST-011's evidence link now matches the most recent exact-source/test-head per-run record; its persistent deployment limitation remains open.
- Keep S2 Phase 8 open until the remaining mandatory system/runtime acceptance is reconciled and GPT-PM reviews the exact final head.
- Owner: Codex for evidence and backlog reconciliation; operator for any required platform/policy disposition; GPT-PM for the later exact-head gate.

## Attribution

Change: 0435
Executor: Codex
