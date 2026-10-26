# Change 0357 — Record S4 report-bound evidence at `b3fb7bc`

## What changed

- Preserved the Windows report-bound seeded-failure report and complete stdout/stderr snapshots byte-for-byte under `docs/sdlc/evidence/qa/s4-seeded-failure-20261026-win-b3fb7bc-r1/`.
- Added `docs/sdlc/evidence/s4-b3fb7bc-report-bound-evidence-20261026.md` with candidate, registry, target, row-hash, WSL staging and policy-exclusion evidence.
- Updated `core/STATE.md` and `core/BACKLOG.md` to distinguish the current Windows result from older WSL evidence and the current WSL `NOT_RUN` state.

## Windows run evidence

- Exact run: `s4-seeded-failure-20261026-win-b3fb7bc-r1`; candidate `b3fb7bc38aee308520e29091707e4c6cb3d46da1`; source/test `62e9c946bdb66fccc6eaf0b164b8c5e178592cf8`; registry SHA-256 `aa9c7370d87500d280771d8eb356f8a3debd903238f48f763af4b0c7c0c2b72b`.
- Result: **PASS 3/3**, exit 0, zero run reasons. Report row SHA-256: `480762444bacc8a9ec853b8802a66f6ed9929382d945d0aacae4f61eecbde172`.
- Dependency target SHA-256 before and after: `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84`; both exact-content checks were true. The hash-pinned wheelhouse was unchanged.
- Preserved artifact hashes: `report.jsonl` 57,303 bytes, `227ac94b7e8e9601e11087775651abed396764083e4156edf938821ad9d6dff1`; `stdout.txt` 800 bytes, `b306fd6308f5c5b80b8e17fe269382260d6dd0a5fedc84cc6cf14482ddae55b1`; `stderr.txt` 101 bytes, `a528b1e4d996e9b60eccbc8a0592358d1272e47b0eedcbdee4f448ee8777562b`.
- AC-17 explicitly leaves same-identity in-run mutation/change-and-restore protection `NOT_VERIFIED`; the before/after checks do not prove that stronger property.

## WSL and policy limitations

- Current-candidate WSL seeded-failure and AC-16 identity are `NOT_RUN`; all attempts stopped before candidate/target preparation or selector execution. A small 26-byte stdin probe matched host/WSL hash, but the 5,396,149-byte input tar did not become visible for WSL-side hash verification, including the final one-process transfer attempt. The failure's root cause is not verified. No helper, candidate, target, or canonical report was changed by those attempts.
- Older candidate `4fe1503` still has report-bound WSL identity PASS 1/1 and seeded-failure PASS 3/3. These are not relabeled as `b3fb7bc` evidence.
- The restricted-root profile remains `NOT_RUN`; the installed helper did not match the requested candidate and was left unchanged. The 52 policy-excluded selectors remain `NOT_RUN`; no process-kill, process-death, timeout-termination, mutation, crash/resume, or kill-table selector was run.

## GPT-PM gate status and next steps

- The earlier request `6af6f2d7-742a-4c8d-9eb2-85cb9ce2a03b` / job `1e04d054-66b0-412a-99ef-64e119a1b869` remains `uncertain`, with no correlated turn/reply, `generationLease=null`, and error `CHATGPT_SEND_UNCONFIRMED`. The request was absent from the project message log, conversation peek still awaited a review package, and a cancellation request did not change the durable record. It predates the present code/test revision and is not a gate.
- Next actions: GPT-PM/PM Bridge owner reconciles the uncertain durable job; Codex prepares a fresh exact-head review only after safe request correlation is available. Continue to preserve the 52 policy exclusions and AC-17 limitation. Do not push, create a PR, or merge without exact-head GPT-PM approval.
- Accountable task owner: operator. Evidence and local Git work: Codex. Runtime execution: designated `e2e-runner`.
