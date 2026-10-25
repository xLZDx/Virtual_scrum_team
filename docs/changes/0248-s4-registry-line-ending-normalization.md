# 0248 S4 registry line-ending normalization

**Date:** 2026-10-25  
**Executor:** Codex  
**Implementation agent:** `implementation-engineer`, GPT-6 Luna, medium effort  
**Test author:** `functional-test-reviewer`, GPT-6 Luna, medium effort  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `0122f063d173678e8285a9b0b956998ed7a44851`

## What changed

- Normalized CRLF to LF before hashing test source bytes in both registry generation and validation. Other source edits remain hash-significant, and selector parsing continues to use the original bytes.
- Added a functional contract test that generates a registry over LF source, rewrites the same source with CRLF, and requires the existing inventory hash to validate.
- Preserved the first exact-head category attempt at `d99be24` and all six subsequent category attempts at `0122f06` as append-only JSONL reports with their captured stderr/stdout chunks.

## Why

The registry generator hashed raw bytes from the canonical Windows working copy. The tracked Python file `tests/vst/test_s2_runner_lifecycle.py` had CRLF working-copy bytes (62,456 bytes, digest `765745b3fa46be84f32862a8a306cc4a91188fe2da9b4239a61b2a35390d27a5`), while its committed Git blob and clean candidate checkout had LF bytes (61,023 bytes, digest `cde106cf3e386d444f948e53b43c9a14bbc07a8daac0bd39ca466812b6604059`). The manifest therefore reflected line-ending conversion rather than a source change.

## Evidence and verification

- At exact candidate HEAD `0122f063d173678e8285a9b0b956998ed7a44851`, each of the six QA categories (`functional`, `integration`, `api`, `e2e`, `seeded-failure`, `regression`) returned `BLOCKED` before pytest collection with `RegistryError: test source changed after registry generation: tests/vst/test_s2_runner_lifecycle.py`. All six reports record zero expected/executed tests, an empty child command, and no pytest version; no test body ran.
- The reports are preserved under `docs/sdlc/evidence/qa/`. The functional report retains the earlier d99 blocked attempt as row one and the 0122 attempt as row two; the other category reports each have one blocked row. Stdout chunks are empty; stderr chunks retain the preflight reason.
- The difference between the committed LF Git blob and canonical CRLF working copy proves the mismatch was line-ending-only, not an uncommitted source edit. `.gitattributes` declares `*.py text eol=lf`.
- The registry fix and its line-ending test are committed together; **no tests were run after the fix**. No worktree or development clone was created; the temporary exact-commit candidate was used only for test execution. The pre-existing untracked S2 evidence file remains untouched.

## Acceptance and next steps

- VST-032: registry hashes are now line-ending-stable; regenerate the manifest after this test-source commit.
- VST-033–037: exact runtime/category evidence remains pending; the six preserved reports are preflight `BLOCKED`, not test results.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Implementation executor: `implementation-engineer`; test author/executor: `functional-test-reviewer`/`e2e-runner`.
- Next: commit this fix and the new test, regenerate and commit the category registry with normalized hashes, then repeat all six categories on the new exact HEAD. Keep all policy-prohibited selectors `NOT_RUN`.
