# Change 0256: Map QA source ACL regressions

## What changed

- Added functional selectors for named user/group access ACLs on tracked source, directory default ACLs, ACL inspection failure, and an ACL-free source tree.
- Mapped those selectors to the committed functional category and pinned its source provenance to the source fix commit `c51105abfef72aceb295633bbdf637666ad843a2`.

## Why

The security review found that mode-bit-only source/Git preflight could miss a named ACL granting worker write access. The tests isolate the ACL guard from the mode-bit fallback so the old behavior would accept the synthetic worker ACL and the fixed behavior refuses it.

## Decisions and ownership

- A synthetic ACL xattr is sufficient for deterministic unit-level verification that any extended access/default ACL is refused; it does not claim to install a real host ACL.
- The designated `functional-test-reviewer` owns the selectors and focused test execution. The operator is accountable for the delegated task; Codex coordinates.

## Affected contracts and paths

- `tests/qa/test_s4_worker_boundary_contracts.py`
- `docs/qa/categories.json` functional test-ID denominator and source provenance

## Verification state

- Product source HEAD: `c51105abfef72aceb295633bbdf637666ad843a2`.
- Test execution: `NOT_RUN` at commit preparation; run the six `qa_preflight` selectors on the exact committed test head and retain the exact command/result.
- The outer report-bound functional run and full focused worker suite must be rerun by `e2e-runner` after this test mapping commit.

Executor: Codex
