# Change 0153: Retry transient QA registry Git timeouts once

## What changed

`tools/qa/registry.py` now retries `git ls-files --error-unmatch` and `git rev-parse --verify HEAD` once when, and only when, the subprocess raises `TimeoutExpired`. Each attempt remains bounded to five seconds; total waiting is capped at ten seconds per affected lookup. A second timeout still returns a fail-closed result. Nonzero exits and `OSError` are not retried.

## Why

Change 0152 records three full focused-module attempts where the suite's committed-registry integration case failed closed after `git rev-parse --verify HEAD` timed out at five seconds; an earlier attempt observed a timeout in `git ls-files`. A direct helper call outside pytest succeeded. The evidence establishes intermittent timeout behavior, but not its underlying environmental cause. One bounded retry gives transient stalls a chance to recover without making Git calls unbounded or weakening provenance checks.

## Contracts and affected paths

- `tools/qa/registry.py`: timeout constants and one retry wrapper used by tracked-path and candidate-HEAD lookups.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: record the observed failure and bounded retry policy.
- `governance/DOCUMENT_REGISTRY.md`: generated index updated.

## Verification state

Implemented; no tests, checks, or builds were run during coding. Functional agent must rerun the complete focused registry module at the resulting exact HEAD. Failures after both attempts remain fail-closed.

## Provenance

Implemented by Codex in response to failure evidence recorded in change 0152. Commit hash is recorded in the commit containing this record.
