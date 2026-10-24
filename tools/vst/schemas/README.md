# VST control-plane contracts (human-readable schema)

Implemented in `tools/vst/contracts.py`, `tools/vst/signing.py`, `tools/vst/gate.py`. Standard library only. All validators require the EXACT key set (missing and unknown fields are rejected), have no defaults, never accept `bool` as `int`, and return a deep copy. Violations raise `ContractError` (a `ValueError`) naming the field.

Closed enums: `RESULT` = PASS, FAIL, BLOCKED, NOT_RUN, INCONCLUSIVE. `COVERAGE` = FULL, PARTIAL, NOT_COVERED. `VERDICT` = APPROVE, APPROVED_WITH_WAIVER, MODIFY, NO_GO. `RECEIPT_TYPES` = TestRun, StaticAnalysis, IndependentReview, Documentation. Hashes are lowercase hex (head = 40 chars, sha256 = 64). Dates are opaque non-empty strings.

## TaskManifest (`validate_task_manifest`)

| Field | Type / rule |
|---|---|
| task_id, project_id, story_id, owner_role, model_policy | non-empty str |
| phase | int 1..10 |
| base_head | 40 hex |
| scope | non-empty list of unique repo-relative paths: no absolute path, no leading `/` or `\`, no `:`, no empty / `.` / `..` segments |
| forbidden_actions, tools | list of unique non-empty str (may be empty) |
| role_sha256 | 64 hex |
| skills | list of `{id: non-empty str, sha256: 64 hex}`, unique ids (may be empty) |
| acceptance | non-empty list of unique non-empty str ids |
| required_receipts | non-empty list of `{slot: unique non-empty str, receipt_type: RECEIPT_TYPES}` |
| timeout_sec | int > 0 |
| cost_cap, retry_cap | int >= 0 |

## Receipt (`validate_receipt`)

Common fields: `receipt_id`, `task_id`, `slot` (matches a manifest slot), `runner_id`, `resolved_model`, `invocation_id`, `created_at` are non-empty str; `receipt_type` in RECEIPT_TYPES; `attempt` int >= 1; `prev_receipt_sha256` is null iff attempt == 1, else 64 hex; `candidate_head` 40 hex; `epoch` int >= 1; `role_sha256` 64 hex; `result` in RESULT; `signature` 64 hex.

Per type (lists contain non-empty str unless stated):

- TestRun: `expected_test_ids`, `executed_test_ids`, `skipped_test_ids`, `xfail_test_ids`, `covered_acceptance`; `commands` = non-empty list of `{argv: non-empty list of str, exit_code: int}`; `artifact_digests` (REQUIRED, may be empty) = dict mapping a non-empty path str to a 64-hex sha256 of that artifact as it was after the commands ran. The all-zero digest (`MISSING_ARTIFACT_DIGEST`, 64 zeros) means "artifact missing after the run".
- StaticAnalysis: `coverage` in COVERAGE; `covered_rules`, `unsupported_rules`, `covered_acceptance`.
- IndependentReview: `reviewer_principal`, `author_principal` (non-empty str); `covered_acceptance`, `findings`; `signed_verdict` in {MODIFY, NO_GO, APPROVE}.
- Documentation: `check_description` non-empty str; `covered_acceptance`.

## derive_result (what `result` MUST be)

- TestRun: FAIL if `artifact_digests` contains the all-zero digest (checked first); otherwise INCONCLUSIVE if `executed_test_ids` is empty; PASS only if every `exit_code == 0`, `expected_test_ids` non-empty, set(executed) == set(expected), and `skipped_test_ids` and `xfail_test_ids` are empty; otherwise FAIL.
- StaticAnalysis: PASS only if `coverage == FULL` and `unsupported_rules` is empty; otherwise INCONCLUSIVE.
- IndependentReview: PASS only if `signed_verdict == APPROVE` and `reviewer_principal != author_principal`; otherwise FAIL.
- Documentation: the given `result` if it is PASS or FAIL; otherwise INCONCLUSIVE.
- Rule for every receipt type, applied first: a given `result` of BLOCKED, INCONCLUSIVE or NOT_RUN is accepted as given (`NON_APPROVING_RESULTS`). These results can never produce an approval (the gate treats any non-PASS latest attempt as an unmet slot), and the supervisor must be able to write INCONCLUSIVE(WORKER_LOST), BLOCKED(RETRY_EXHAUSTED) and BLOCKED(budget) receipts. A given PASS or FAIL is still compared with the computed value.
- Reason codes: receipts have closed fields, so there is no `reason` field. Supervisor receipts are of type Documentation and carry the reason code in `check_description` (`WORKER_LOST`, `RETRY_EXHAUSTED`, `BUDGET_EXCEEDED`).

The gate treats a receipt whose `result != derive_result(receipt)` as invalid.

## Canonical form and signature

`canonical_bytes(obj)` = `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)` encoded as UTF-8. `receipt_sha256(receipt)` = sha256 hex of the canonical bytes of the FULL receipt including `signature`. `signing.sign(receipt_without_signature, key)` = HMAC-SHA256 hex over the canonical bytes; `signing.verify(receipt, key)` recomputes over the receipt minus `signature` and compares with `hmac.compare_digest`. Key must be non-empty bytes, else `ContractError`.

## GateDecision (`validate_gate_decision`)

`task_id` str, `candidate_head` str (echoes of gate inputs, so that NO_GO can be emitted for malformed inputs), `epoch` int >= 0, `required_receipt_hashes` list of 64 hex, `unresolved_findings` / `human_approvals` / `acceptance_unmet` / `reasons` lists of non-empty str, `verdict` in VERDICT, `waiver_record` non-empty str iff verdict is APPROVED_WITH_WAIVER, else null. APPROVE additionally requires empty `reasons` and `acceptance_unmet`.

## Store (`tools/vst/store.py`)

`Store(path, clock=time.time)`: one sqlite3 connection per instance, WAL, foreign keys on, autocommit with an explicit `BEGIN IMMEDIATE` per mutating method (each public method is atomic). Context manager closes the connection. `StoreError(message, kind)`; kinds: story, epoch, lease, slot, chain, duplicate, budget, argument, append_only.

Tables: `stories(story_id, project_id, phase, epoch, owner, state, owner_expires_at)`, `leases(task_id, story_id, attempt, worker_id, epoch, expires_at, released, marked)`, `slots(slot_no, task_id, worker_id, expires_at)`, `receipts(seq, receipt_id UNIQUE, story_id, task_id, slot, attempt, epoch, receipt_sha256, prev_receipt_sha256, body, UNIQUE(task_id, slot, attempt))`, `events(seq, ts, task_id, actor, kind, payload, prev_hash, hash)`, `budget(task_id, cap, spent)`. Columns beyond the minimal design: `owner_expires_at` (owner liveness), `marked` (supervisor receipt already written), `receipts.story_id` (story view).

- Append-only: triggers `RAISE(ABORT)` on UPDATE and DELETE of `receipts` and `events`.
- Epoch: `open_story` starts at epoch 1 with no owner. `acquire_epoch(story_id, owner, ttl_sec=3600)` is a compare-and-swap: it bumps the epoch and returns it only when no live owner (`owner_expires_at` in the future) holds the story, otherwise `StoreError(kind='epoch')`. Winning fences the previous epoch's live leases (`released = 2`, slots freed). Lease operations and `append_receipt` must carry the current epoch.
- Lease and slot: `acquire_lease` takes a free `slots` row in the same transaction; it fails for a stale epoch, no free slot, a live lease, a non-increasing attempt, or a previous attempt that was lost and not yet marked by the supervisor. `leases.released`: 0 live, 1 released by the worker, 2 reaped on expiry or fenced. `heartbeat` rejects expired, foreign or stale-epoch callers.
- Receipts: `append_receipt` validates, requires `epoch` == current story epoch, attempt == last attempt + 1 per `(task_id, slot)` and `prev_receipt_sha256` == previous receipt hash; body is stored as canonical JSON.
- Events: `hash = sha256(prev_hash + canonical JSON of {ts, task_id, actor, kind, payload})`, first `prev_hash` is 64 zeros; `verify_event_chain` recomputes the chain.
- Budget: `charge` never lets `spent` exceed `cap`; on overflow it commits a `BUDGET_EXCEEDED` event and raises `StoreError(kind='budget')` without charging.
- Supervisor receipts: `supervisor_reap_and_mark(manifest_lookup, key, runner_id)` writes, for each reaped lease with no receipt for its `(task_id, attempt)`, a signed Documentation receipt with result INCONCLUSIVE and `check_description` `WORKER_LOST`; when the lease attempt exceeds `retry_cap + 1` the result is BLOCKED and the description `RETRY_EXHAUSTED`. Slot rule: the first `required_receipts` entry of type Documentation, else the first entry. Attempt = next in that slot's chain; epoch = current story epoch; `candidate_head` = head of the task's latest receipt, else manifest `base_head`.
- Append-only errors: inside any Store transaction a `sqlite3.IntegrityError` raised by the append-only triggers is re-raised as `StoreError(kind='append_only')`. No Store method mutates receipts or events; tests attempt UPDATE/DELETE with raw sqlite3 on the database file and expect the raw trigger error.
- `mark_budget_exceeded(task_id, story_id, manifest, key, runner_id) -> dict`: validates the manifest (its `task_id` must equal `task_id`, else `StoreError(kind='argument')`), then writes a signed supervisor Documentation receipt with result BLOCKED and `check_description` `BUDGET_EXCEEDED` using the same slot, attempt, epoch and `candidate_head` rules as `supervisor_reap_and_mark`, and records a `BUDGET_BLOCKED` event. Returns the receipt.
- `renew_epoch(story_id, owner, ttl_sec) -> None`: only the recorded owner whose ownership is still live may extend `owner_expires_at`; anyone else, or an expired owner, gets `StoreError(kind='epoch')`. The epoch number is unchanged.
- `release_epoch(story_id, owner) -> None`: only the recorded owner may clear ownership (epoch number kept, state OPEN); otherwise `StoreError(kind='epoch')`. The next `acquire_epoch` then succeeds and bumps the epoch.
- `render_state_md(story_id)`: deterministic markdown view, first line states it is a generated view that must not be edited.

## Runner (`tools/vst/runner.py`)

`run_and_sign(...)` first validates EVERY receipt-level input (non-empty str ids, attempt >= 1, epoch >= 1, hex lengths of `candidate_head` / `role_sha256` / `prev_receipt_sha256` (null iff attempt == 1), non-empty bytes key, non-empty commands, list `expected_test_ids` / `covered_acceptance` / `artifact_paths`, `timeout_sec` > 0, str `cwd`, callable parser) and raises `ContractError` before any subprocess starts. A cwd that does not exist is not a validation error. It then runs each argv with `subprocess.run` (no shell, captured text output, timeout, cwd), records `argv` and `exit_code` (-1 timeout; -2 for a missing executable, a missing or invalid cwd, a permission error or any other `OSError` starting the process; non-OSError exceptions propagate), joins stdout, calls the injected parser to get `(executed, skipped, xfail)`, builds a TestRun receipt, sets `result = derive_result(receipt)`, signs it with `signing.sign`, validates it and returns it. The new required keyword `artifact_paths: list[str]` (may be empty) lists artifacts produced by the commands; they are hashed AFTER the commands ran (relative paths resolve against `cwd`, the path string as given is the key in `artifact_digests`). An artifact that cannot be read after the run is recorded with the all-zero digest and the derived result is FAIL. An empty commands list raises `ContractError`. The key is a plain argument: never written, logged or read from the worker cwd. Helpers: `file_sha256(path)` (64 KiB chunks) and `artifact_digests(paths)`.

## Slice harness (`tools/vst/slice.py`)

Synthetic vertical slice: no real project, no process spawning, no network. `build_synthetic_manifest(task_id, base_head)` returns a valid manifest with slots `tests` (TestRun), `static` (StaticAnalysis), `review` (IndependentReview), acceptance `AC-1`, `AC-2`, `retry_cap` 1. `SliceFixture(workdir, key, clock)` creates `workdir/state.db` (2 slots, story `story-1`, epoch acquired) and builds signed receipts directly (`make_test_receipt`, `make_static_receipt`, `make_review_receipt`; expected test ids `t1`, `t2`; `current_head` is a fixed 40-hex string). `gate(receipts=None, waiver=None)` evaluates with receipts read from the store when not given. `run_scenarios(workdir)` runs ten named scenarios (happy_path, worker_death_before_receipt, zombie_late_write, stale_head, retry_after_fail, forged_receipt, partial_static_coverage, missing_required_receipt, not_run_with_waiver, budget_exceeded), each in its own subdirectory with a fake clock, and returns `{name: {verdict, reasons, unresolved_findings, extra}}`. Expected `StoreError`s are caught and reported in `extra`; anything else propagates. CLI: `python -m tools.vst.slice <directory>` prints a sorted-key JSON report.

## Gate rules

`gate.evaluate(manifest, receipts, current_head, current_epoch, key, waiver=None, artifact_resolver=None)` is pure and default-deny; the rule order and the verdict logic are specified in the `tools/vst/gate.py` module docstring. Summary: receipts must be valid, for this task, at the current head and epoch, correctly signed and with a derived-consistent result; the latest attempt per slot decides; earlier failures stay in `unresolved_findings`; unlisted receipts, broken attempt chains and unmet acceptance ids prevent APPROVE; a waiver can only cover unmet slots and acceptance ids and only for the current head.

Artifact binding: `artifact_resolver: Callable[[str], str | None] | None`. When given, for every otherwise-valid TestRun receipt each `(path, digest)` in `artifact_digests` must satisfy `artifact_resolver(path) == digest` (the resolver returns the CURRENT sha256 hex, or None when the artifact is missing); a mismatch, or a resolver that raises, adds a hard reason naming the receipt id and the path and the receipt is treated as invalid (excluded, so its slot is missing). When `artifact_resolver` is None (the default) the gate does NOT re-check artifacts at all: artifact binding is then only as strong as the signature over the receipt. All other gate rules are unchanged.

## Known limits

- Event-chain tail truncation is not detectable: `Store.verify_event_chain` recomputes the hash chain from the first event, so deleting the newest events leaves a valid prefix. Detecting it needs an externally anchored head hash or event count.
- The reviewer == author check inside `gate.evaluate` is defence in depth: `derive_result` already rejects such an IndependentReview as a result mismatch before the slot rule is reached.
- The HMAC proves origin within the machine trust boundary (the holder of the key signed the receipt); it does not prove that the test run was honest or that the recorded stdout, test ids or digests are true.
