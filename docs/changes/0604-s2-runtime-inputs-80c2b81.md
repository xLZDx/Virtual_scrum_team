# Change 0604 — Pin exact S2 runtime inputs for selector fix

Date: 2026-10-30
Owner: Codex
Backlog task: S2-4.8, ordered child of S2-4

## Acceptance delta

The S2-4.7 selector fix was normally pushed as `80c2b81deac364ed6466600fd46af47aafe805e2`.
StageOnly requires an immutable source plan and a recent target inventory for that source. The
prior plan and inventory were for `f685cc9` and cannot be reused as if they described this commit.

## Exact source and target inputs

- Source plan: `docs/sdlc/evidence/s2-runtime-source-plan-80c2b81deac364ed6466600fd46af47aafe805e2.json`
  — 12,750 bytes, SHA-256
  `01818efcd23bc20a3a4b408921d7342f5e5f95adc16ad86fe7b2a3b7176e2344`; archive SHA-256
  `06122645bfe6b1b9c8139fa4a77cca63aab3fd17918245cd75cee1f8f83aae4c`.
- Exact generator invocation: `python tools/qa/prepare_wsl_runtime_plan.py --expected-head 80c2b81deac364ed6466600fd46af47aafe805e2`.
  The generator reads the exact committed Git archive; its Windows CRLF output was normalized to
  LF without changing the JSON value. The plan remains an unsigned candidate and does not authorize
  activation.
- Target inventory: `docs/sdlc/evidence/s2-runtime-target-inventory-80c2b81deac364ed6466600fd46af47aafe805e2.json`
  — 14,458 bytes, SHA-256
  `5f011ff65577a9363d2c1b60747e586d12042995dc88e8dff8779bdb81b28a66`; source and requested
  source heads both equal `80c2b81deac364ed6466600fd46af47aafe805e2`.
- Exact read-only WSL wrapper: `$script | wsl.exe -d Ubuntu-24.04 --user root -- python3 -B -`.
  It queried systemd unit states and jobs, mount visibility, compiler ownership/package/version/hash,
  and metadata for fixed runtime, configuration, Store and preflight paths. It did not read private
  key contents, hash secret bytes, or mutate the target.
- Observation time: `2026-10-30T02:49:02.839487+00:00`. The selected runtime remains `a600774`;
  all nine S2 units are inactive; no systemd jobs are pending; `/var/lib/vst-runner/private/store.sqlite3`
  and the current preflight record are absent. `/usr/bin/cc` resolves to the root-owned GCC 13
  package executable at mode `0755`, SHA-256
  `1b99826121ae6682a634e5efe09bd3e3df58ce58e0b28f849114ab5b89139c26`.
- Historical note `s2-runtime-qualification-a600774.md` was corrected to label the old Runner-signature
  diagnosis as superseded by accepted S2-4.1/S2-4.2 source contracts. It remains valid history for
  `a600774`, not a current prerequisite.

## Acceptance disposition and next action

- Exact source plan and refreshed read-only target inventory: captured and hash-checked. The first
  inventory snapshot expired before installation: the normal installer rejected it when its age
  was 318.9 seconds (the limit is 300 seconds), before any target mutation. All other revision and
  compiler identity values matched. The new inventory was collected immediately before retry.
- No runtime selection, service start, Store initialization, bootstrap, or dispatch occurred. The
  StageOnly retry with the refreshed inventory is the next action; verify the immutable staged tree
  against this exact plan and inventory. Do not select the runtime or install the separate stale
  configuration candidate in this step.
- Current E5 evidence and the real owner-to-Runner journey remain open. Restricted process-kill,
  crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`.
