# Change record 0019: S1 second remediation, gate and contracts (package C1)

## What changed
- `tools/vst/gate.py`: the head and artifact-digest checks moved from `_check_receipt` (every receipt) to the deciding receipt of each real slot (latest attempt of an intact chain). `_check_receipt` now validates contract, task, `manifest_sha256`, `role_sha256`, future epoch (hard), signature and `derive_result` only; its `head` and `artifact_resolver` parameters were removed. New helper `_check_artifacts`. Older attempts at another head are listed as `history attempt at other head: <slot> attempt <n>` in `unresolved_findings`. A deciding receipt at a stale head is a hard `stale head` reason and the slot is unmet. `SUPERVISOR_SLOT` markers are exempt from the head check; a future-epoch marker is hard but kept, so terminal markers are dropped only for invalid signature or binding. The "all receipts stale" `NO_GO` now counts deciding receipts and future-epoch receipts only (markers and older attempts excluded). `evaluate` returns `NO_GO` when `key`, `supervisor_key` and `operator_key` (if given) are not pairwise distinct.
- `tools/vst/contracts.py`: `normalize_principal` applies `unicodedata.normalize("NFKC")`, rejects Cc and Cf characters (control, zero-width, format) with `ContractError`, then strips and casefolds. Artifact digest keys in TestRun receipts must pass `_validate_repo_path`.
- `tools/vst/schemas/README.md`: head rule, key distinctness, NFKC and artifact key rules documented.

## Why
Decision "S1 re-review of 3e27720" in `core/DECISION_LOG.md`: all four reviewers found that a retry on a new commit could never reach APPROVE because every older attempt and every `WORKER_LOST` marker at another head was a hard reason. Key reuse and Unicode principal spoofing were the listed minor findings.

## Affected contracts and paths
`tools/vst/gate.py`, `tools/vst/contracts.py`, `tools/vst/schemas/README.md`. Behavior change: older attempts and supervisor markers at another head no longer block; principals with Cc/Cf characters (including embedded or trailing newline or tab) now raise `ContractError`; receipts with non-repo-relative artifact keys no longer validate (the runner already enforces this for its own output).

## Verification state
Code changed only. Tests were NOT run or rerun, nothing was imported or executed. Not independently reviewed.
