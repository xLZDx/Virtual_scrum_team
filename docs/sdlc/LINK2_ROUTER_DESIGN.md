# LINK-2 design: router mode (VST routes AEVE task packets and handoff reports)

Status: design for sprint LINK-2, revision 2 (after architect and reliability review), written before
implementation. Nothing here is implemented. Until the reviewed implementation lands, `ROUTER_CAPABILITY_READY` stays
`False` (`tools/vst/link_mode.py` line 49).

## 1. Goal and non-goals

Goal: make `router` mode of `catalog/link_mode.json` selectable. For the AEVE class HANDOFF_ASSISTED, AEVE builds the
task packet and verifies the handoff and VST only carries the request, packet, result and report. AEVE README (origin/main
`35e5de8`, line 54): HANDOFF_ASSISTED is "an intentional scope boundary: authoring or judgment roles that a zero-model
engine cannot reproduce", and its five roles are `implementation-engineer`, `ml-engineer`, `planner`,
`product-ux-reviewer`, `ux-design-contract`. The role set is an explicit input of LINK2-T2 (a constant tuple),
confirmed in T1 against the rebuilt `catalog/role_table.json`; a mismatch fails T1.

Non-goals (decided):
- AEVE does not judge the quality of model output (README: "never judged or guaranteed"; AGENT_CLI.md `verify-handoff`).
- The AEVE basis is the CLAIMED changes: the report carries `basis` = `CLAIMED_RESULT_NOT_INDEPENDENTLY_DIFFED`.
  VST keeps its own diff gate (`worker_gate.gate_worker_change`, used by `review_loop`) and the final package diff checks
  (`DIFF_HASH_MISMATCH`, `PATHS_UNDERSTATED`, `PATHS_EXTRA` in `tools/vst/final_package.py`). Router never replaces them.
- No in-process import of AEVE, no model call by VST, no change to `gates` mode, router is not the default (`mode` stays
  `gates`), no change to the AEVE repository.

## 2. Facts read

VST side:
- `tools/vst/link_mode.py`: `ROUTER_BLOCKED_REASON`, `ROUTER_REQUIRES` (lines 47-51); `_parse` line 171 rejects an
  available router while READY is False; `_parse_entry` line 149 pins a blocked router's `blocked_reason`/`requires`;
  `set_mode` line 238 refuses router. `_replace_with_retry` (line 205) retries winerror 5/32. Nothing in `tools/vst`
  reads the mode (`grep link_mode tools`: only `link_mode.py` itself and `tools/qa/build_registry.py`).
- `catalog/role_table.json`: `aeve_pin.head` `8a9f6c1a684e03eac252b285a96a11d363dbc9e6`, `matrix_digest_sha256`
  `9822b853...7561`. Gate refusals `ROLE_TABLE_DRIFT`, `AEVE_HEAD_DRIFT` (`docs/sdlc/u6/RUNBOOK.md` item 1);
  `role_table.py` line 126: "pin: AEVE head differs from the probed checkout".
- `tools/uc/aeve_probe.py`: child launch `python -P -s -B -m aeve`, `shell=False`, minimal env. `_checkout_state` (line 101)
  lists tracked and untracked lines, but the record separates them (`untracked_paths`, line 198), so its notion of
  "dirty" is not "any change"; it is not reused as is.
- `tools/uc/adapter.py`: `DEFAULT_TIMEOUT_SECONDS = 120.0` (line 31), `DEFAULT_STDOUT_CAP` 8 MiB (32),
  `OK_EXIT_CODES = (0, 3)` (34), argv hard-wired `"review"` (155), exit check (198), tree kill, `command_prefix` for tests.
- `tools/vst/review_loop.py`: `Judgement.verdict` is CLEAN, FINDINGS, PARTIAL or BLOCKED (line 232); the loop's final
  `ReviewLoopResult` is CLEAN or BLOCKED; `run_review_loop(state, story_id, *, epoch, attempt_no, initial_head, ...)`
  (line 947); step ids `rl-a<attempt>-i<index>`.
