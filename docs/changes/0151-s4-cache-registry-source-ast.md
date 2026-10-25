# Change 0151: Cache QA registry source ASTs per validation

## What changed

`tools/qa/registry.py` now caches each resolved test source's parsed AST for the duration of one `load_registry` call. Every ID still passes canonical path, symlink, containment, and tracked-file checks. A source is read and parsed at most once per resolved path; failed, oversized, unreadable, invalid-UTF-8, syntactically invalid, or recursion-exhausting sources are cached as unresolved and continue to fail closed.

## Why

The S4 security review at `2ffc8f7c59156d882f9d69729bc0337439e3705c` found that a candidate-controlled registry could cause the same source file (up to 1 MiB) to be reread and reparsed for every declared test ID. Per-load caching removes that multiplicative I/O and AST parsing cost for IDs sharing a source file while preserving source-path validation on each ID.

## Contracts and decisions

- Cache lifetime is one registry validation; no cross-run stale AST state is retained.
- Cache keys are strictly resolved source paths, after canonical path, symlink-component, and tests-root containment checks.
- Invalid parse results are cached as `None` and rejected for every referencing ID.
- The helper keeps its optional cache argument so existing direct two-argument calls remain compatible.
- No tests, builds, or runtime checks were run during coding. While preparing the commit, `git diff --check` was invoked in the coding phase and emitted only CRLF-to-LF warnings for the two log files; this is recorded as a process deviation, not verification evidence. Test-owner regression evidence is pending.

## Affected paths

- `tools/qa/registry.py`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

Implemented; not runtime-verified. Expected acceptance: same-source test IDs trigger one source read/parse per registry load; invalid source caching remains fail-closed; prior exact-head test and E2E results do not cover this change.

## Provenance

Implemented by Codex in response to the GPT-6 Luna security review at the base HEAD above. Commit hash is recorded in the commit that contains this file.
