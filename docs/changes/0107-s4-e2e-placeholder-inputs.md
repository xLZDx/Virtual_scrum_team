# 0107 S4 E2E placeholder input hardening

## What changed

- Replaced the snapshot-refusal test's unused runner account, worker GID, and destination path with explicit placeholder values.

## Why

The test exits on the unsupported distribution before validating or using the other CLI arguments. The earlier numeric fixture happened to match an identity recorded in historical S2 evidence. It was inert test data, but using unmistakable placeholders avoids any suggestion that it represents private S4 provisioning.

## Affected contracts and paths

- `tests/qa/test_s4_qa_e2e.py`: wrong-distribution validation must reject before any WSL, Git bundle, or signer operation; other required CLI fields are placeholders only.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`).
- No private runner account, worker GID, destination root, or signer socket is supplied or inferred by this test.

## Verification state

- Before this change's test-source commit, at source HEAD `e58edf1f784c6dff8d540088352e148f7e818d68`, the focused module passed 2/2 in 6.80 seconds on Windows Python 3.14.3 / pytest 8.4.2; one existing `pytest-asyncio` warning.
- The changed test source was uncommitted during this run. Exact post-commit verification will be recorded separately.

## Follow-up

1. Commit this test-only input cleanup with this record.
2. Rerun the focused E2E module against that commit; native WSL transfer remains `NOT_RUN` pending exact S4 private provisioning inputs.