- `tools/vst/final_package.py`: `build_final_package(*, story_id, base_head, head, diff_bytes, ..., review_results,
  receipts, isolation_proof, ...)` (line 616); `_review_section` accepts only CLEAN or BLOCKED.
- Only caller of both: `tools/vst/u5_real_change_driver.py` (stages `stage_review` line 118, `stage_package` line 195).

AEVE side (`git show origin/main:...`, head `35e5de868edaa37e021955147afb587011ca39c0`):
- `aeve packet --request FILE`: input `aeve.task_packet.request.v1`; output `aeve.task_packet.v1` COMPLETE (with
  `request_sha256`, `scope`, `files`, `acceptance` ids `AC-n`, `risks`, `llm_calls` 0, `executed_project_code` false,
  `source_modified` false) or INVALID with `reason`. Exit 0 on COMPLETE, otherwise 3.
- `request_sha256` is SHA-256 of `json.dumps(request, ensure_ascii=True, sort_keys=True, separators=(",", ":"))`
  (`src/aeve/governance/task_packet.py:218`), i.e. of the parsed request object, NOT the raw file bytes. Whether `request`
  is normalised before that line was not verified. Decision: VST does not recompute it and does not depend on it; VST
  stores it as an opaque value and only checks that the same request gives the same value (determinism).
- `aeve verify-handoff --packet FILE --result FILE [--root DIR]`: output `aeve.handoff_verify.v1`, `status` VERIFIED,
  REJECTED, UNKNOWN or INVALID, `checks[]` ids `CHANGES_INSIDE_SCOPE`, `EVIDENCE_DOCUMENTS_EXIST`, `FORBIDDEN_UNTOUCHED`,
  `TASK_ID_MATCH`, `TESTS_FOR_LOGIC`, each PASS/FAIL/UNKNOWN. Exit 0/1/2/3. Without `--root` the evidence check is UNKNOWN.

## 3. Decisions

### D1. Bump `aeve_pin` to `35e5de868edaa37e021955147afb587011ca39c0` (LINK2-T1, own commit, no router code)
Re-check in order: (1) AEVE checkout at that head, clean (definition in D5); (2) `tools/uc/aeve_probe.py --aeve-root <AEVE>`;
(3) `role_table.py validate ...` (command in `docs/sdlc/u6/RUNBOOK.md`), then `build` because the matrix digest will change
(README line 21: five roles PARTIAL through handoff); review the diff of every entry and confirm the five-role set of
section 1; (4) re-point tests that fix the old head or digest (`tests/uc/test_router.py::test_review_aeve_pin_mismatch_head_and_digest`,
`tests/uc/test_u2_result_bridge.py`, `tests/vst/u5_e2e_support.py`). Rollback: revert the commit.

### D2. Router flow (module `tools/vst/router_mode.py`)
Caller and trigger: `tools/vst/u5_real_change_driver.py` is the only driver of the review loop and package today. T4b adds a
stage `stage_router` between apply and review. It runs only when `link_mode.resolve().mode == "router"` AND the story's role is
one of the five; otherwise the stage is skipped and `gates` flow is byte-for-byte unchanged. `router_mode` also refuses
(`ROUTER_NOT_SELECTED`) when called while the mode is not `router`.

Steps per task:
1. Build the request (`aeve.task_packet.request.v1`) from the story: canonical JSON, sorted keys, LF. `task_id` must match
   `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` or `ROUTER_BAD_REQUEST` before any call.
2. Claim (D4), then pin check: AEVE HEAD equals `aeve_pin.head` and the checkout is clean, else `ROUTER_PIN_DRIFT`.
3. `aeve packet` via the generic runner (T3a). Validate the packet: `schema_version`, `status` COMPLETE, `role` and `task_id`
   equal the request, guards (`llm_calls` 0, `executed_project_code` false, `source_modified` false). Size cap D6.
