# Change 0258: Use registry-resolvable ACL selector IDs

## What changed

- Replaced a parametrized ACL selector with two explicit named-user and named-group test functions.
- Updated the functional category mapping to use their static pytest node IDs, which the committed registry resolver supports.

## Why

The first ACL test mapping used pytest parameter suffixes such as `[named-user]`. The category resolver deliberately rejects parameterized node IDs because it resolves tests statically from source. Reviewing the resolver caught the mapping defect before the new report-bound functional run. The separate test functions preserve both named grant cases and produce stable, statically resolvable IDs.

## Decisions and ownership

- Keep the functional denominator source-resolvable; do not weaken registry resolution to accept runtime-generated parameter IDs.
- Test author/executor: `functional-test-reviewer`. Accountable task owner: operator; coordinator: Codex.

## Affected contracts and paths

- `tests/qa/test_s4_worker_boundary_contracts.py`
- `docs/qa/categories.json` functional denominator

## Verification state

- Product source provenance remains `c51105abfef72aceb295633bbdf637666ad843a2`.
- The corrected selectors and mapping require a fresh focused run at the committed test HEAD.
- The earlier run at `97c2c24` passed the function bodies while the registry mapping was not source-resolvable; it is not report-bound category evidence.

Executor: Codex
