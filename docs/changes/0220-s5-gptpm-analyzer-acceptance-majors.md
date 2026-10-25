# Change 0220: Record S5 analyzer acceptance findings

## What changed

- Preserved the complete correlated GPT-PM final response for S5 exact repository HEAD `8cb3ab4167239c0ad3316a9e51d756be3d9520c2` in `docs/sdlc/evidence/s5-gptpm-final-review-8cb3ab4.json`.
- Updated the S5 plan status, VST-038–VST-042 backlog entries, decision/lesson logs, and bilingual report to record two open full-acceptance MAJOR requirements separately from the implemented local v3 contract.

## Why

GPT-PM confirmed there is no demonstrated source-level BLOCKER or MAJOR in the local VST v3 evidence contract, but returned `MAJOR — MODIFY` for two explicitly required S5 capabilities that are absent or unverified: bounded analyzer execution and truthful executed analyzer-rule evidence. The local digest and receipt helpers must not be described as an immutable execution boundary or proof that a declared rule ran.

## Correlated review

- Request ID: `f9399e86-4b8b-4d8a-b2b5-26140f5639e1`
- Reply ID: `61d7078e-ec7e-45e6-9f6a-ad2beb99c9e7`
- Review-input hash: `8ab6b4e5d46876a4266847340e4c3481f8c4b70594621cbac40e4e8e686dd52f`
- Branch: `s5-bounded-aeve-evidence`
- Exact reviewed HEAD: `8cb3ab4167239c0ad3316a9e51d756be3d9520c2`
- Verdict: `MAJOR — MODIFY` for full S5 AC-1–AC-13 acceptance; source-level BLOCKER=0 and MAJOR=0; two unclosed acceptance MAJOR items.

## Findings and remaining dependencies

### S5-M01: bounded execution and immutable snapshot boundary (AC-5/6)

`tools/vst/source_tree.py` deterministically hashes a supplied directory and fails closed on traversal, symlinks, non-regular files, content changes and configured bounds. It does not create/enforce an immutable read-only snapshot or constrain analyzer CPU, memory, wall time, output, subprocesses or network. The actual AEVE source identity, adapter interface, runtime and technical owner are UNKNOWN in the project. An untested generic wrapper without that accepted contract would not close the criterion.

### S5-M02: executed rule truth and seeded analyzer evidence (AC-7/8)

The VST contract validates rule-status partitions and finding-derived failure locally. `docs/qa/seeded_failures.json` remains empty with `state: NOT_RUN`; no authorized analyzer has demonstrated a supported-rule inventory, a known-issue finding and a clean checked-rule scenario. The analyzer and rule-catalog technical owner is UNKNOWN.

The operator is accountable for delegated S5 and for providing/authorizing the in-scope source/runtime identity. Codex is executor once the interface and boundary are available. `functional-test-reviewer` and `e2e-runner` own the subsequent acceptance-test authoring/execution. Do not inspect sibling checkouts or acquire unapproved external candidates. After source and runtime authority are established: implement the bounded adapter, accept fixture-to-rule mappings, run seeded positive and clean scenarios, provision an independent trusted attestor, then run exact-head signed report/gate acceptance and obtain a new GPT-PM review.

## Verification state

- Existing local evidence remains scoped: functional v3 contract 39 passed/1 skipped at `0dbb662`; Store-to-Gate E2E 3/3 at `7cd83ea`; focused POSIX source-digest symlink selector 1/1 at `606bba9` (0137). Those are not analyzer-runtime evidence.
- The GPT-PM review was source/evidence inspection; it did not independently run tests, provision AEVE, or verify a live checkout.
- No product code or tests were changed or run for this documentation update. `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and generated 202 lines. `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py reports\S5_V3_GATE_STATUS_2026-10-25.ru.html reports\S5_V3_GATE_STATUS_2026-10-25.html` exited 0 and refreshed both reports; `report_conform.py reports --check` exited 0 with “all reports carry the mandated block”. `git diff --check` exited 0.