4. Record the packet (row `rt-a<attempt>-packet`, state AWAITING_RESULT) and hand the packet file to the host session.
5. Result intake: copy the host result into the VST-owned work directory, hash THE COPY, run everything on the copy only.
6. `aeve verify-handoff --packet <copy> --result <result copy> --root <worktree>` (always with `--root`).
7. Report checks (all else is `ROUTER_BAD_OUTPUT`): schema `aeve.handoff_verify.v1`, guards, `basis` claimed-result value,
   `task_id` equal, and status equals the worst of `checks[]` (any FAIL gives REJECTED, else any UNKNOWN gives UNKNOWN,
   else VERIFIED; INVALID has no checks). VERIFIED with any UNKNOWN or FAIL check is `ROUTER_BAD_OUTPUT`. Exit code and
   status must agree (0 VERIFIED, 1 REJECTED, 2 UNKNOWN, 3 INVALID) or `ROUTER_BAD_EXIT`.
8. Route the report without re-deciding it (stored unmodified, digest in the row):

| AEVE status | VST outcome | Effect |
|---|---|---|
| VERIFIED | `ROUTED_VERIFIED` | necessary, never sufficient: diff gate and a CLEAN review loop are still required |
| REJECTED | `ROUTED_REJECTED` | story blocked; FAIL check ids and paths go to the caller's fix path as text |
| UNKNOWN | `ROUTED_UNKNOWN` | story blocked exactly like REJECTED; never a pass; unknown checks listed |
| INVALID (exit 3) | `ROUTER_INVALID_INPUT` | blocked; `reason` stored; no auto-correction, no auto-retry |

Pinned insertion points (from the signatures read; T4a confirms them by reading the bodies and amends this section if a
body contradicts them):
- `review_loop.py`: NO change. The router outcome is a precondition checked by `stage_router` before `run_review_loop` is
  called. If the outcome is not `ROUTED_VERIFIED` the driver does not call the loop for that attempt. (`Judgement`
  verdicts FINDINGS and PARTIAL and the final CLEAN/BLOCKED stay as they are.)
- `final_package.py`: `build_final_package` gets two keyword-only parameters, `router_required: bool = False` and
  `router_report: Mapping[str, Any] | None = None` (row fields: `outcome`, `status`, `task_id`, `request_sha256`,
  `packet_sha256`, `result_sha256`, `report_sha256`, `pin_head`). A new `_router_section` runs after `_review_section` in
  `_build`. With `router_required` True it refuses with `ROUTER_NOT_VERIFIED` unless outcome is `ROUTED_VERIFIED` and
  `pin_head` equals the expected pin; a recomputed result digest that differs gives `ROUTER_RESULT_DIGEST_MISMATCH`.
  Defaults keep every existing caller unchanged.

### D3. Flip of `ROUTER_CAPABILITY_READY` (LINK2-T6)
T6 is the LAST implementation commit of the sprint branch. The sprint's tests, reviewers and the GPT-PM round run on that
HEAD; approval is bound to it, and any later fix commit needs re-approval. The push happens only after APPROVE. T6 contains,
together: `ROUTER_CAPABILITY_READY = True`; removal of `ROUTER_BLOCKED_REASON` and `ROUTER_REQUIRES`; the catalog router
entry becomes `{"available": true, "description": ...}` (`_AVAILABLE_KEYS`) with `mode` still `gates`; `load()`: line 149
pinned-values rule dropped, line 171 kept, new rule "READY True with a blocked router entry is `CATALOG_INVALID`";
`set_mode` line 238 refuses router only while READY is False. `LINK_MODE.md` is rewritten at close. A flip missing any
part is a defect. Rollback: revert T6; a half-reverted state fails closed in `load`.

