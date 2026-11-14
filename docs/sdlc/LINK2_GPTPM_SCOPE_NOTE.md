# LINK-2 scope note for the GPT-PM sprint review

Sprint LINK2: VST router mode over AEVE `aeve packet` and `aeve verify-handoff`.
Branch `link2-router-design`, base `origin/main` 1c0db28, AEVE pin 35e5de868edaa37e021955147afb587011ca39c0.
Review head: the commit that adds this note (code head before it: abe12e5).

## What changed

- Design: `docs/sdlc/LINK2_ROUTER_DESIGN.md` (reviewed by architect and reliability-reviewer before any code, 12 MAJOR folded in).
- LINK2-T1 `catalog/role_table.json`: aeve_pin moved from 8a9f6c1 to 35e5de8, table rebuilt.
- LINK2-T2 `tools/vst/router_request.py`: request builder, strict packet validation.
- LINK2-T3A `tools/uc/adapter.py`: generic `run_aeve_command` with a per-command exit table; `run_review` keeps its behaviour. `tools/uc/aeve_probe.py`: `checkout_is_clean`, `checkout_head`.
- LINK2-T3 `tools/vst/router_aeve_cli.py`: wrappers for packet and verify-handoff, pin check, report validation, bounded retry on timeout.
- LINK2-T5 `tools/vst/router_mode.py`: OS-level claim and slot locks, result copy and hash, states NEW / AWAITING_RESULT / RESULT_COPIED / DONE, crash recovery that adopts a verdict only when every digest matches.
- LINK2-T4B `tools/vst/final_package.py`, `tools/vst/u5_real_change_driver.py`: router section in the final package and a router stage in the driver. `review_loop.py` is unchanged.
- LINK2-T6 `tools/vst/link_mode.py`, `catalog/link_mode.json`, `docs/sdlc/LINK_MODE.md`: `ROUTER_CAPABILITY_READY` flipped to True together with the catalog entry. Default mode stays `gates`.
- Fix batches: LINK2-FIX (three defects found by tests: end-of-string anchors, DONE verdict adoption, corrected result after a torn copy), LINK2-FIX2 (findings of four routed reviewers: OS locks instead of age-based claim takeover, router mode blocks without a valid role, package refuses any unverified or foreign router row, Windows reserved task ids, driver exit code).

## Trust boundary and invariants to check

- UNKNOWN, REJECTED, timeout, bad exit, malformed output, digest mismatch and a row for another story must never reach READY.
- AEVE checks CLAIMED changes, not an independent diff (basis CLAIMED_RESULT_NOT_INDEPENDENTLY_DIFFED); VST keeps its own diff gate.
- Gates mode and `run_review` must behave as before.

## Prior review and tests (evidence)

- Routed reviewers (by `.harness-tools/route.py`, risky): code-reviewer, silent-failure-hunter, python-reviewer, reliability-reviewer. No BLOCKER; the accepted MAJOR findings were fixed in f8db548.
- Functional tests were run on named files only, at head abe12e5 (command `C:/Python314/python.exe -m pytest -p no:cacheprovider -q <file>`), results passed/failed/skipped: test_link_mode 74/0/0, test_router_request 172/0/0, test_router_aeve_cli 135/0/0, test_router_mode 98/0/0, test_router_routing 117/0/0, test_router_e2e_real_aeve 6/0/0 (real AEVE at 35e5de8), tests/uc/test_run_aeve_command 11/0/0, test_router 264/0/1, test_adapter 146/0/0, test_aeve_probe 59/0/1, test_role_table 54/0/2.
- Two real-AEVE tests now read the checkout from `AEVE_PIN_CHECKOUT` and skip when it is not at the pin.

## NOT run, not verified

- Full suite, lint, typecheck, CI: prohibited by the operator.
- The POSIX `fcntl` lock branch was never run; only `msvcrt` on Windows was exercised.
- `main()` tests fake every stage except the router decision; `stage_package` handling of router-row errors is not covered by a test.
- The 4 skipped tests in tests/uc were not investigated.
- `release_work_dir` checks the claim and then deletes; a run that starts between the two steps is not covered.
- No end-to-end run of the driver against a real host session result.

## Known limits and backlog (design doc section 8)

- AEVE reads packet and result files only up to 64 KiB while VST caps them at 1 MiB: a file between the two returns ROUTER_INVALID_INPUT.
- Descendants of the AEVE process tree are not confirmed dead (tree_dead checks the root only).
- `router.log.jsonl` has no rotation or append lock.
- A torn `state.json` is treated as NEW and loses recorded digests (the verdict is re-verified, so it cannot become a false VERIFIED).
- The pre-commit report step fails on an unrelated ledger status of task U6-2 ("ACCEPTED as NOT_RUN measurement"); it never blocked a commit.
