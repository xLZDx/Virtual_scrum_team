# Link mode (VST and AEVE)

Status: skeleton. Only the mode declaration and the switch exist.

## The two modes

- `gates` (default, available): VST owns the gates, the receipts and the review loop. This is the current
  U1-U6 scheme.
- `router` (declared, NOT available): AEVE does the checks and VST only routes AEVE reports to sessions and
  reviewers. No router behaviour exists in this repository.

The state lives in `catalog/link_mode.json` (schema `vst.link_mode.v1`); the code is `tools/vst/link_mode.py`.

## Why router is blocked

The catalog entry carries `blocked_reason` = `ROUTER_REQUIRES_AEVE_TASK_PACKET_AND_HANDOFF_VERIFIER`. It needs two
AEVE tasks of sprint S20, both NOT_STARTED in AEVE when this was written:

- AEVE S20-T07: the task packet.
- AEVE S20-T08: the handoff verifier.

Router availability is pinned in code (`ROUTER_CAPABILITY_READY = False` in `tools/vst/link_mode.py`), not in the
data file. A hand edit of the JSON that marks router available, or that changes its `blocked_reason` or `requires`, is
rejected by `load` (`CATALOG_INVALID`). The constant flips only together with the reviewed router implementation,
after both AEVE tasks exist. `set router` is refused with `MODE_UNAVAILABLE` before the file is even read.

## How to switch

- Read: `python -m tools.vst.link_mode get`
- Set: `python -m tools.vst.link_mode set gates`

Each call prints one JSON line. Exit code 0 is success, 1 is a refusal, 2 is a usage error, 3 is an internal error (`INTERNAL`, no message echoed). Reason codes:
`UNKNOWN_MODE` (name is not `gates` or `router`), `MODE_UNAVAILABLE` (the mode is declared but blocked; `set router`
gives this), `CATALOG_UNREADABLE`, `CATALOG_INVALID` (bad schema, unknown key, wrong type, duplicate JSON key, lone surrogate,
UTF-8 BOM, router marked available, current mode unknown or unavailable), `WRITE_FAILED`. A refusal never changes the file. A successful write is
atomic (temp file in the same directory, then replace). The Python API is `load`, `resolve`, `set_mode`. The catalog path is read as given: a symlink or junction there is
followed (acceptable because the CLI path is a repo constant).

## What is NOT done

- Router behaviour of any kind.
- Any integration with the review loop (`tools/vst/review_loop.py`) or the final package
  (`tools/vst/final_package.py`): nothing reads the mode yet, so the switch changes no VST behaviour.
- Any call into AEVE.

## Verification

Tests are in `tests/vst/test_link_mode.py`, written by the functional-test-reviewer from the acceptance criteria and hand-traced against the code. None was run (NOT_RUN, operator ban), and the Windows retry behaviour is simulated, not observed.