### D4. Concurrency, claim and resume
- Work directory: `<state_root>/router/<task_id>/<request_sha256[:16]>-<result_sha256[:16] or "pending">/`.
- Exclusive claim before any AEVE call: `claim.lock` created with `os.open(O_CREAT|O_EXCL)`, content `{owner, created_at}`
  (owner = random token, not a pid; `os.kill(pid,0)` is not a liveness probe on Windows). A claim older than 600 s (chosen
  default) is stale: the taker renames it to a unique name (atomic) and then creates its own claim; the takeover is logged.
  Lock wait is bounded (60 s, poll 0.5 s); expiry is `ROUTER_LOCK_TIMEOUT`.
- Cap on concurrent AEVE subprocesses: 2 (chosen default), counted by slot lock files taken with the same O_EXCL rule;
  waiting is bounded and ends in `ROUTER_LOCK_TIMEOUT`.
- States: NEW, AWAITING_RESULT (packet recorded, result absent: a normal wait, no AEVE call, not an error), RESULT_COPIED,
  DONE (verdict recorded). A crash is recognised only by a stale claim plus a state older than the recorded step.
- Adoption on resume: a recorded verdict is adopted only if the row, report digest, packet digest, result digest AND pin head
  all match the files and the current pin; otherwise `verify-handoff` is re-run (read-only). Every resume logs `adopted`
  or `rerun`.

### D5. Definitions, timeouts, files
- Clean checkout: `git status --porcelain --untracked-files=all` is empty (no tracked change AND no untracked file; ignored
  files are not listed). New helper `aeve_probe.checkout_is_clean(aeve_root)` (T3a), used by the pin check; `_checkout_state`
  is untouched.
- Timeout: 120 s per AEVE command (chosen default, equal to `adapter.DEFAULT_TIMEOUT_SECONDS`, configurable). Retry only on
  `ROUTER_TIMEOUT`: at most 2 retries, jitter 0.5-2 s, and only after the child process tree is confirmed dead (adapter kill
  plus wait); if it is not confirmed dead there is no retry. No retry for any other code.
- Atomic writes: temp file in the same directory, flush, fsync, `os.replace` through the existing
  `link_mode._replace_with_retry` (exported as public `replace_with_retry`, no behaviour change). At the start of each run
  `*.tmp` files older than 1 h in the router work root are removed.
- Size caps (chosen defaults): packet 1 MiB, host result 1 MiB (copy refuses larger: `ROUTER_SIZE_CAP`), AEVE stdout 1 MiB.
- Retention: a work directory is deleted after the story's final package is built; BLOCKED directories after 14 days;
  deletion touches only directories under `<state_root>/router/`.
- Observability: one JSON line per step in `router.log.jsonl` with `task_id`, `request_sha256`, `step`, `outcome`,
  `retry_count`, `resume` (`adopted`/`rerun`/`none`), `claim_takeover`. No packet, result or env content, no secrets.

### D6. Failure modes (reason codes)

| Case | Behaviour |
|---|---|
| AEVE missing or not runnable | `ROUTER_AEVE_MISSING`, BLOCKED; no silent fallback to `gates` |
| Pin or clean-checkout mismatch | `ROUTER_PIN_DRIFT` before any AEVE call |
| `packet` exit 3 / INVALID | `ROUTER_PACKET_INVALID` (AEVE reason truncated, ASCII-escaped) |
| `verify-handoff` exit 3 | `ROUTER_INVALID_INPUT`, no retry |
| Timeout / stdout cap | tree killed; `ROUTER_TIMEOUT` (retry per D5); `ROUTER_SIZE_CAP` for caps |
| Malformed JSON, duplicate keys, wrong schema, guards, status vs checks | `ROUTER_BAD_OUTPUT`; unknown exit or mismatch `ROUTER_BAD_EXIT` |
| Two concurrent requests | claim D4; the loser waits, then adopts the recorded row, or `ROUTER_LOCK_TIMEOUT` |
| Retry | safe: both commands report `source_modified` false and are deterministic |
| Crash half-way | resume per D4; torn file fails parse; no file is trusted without a matching digest |
| Result changed after verify | `ROUTER_RESULT_DIGEST_MISMATCH` (own code; `STALE_EVIDENCE` is not reused) |

