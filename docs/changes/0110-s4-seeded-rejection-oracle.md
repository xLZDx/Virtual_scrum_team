# 0110 S4 seeded rejection oracle precision

## What changed

- Tightened the seeded invalid-manifest assertion to require the expected `task_manifest_v2: missing field(s)` rejection context, rather than accepting any `ContractError`.

## Why

The fixture's stable rejection code is `INVALID_TASK_MANIFEST`. Asserting the validator's schema-specific context makes the observation fail if an unrelated contract error replaces the intended rejection path.

## Affected contracts and paths

- `tests/qa/test_s4_registry_contracts.py`: seeded failure scenario for `{"contract_version":2}`.
- `docs/qa/seeded_failures.json`: fixture input, digest, expected rejection and linked node remain unchanged.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- The test observes the existing `validate_task_manifest` boundary and does not modify product code or injected defects.

## Verification state

- The 9-case run at working HEAD `666d6e3d3063c8cf5323088f58cd94d01db03d7f` passed after the registry's per-load Git-query cache was added, with the worktree dirty; that run preceded this assertion refinement and is provisional.
- Exact clean-head verification for this tightened assertion is `NOT_RUN` pending commit `0111` (source/cache and provenance reconciliation) and a fresh focused run.

## Follow-up

1. Run the 9-case owned registry suite on clean committed HEAD after 0111.
2. Record exact head, environment, command, result and warning in the S4 evidence file.
