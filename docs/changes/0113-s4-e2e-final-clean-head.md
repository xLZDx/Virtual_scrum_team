# 0113 S4 E2E final clean-head rerun

## What changed

- Updated `docs/sdlc/evidence/s4-e2e-local-1cd868b.md` with the final clean-head rerun of the owned local E2E module and reconciled its registry-provenance note to the committed final registry.

## Why

The coordinator requested a rerun after the E2E IDs were integrated into the category registry with an ancestor source head and the complete candidate worktree was clean.

## Affected contracts and paths

- `tests/qa/test_s4_qa_e2e.py`: both owned local synthetic E2E journeys.
- `docs/qa/categories.json`: source registry at `4913425c9327b2416ac7cc1e421268223ee43ae1` contains both committed test nodes and is an ancestor of the validation HEAD.
- `docs/sdlc/evidence/s4-e2e-local-1cd868b.md`: records the exact clean-head execution and limitations.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`).
- This rerun uses the existing local synthetic journeys only. Native transfer and signer acceptance remain gated on the exact S4 provisioning inputs; no values were inferred.

## Verification state

- Exact HEAD: `594eeddcd1f6409928e7eebb1e9f8581c8eba75c`; worktree was clean before the run.
- Commands: `python --version`; `python -m pytest --version`; `python -m pytest -q tests/qa/test_s4_qa_e2e.py`.
- Environment: Windows host, Python 3.14.3, pytest 8.4.2.
- Result: 2 passed, 0 failed in 5.28 seconds; one `pytest-asyncio` deprecation warning (`asyncio.get_event_loop_policy`, removal scheduled in Python 3.16).
- Native S4 WSL snapshot transfer, signer/report execution, and exact-head VST gate remain `NOT_RUN` because the private runner identity, worker group, snapshot root, and signer socket are not established in S4 provisioning evidence.

## Follow-up

1. Keep native S4 acceptance as `NOT_RUN` until the designated provisioning evidence supplies the exact runner, worker, snapshot root, and signer socket.
2. Once available, transfer the clean committed candidate and run the native mapped E2E category in `Ubuntu-24.04` without package installation.
