# S2 safe source-gap audit — 2026-10-26

## Scope and result

Read-only inspection of `tools/vst` and the current S2 platform/sandbox acceptance at canonical repository HEAD `6ca2ee00ef31ac621e7ff3231ac175646bbd3bb2`. The `code-explorer` used GPT-6 Luna, medium effort. It made no changes and ran no tests, checks, builds, provisioning, process-kill, crash, or mutation scenarios. The audit found no evidence-backed source fix that could safely close remaining S2 acceptance without those prohibited runtime scenarios.

## Code evidence

- Strict Windows execution fails closed if Job Object attach/resume setup fails (`tools/vst/runner.py:398-421, 561-586`). This source behavior is implemented; actual nested-Job-Object/descendant runtime proof remains `NOT_RUN`.
- Signed preflight and supervisor verification are implemented (`tools/vst/preflight.py:211-217, 244-281`; `tools/vst/supervisor.py:245-275`). The sandbox specification states that a probe cannot prove host firewall or hypervisor enforcement (`docs/SANDBOX_SPEC.md:34-46, 60-85`). The operator-provisioned environment has per-run evidence; comprehensive host/system enforcement is still not inferred from the probe.
- S2 E8 still needs runtime evidence for crash-mid-edit, STOP, budget/resume and unauthorized-write/egress acceptance (`docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md:105-110`). Crash/process-death and mutation portions remain excluded by the active scope.

## Acceptance disposition

The audit is not runtime proof and does not close S2. E4 process-group/descendant cleanup and Windows Job Object nesting remain `NOT_RUN`; E5 host firewall/hypervisor, persistent deployment, workspace binding and full egress remain incomplete or `NOT_VERIFIED`; E8 crash/process-death/mutation scenarios remain `NOT_RUN`. Codex owns source audit and evidence reconciliation; the operator owns any expansion of process/crash/mutation policy; `e2e-runner` may execute only the permitted scenarios. Preserve all excluded statuses.
