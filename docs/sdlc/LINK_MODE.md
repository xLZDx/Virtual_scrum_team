# Link mode (VST and AEVE)

Status: both modes exist. `gates` is the default; `router` can be selected since sprint LINK-2.

## The two modes

- `gates` (default, available): VST owns the gates, the receipts and the review loop. This is the U1-U6 scheme and its
  behaviour is unchanged.
- `router` (available): for the five HANDOFF_ASSISTED roles (`implementation-engineer`, `ml-engineer`, `planner`,
  `product-ux-reviewer`, `ux-design-contract`) AEVE builds the task packet (`aeve packet`) and verifies the handoff
  (`aeve verify-handoff`, always with `--root`); VST only carries the request, packet, result and report. The design,
  decisions, failure modes and acceptance criteria are in `docs/sdlc/LINK2_ROUTER_DESIGN.md`.

The state lives in `catalog/link_mode.json` (schema `vst.link_mode.v1`); the code is `tools/vst/link_mode.py`. Nothing
selects router by itself: `mode` in the catalog stays `gates` until someone runs `set router`.

## What router mode does

| Module | Role |
|---|---|
| `tools/vst/router_request.py` | builds the `aeve.task_packet.request.v1` request from a story and validates the packet |
| `tools/vst/router_aeve_cli.py` | pin check (AEVE HEAD equals `aeve_pin.head` of `catalog/role_table.json`, checkout clean), runs `packet` and `verify-handoff`, validates the report, retries only a timeout |
| `tools/vst/router_mode.py` | claim lock, AEVE slots (2), VST-owned copy and hash of the host result, states NEW, AWAITING_RESULT, RESULT_COPIED, DONE, crash recovery, `router.log.jsonl`, sweep |
| `tools/vst/u5_real_change_driver.py` | `stage_router` between apply and review (only when the mode is `router` and `--router-role` is one of the five) |
| `tools/vst/final_package.py` | `router_required`, `router_report`, `router_pin_head`; refuses `ROUTER_NOT_VERIFIED` and `ROUTER_RESULT_DIGEST_MISMATCH` |

The router verdict is necessary, never sufficient. AEVE judges the CLAIMED changes (`basis` =
`CLAIMED_RESULT_NOT_INDEPENDENTLY_DIFFED`), so VST keeps its own diff gate, the review loop and the package checks.

| AEVE status | VST outcome | Effect |
|---|---|---|
| VERIFIED | `ROUTED_VERIFIED` | may proceed to the review loop; READY needs a CLEAN review as well |
| REJECTED | `ROUTED_REJECTED` | story blocked, FAIL checks go to the fix path |
| UNKNOWN | `ROUTED_UNKNOWN` | blocked like REJECTED; never a pass |
| INVALID | `ROUTER_INVALID_INPUT` | blocked, no auto-correction, no retry |

Any contract break (wrong schema, exit code that disagrees with the status, status that differs from the worst check, a
changed pin, a changed result copy, a lock timeout) is a `ROUTER_*` refusal and blocks the story. There is no silent
fallback to `gates`.

## How the flip is guarded

Router availability is pinned in code (`ROUTER_CAPABILITY_READY = True` in `tools/vst/link_mode.py`), not in the data
file. `load` rejects the catalog (`CATALOG_INVALID`) when the file marks router available while the constant is False, and
also when the constant is True and the file still marks router blocked, so a half-reverted flip fails closed. `set router`
is refused with `MODE_UNAVAILABLE` only while the constant is False. To roll back: revert the commit that flipped the
constant together with the catalog entry.

## How to switch

- Read: `python -m tools.vst.link_mode get`
- Set: `python -m tools.vst.link_mode set gates` or `python -m tools.vst.link_mode set router`

Each call prints one JSON line. Exit code 0 is success, 1 is a refusal, 2 is a usage error, 3 is an internal error (`INTERNAL`, no message echoed). Reason codes:
`UNKNOWN_MODE` (name is not `gates` or `router`), `MODE_UNAVAILABLE` (the mode is declared but blocked), `CATALOG_UNREADABLE`,
`CATALOG_INVALID` (bad schema, unknown key, wrong type, duplicate JSON key, lone surrogate, UTF-8 BOM, router availability
that disagrees with the code constant, current mode unknown or unavailable), `WRITE_FAILED`. A refusal never changes the file.
A successful write is atomic (temp file in the same directory, then replace; `replace_with_retry` is exported and also used
for the router work files). The Python API is `load`, `resolve`, `set_mode`. The catalog path is read as given: a symlink or
junction there is followed (acceptable because the CLI path is a repo constant).

## What is NOT done

- AEVE does not judge the quality of model output; VST does not either.
- How the host session receives the packet file is outside this repository: VST writes the packet file and reads the result file.
- AEVE reads packet and result files only up to 64 KiB, VST caps them at 1 MiB; a result between the two comes back as an AEVE
  INVALID answer (`ROUTER_INVALID_INPUT`), not as a VST size refusal.
- No end-to-end run against a real AEVE has been made (see Verification).

## Verification

Tests are written later by the functional-test-reviewer and e2e-runner from the acceptance criteria of
`docs/sdlc/LINK2_ROUTER_DESIGN.md` (section 6). At the time of this commit none was run (NOT_RUN, operator ban); the code is
hand-traced only. `tests/vst/test_link_mode.py` still asserts the old blocked router and must be updated first.
