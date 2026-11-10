# U5-1 GPT-PM code review scope

Task: U5-1, worker integration with the diff gate (Windows-local isolation, no WSL). Base origin/main b237194, head = current HEAD. Review the delta only: tools/vst/worker_gate.py, docs/sdlc/u5/WORKER_GATE.md, tests/vst/test_u5_worker_gate.py (tests are NOT_RUN; judge by reading), core/DECISION_LOG.md and core/LESSONS_LOG.md entries.

Delivers: `gate_worker_response` / `gate_worker_change` returning ACCEPTED / REFUSED / BLOCKED with reasons, the diffgate evidence and an isolation proof that lists VERIFIED, FAILED and NOT_VERIFIED properties. `tools/vst/diffgate.py`, `worker_adapter.py` and the WSL files are unchanged.

Interpretation decisions:
- The diff gate is reused for the final PASS/FAIL; checks it cannot express are added in the new module and only ever refuse (protected path inside allowed scope, case variants, Windows aliases, diff text versus declared paths, gitlinks).
- The scope is passed as plain `allowed_paths` plus `manifest_sha256` and `base_head`, not as a full manifest, so the module does not depend on manifest validation.
- REFUSED outranks BLOCKED when both kinds of reasons exist.
- ACCEPTED needs all five checkable isolation properties VERIFIED; an uncheckable one blocks. Nine properties are always NOT_VERIFIED.
- `base_commit_pinned` compares a caller-reported worktree base with the manifest base; it does not read git.
- Default protected list is `.git`, `.github`, `.gitlab`, `.hooks`, `.husky`, `.harness`, `.claude`, `.gitattributes`, `.gitmodules`, `AGENTS.md`, `CLAUDE.md`, on top of the caller list and `diffgate.is_blocked_path`.

Limits: no OS sandbox, no process containment, no network enforcement, point-in-time link check, diff text and isolation context are caller-supplied, no signing of the verdict. No caller of the new module is wired in this task.

Tests: written, NOT_RUN (pytest forbidden by the operator). No code was executed; evidence is static reading only.

Ask: the complete BLOCKER/MAJOR set for this delta only.
