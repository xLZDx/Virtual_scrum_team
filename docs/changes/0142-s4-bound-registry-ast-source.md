# 0142 S4 bound registry AST source input

## What changed

- Bounded the source bytes read by the QA registry's static pytest-node resolver to 1 MiB.
- Read at most one byte beyond that bound and reject oversized source before decoding or AST parsing.
- Treat `RecursionError` from AST parsing as a non-resolving test ID, preserving the existing fail-closed behavior.
- Preserved canonical path, symlink, repository-root, and `tests/` directory confinement checks.
- Updated the S4 backlog and decision/lesson records; regenerated the document registry.

## Why

The final S4 code review found that an arbitrarily large or deeply nested tracked test source could consume parser resources or escape the registry's typed refusal path. Current tracked test sources inspected during this change are below 148 KiB; a 1 MiB limit leaves substantial room while bounding the untrusted parse input.

## Affected contracts and paths

- `tools/qa/registry.py`: bounded source read and AST recursion handling in `_pytest_node_id_exists`.
- `core/BACKLOG.md`: S4 parser-bound regression status.
- `core/DECISION_LOG.md` and `core/LESSONS_LOG.md`: bounded-input decision and lesson.
- `governance/DOCUMENT_REGISTRY.md`: generated index.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation; executor: Codex.
- Reviewer roles remain reviewers, not technical service owners. No technical service owner for the QA registry is established in canonical project records.
- Oversized or recursively unparseable source cannot resolve as a registered node. No raw source content is included in errors.

## Verification state

- The source change and supporting documentation were authored. No tests, builds, CI, migrations, or runtime probes were run in this coding pass. The coordinator accidentally ran `git diff --cached --check`; it returned exit code 0 with no diagnostics and is explicitly not verification evidence. This process error is recorded in `core/LESSONS_LOG.md`.
- Focused functional regression for the byte limit and AST recursion handling is pending with the designated functional-test reviewer.
- Current WSL transfer/native behavior remains `RESULT_NOT_CAPTURED` / `NOT_RUN` as recorded in change 0141.
