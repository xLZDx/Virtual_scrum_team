# U5-1 GPT-PM code review scope

Task: U5-1, worker integration with the diff gate (Windows-local isolation, no WSL). Base origin/main b237194, head = current HEAD. Review the delta only: tools/vst/worker_gate.py, docs/sdlc/u5/WORKER_GATE.md, tests/vst/test_u5_worker_gate.py (tests are NOT_RUN; judge by reading), core/DECISION_LOG.md and core/LESSONS_LOG.md entries.

Delivers: `gate_worker_response` / `gate_worker_change` returning ACCEPTED / REFUSED / BLOCKED with reasons, the diffgate evidence and an isolation proof that lists VERIFIED, FAILED and NOT_VERIFIED properties. `tools/vst/diffgate.py`, `worker_adapter.py` and the WSL files are unchanged.

Interpretation decisions:
- The diff gate is reused for the final PASS/FAIL; checks it cannot express are added in the new module and only ever refuse (protected path inside allowed scope, case variants, Windows aliases, diff text versus declared paths, gitlinks).
- The scope is passed as plain `allowed_paths` plus `manifest_sha256` and `base_head`, not as a full manifest, so the module does not depend on manifest validation.
- REFUSED outranks BLOCKED when both kinds of reasons exist.
- ACCEPTED needs six isolation properties: three VERIFIED (computed here) and three CALLER_ASSERTED (base pin, worktree HEAD, network flag; only caller values exist). An uncheckable one blocks. Nine properties are always NOT_VERIFIED.
- Default protected list (see WORKER_GATE.md): names matched at any depth, `tools/vst` and `.harness-tools` as root prefixes, on top of the caller list and `diffgate.is_blocked_path`.

Limits: no OS sandbox, no process containment, no network enforcement, point-in-time link check, diff text and isolation context are caller-supplied, no signing of the verdict. No caller of the new module is wired in this task.

Tests: written, NOT_RUN (pytest forbidden by the operator). No code was executed; evidence is static reading only.

Ask: the complete BLOCKER/MAJOR set for this delta only.

## Review remediation

Three read-only reviewers reported; one batch fixed (static only, tests NOT_RUN):
- BLOCKER: `.git` in the default protected list failed the canonical-path check, so every call was BLOCKED. Protected entries now use a weak check; `.git` components are PROTECTED_PATH at any depth, also when listed as allowed; hazardous allowed entries no longer block.
- MAJOR: protected matching was root-prefix only. Default names now match at any depth; `tools/vst` and `.harness-tools` added as root prefixes; alias spellings are normalised for matching.
- MAJOR: the diff grammar was not fully validated. A full block grammar with hunk line counts, size caps and mode checks replaces the header scan.
- MAJOR: isolation properties derived from caller strings were reported VERIFIED. New status CALLER_ASSERTED, a real two-root existence and disjointness check, worktree HEAD recorded and required, link walk counts inspected components and requires existing paths.
- MINOR: evidence path comparison uses `sorted(set(changed))`; reason details are `ascii()` cut to 200; docstrings and docs corrected.
- The test file was not registered: `tools/qa/build_registry.py` now maps it as functional. `docs/qa/categories.json` is generated (per-test entries, `source_commit` and file sha256 that exist only after the test file is committed) and was NOT updated by hand; it must be regenerated with the generator after commit.
