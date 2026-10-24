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

- TestRun: `expected_test_ids`, `executed_test_ids`, `skipped_test_ids`, `xfail_test_ids`, `covered_acceptance`; `commands` = non-empty list of `{argv: non-empty list of str, exit_code: int}`.
- StaticAnalysis: `coverage` in COVERAGE; `covered_rules`, `unsupported_rules`, `covered_acceptance`.
- IndependentReview: `reviewer_principal`, `author_principal` (non-empty str); `covered_acceptance`, `findings`; `signed_verdict` in {MODIFY, NO_GO, APPROVE}.
- Documentation: `check_description` non-empty str; `covered_acceptance`.

## derive_result (what `result` MUST be)

- TestRun: INCONCLUSIVE if `executed_test_ids` is empty; PASS only if every `exit_code == 0`, `expected_test_ids` non-empty, set(executed) == set(expected), and `skipped_test_ids` and `xfail_test_ids` are empty; otherwise FAIL.
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

`Store(path, clock=time.time)`: one sqlite3 connection per instance, WAL, foreign keys on, autocommit with an explicit `BEGIN IMMEDIATE` per mutating method (each public method is atomic). Context manager closes the connection. `StoreError(message, kind)`; kinds: story, epoch, lease, slot, chain, duplicate, budget, argument.

Tables: `stories(story_id, project_id, phase, epoch, owner, state, owner_expires_at)`, `leases(task_id, story_id, attempt, worker_id, epoch, expires_at, released, marked)`, `slots(slot_no, task_id, worker_id, expires_at)`, `receipts(seq, receipt_id UNIQUE, story_id, task_id, slot, attempt, epoch, receipt_sha256, prev_receipt_sha256, body, UNIQUE(task_id, slot, attempt))`, `events(seq, ts, task_id, actor, kind, payload, prev_hash, hash)`, `budget(task_id, cap, spent)`. Columns beyond the minimal design: `owner_expires_at` (owner liveness), `marked` (supervisor receipt already written), `receipts.story_id` (story view).

- Append-only: triggers `RAISE(ABORT)` on UPDATE and DELETE of `receipts` and `events`.
- Epoch: `open_story` starts at epoch 1 with no owner. `acquire_epoch(story_id, owner, ttl_sec=3600)` is a compare-and-swap: it bumps the epoch and returns it only when no live owner (`owner_expires_at` in the future) holds the story, otherwise `StoreError(kind='epoch')`. Winning fences the previous epoch's live leases (`released = 2`, slots freed). Lease operations and `append_receipt` must carry the current epoch.
- Lease and slot: `acquire_lease` takes a free `slots` row in the same transaction; it fails for a stale epoch, no free slot, a live lease, a non-increasing attempt, or a previous attempt that was lost and not yet marked by the supervisor. `leases.released`: 0 live, 1 released by the worker, 2 reaped on expiry or fenced. `heartbeat` rejects expired, foreign or stale-epoch callers.
- Receipts: `append_receipt` validates, requires `epoch` == current story epoch, attempt == last attempt + 1 per `(task_id, slot)` and `prev_receipt_sha256` == previous receipt hash; body is stored as canonical JSON.
- Events: `hash = sha256(prev_hash + canonical JSON of {ts, task_id, actor, kind, payload})`, first `prev_hash` is 64 zeros; `verify_event_chain` recomputes the chain.
- Budget: `charge` never lets `spent` exceed `cap`; on overflow it commits a `BUDGET_EXCEEDED` event and raises `StoreError(kind='budget')` without charging.
- Supervisor receipts: `supervisor_reap_and_mark(manifest_lookup, key, runner_id)` writes, for each reaped lease with no receipt for its `(task_id, attempt)`, a signed Documentation receipt with result INCONCLUSIVE and `check_description` `WORKER_LOST`; when the lease attempt exceeds `retry_cap + 1` the result is BLOCKED and the description `RETRY_EXHAUSTED`. Slot rule: the first `required_receipts` entry of type Documentation, else the first entry. Attempt = next in that slot's chain; epoch = current story epoch; `candidate_head` = head of the task's latest receipt, else manifest `base_head`.
- `render_state_md(story_id)`: deterministic markdown view, first line states it is a generated view that must not be edited.

## Runner (`tools/vst/runner.py`)

`run_and_sign(...)` runs each argv with `subprocess.run` (no shell, captured text output, timeout, cwd), records `argv` and `exit_code` (-1 timeout, -2 missing executable), joins stdout, calls the injected parser to get `(executed, skipped, xfail)`, builds a TestRun receipt, sets `result = derive_result(receipt)`, signs it with `signing.sign`, validates it and returns it. An empty commands list raises `ContractError`. The key is a plain argument: never written, logged or read from the worker cwd. Helpers: `file_sha256(path)` (64 KiB chunks) and `artifact_digests(paths)`.

## Gate rules

`gate.evaluate(manifest, receipts, current_head, current_epoch, key, waiver=None)` is pure and default-deny; the rule order and the verdict logic are specified in the `tools/vst/gate.py` module docstring. Summary: receipts must be valid, for this task, at the current head and epoch, correctly signed and with a derived-consistent result; the latest attempt per slot decides; earlier failures stay in `unresolved_findings`; unlisted receipts, broken attempt chains and unmet acceptance ids prevent APPROVE; a waiver can only cover unmet slots and acceptance ids and only for the current head.