## 4. Rejected options
- Import `aeve` in process: couples to AEVE internals, loses the clean env and tree kill. Rejected.
- VST re-implements scope checks and uses AEVE only for the packet: two verdicts. Rejected.
- UNKNOWN as soft pass: hides an unestablished fact. Rejected.
- Omit `--root`: evidence check UNKNOWN by omission, never VERIFIED.
- Router availability from the JSON file: already rejected in `link_mode.py`.
- Silent fallback to `gates` when AEVE fails: changes who owns the gates; explicit `set gates` only.
- Verify the host's original result path: the file can change between check and use; the VST-owned copy is hashed instead.
- Pid-based lock liveness: unreliable on Windows; owner token plus age is used.
- Change `run_review_loop` to take the router outcome: widens a settled module; a precondition in the driver is enough.
- Recompute AEVE's `request_sha256` in VST: depends on an unverified AEVE normalisation.

## 5. Tasks and acceptance criteria (Given/When/Then)
Order by dependency, flip last: T1, T2, T3a, T3b, T4a, T4b, T5, T6.

**T1 pin bump.** AC-1: new pin, validate against `35e5de8` gives `status: VALID` with head `35e5de868edaa37e021955147afb587011ca39c0`.
AC-2: another head gives exit 1 with "pin: AEVE head differs from the probed checkout". AC-3: the rebuilt table's five
HANDOFF_ASSISTED roles equal the T2 constant tuple.

**T2 request builder and packet validation.** AC-4: same story twice gives identical bytes. AC-5: bad `task_id` or empty
`acceptance` gives `ROUTER_BAD_REQUEST`, no process started. AC-6: packet with another role/task_id or `llm_calls` not 0
gives `ROUTER_PACKET_INVALID`. AC-7: packet over 1 MiB gives `ROUTER_SIZE_CAP`.

**T3a generic AEVE runner (extract from `adapter.run_review`).** `run_aeve_command(command, args, ..., ok_exit_codes)` with a
per-command table: review (0,3), packet (0,3), verify-handoff (0,1,2,3); `run_review` becomes a caller. Also
`aeve_probe.checkout_is_clean`. AC-8: `run_review` argv is still `[*prefix, "review", "--request", path]` and exit 0/3 are accepted,
any other exit gives `AEVE_EXIT`. AC-9: `TIMEOUT`, `OUTPUT_TOO_LARGE`, `BAD_OUTPUT`, `check_response` behave as before
(`tests/uc/test_adapter.py`, `tests/uc/test_router.py` unchanged and green). AC-10: `packet` exit 1 gives `AEVE_EXIT`;
`verify-handoff` exits 0,1,2,3 are accepted and 4 gives `AEVE_EXIT`. AC-11: `checkout_is_clean` is False for one untracked file
and for one tracked change, True for an empty status.

**T3b router CLI use.** AC-12: fake AEVE sleeping past 120 s (injected small timeout) gives `ROUTER_TIMEOUT`, process tree dead,
at most 2 retries. AC-13: exit 0 with REJECTED, or exit 1 with VERIFIED gives `ROUTER_BAD_EXIT`. AC-14: stdout not JSON, duplicate
keys or a list gives `ROUTER_BAD_OUTPUT`. AC-15: unknown executable gives `ROUTER_AEVE_MISSING`; head or cleanliness mismatch gives
`ROUTER_PIN_DRIFT` with no AEVE call. AC-16: VERIFIED with one UNKNOWN or FAIL check gives `ROUTER_BAD_OUTPUT`; REJECTED
without a FAIL check gives `ROUTER_BAD_OUTPUT`. AC-17 (forced failure of the timeout path): a hanging fake that ignores the
first kill signal gives no retry and a BLOCKED row.

**T4a pin the contracts.** Read the bodies of `review_loop.py` and `final_package.py`, confirm or amend the insertion points
and row fields of D2 in this document before T4b starts. AC-18: the document names exact function, parameter and field names
and no "about N lines".

**T4b routing and caller.** AC-19: for router outcome x judgement verdict, READY is reachable only for `ROUTED_VERIFIED` with
CLEAN; the full matrix {VERIFIED, REJECTED, UNKNOWN, INVALID} x {CLEAN, FINDINGS, PARTIAL, BLOCKED} is asserted, every other cell is
BLOCKED or not reached. AC-20: UNKNOWN never produces READY in any cell. AC-21: `router_required` True with no row gives
`ROUTER_NOT_VERIFIED`; `router_required` False leaves the package byte-identical to today. AC-22: mode `gates` makes no
`packet` or `verify-handoff` call and skips `stage_router`. AC-23: mode `router` with a non-HANDOFF_ASSISTED role skips
`stage_router`.

**T5 state and concurrency.** AC-24: two concurrent runs of one task call AEVE once per command and return the same row.
AC-25: stale claim (older than 600 s) is taken over and logged; a fresh claim makes the second caller wait, then
`ROUTER_LOCK_TIMEOUT`. AC-26: crash after `packet` and before `verify` resumes in AWAITING_RESULT or verifies once, never re-runs
`packet` for a recorded step. AC-27: result file altered after copy gives `ROUTER_RESULT_DIGEST_MISMATCH`; the host's original file
is never passed to AEVE. AC-28: a row whose pin head, or any digest, differs is re-verified and logged `rerun`; a matching row is
logged `adopted`. AC-29: torn result gives `ROUTER_BAD_OUTPUT`. AC-30: third concurrent AEVE call waits on the 2-slot cap.
AC-31: stale `*.tmp` older than 1 h is swept; a BLOCKED directory older than 14 days is removed; nothing outside
`<state_root>/router/` is touched. AC-32: each step writes one log line with the D5 fields and no result content.

**T6 flip (last implementation commit).** AC-33: `link_mode set router` succeeds and `get` reports router available.
AC-34: READY True with a blocked router entry gives `CATALOG_INVALID`. AC-35: READY False with an available router gives
`CATALOG_INVALID` (existing rule kept). AC-36: catalog default `mode` is still `gates`.

## 6. Test list (written later by `functional-test-reviewer`; NOT run now; run once, named files, when the stories are coded)
- `tests/uc/test_role_table.py`, `tests/uc/test_aeve_probe.py`: AC-1 to AC-3, AC-11.
- `tests/vst/test_router_request.py`: AC-4 to AC-7.
- `tests/uc/test_adapter.py`, `tests/uc/test_router.py` (existing, extended): AC-8 to AC-10.
- `tests/vst/test_router_aeve_cli.py`: AC-12 to AC-17 (fake AEVE through `command_prefix`; AC-17 is the forced-failure case).
- `tests/vst/test_router_routing.py`: AC-19 to AC-23.
- `tests/vst/test_router_state.py`: AC-24 to AC-32.
- `tests/vst/test_link_mode.py` (extend): AC-33 to AC-36.
- `tests/vst/test_router_e2e_real_aeve.py` (e2e-runner, real AEVE at the pin): VERIFIED, REJECTED, UNKNOWN, INVALID using
  AEVE `tests/fixtures/handoff_verify/{verified,rejected,unknown,invalid}.result.json` with `packet.json`; expected values
  from the matching `*.expected.json`.
No suite, lint, typecheck or CI run.

## 7. Unknowns
- Whether AEVE normalises the request before hashing: not verified; VST does not depend on it (owner T2 re-reads if needed).
- How the host session receives the packet (path in prompt or MCP): out of scope; VST writes the packet file and reads the
  result file.
- Chosen defaults (120 s, 600 s claim age, 60 s lock wait, 2 slots, 1 MiB caps, 14 days): owner T3b/T5 may adjust with a
  recorded reason; they are configuration, not contracts.
