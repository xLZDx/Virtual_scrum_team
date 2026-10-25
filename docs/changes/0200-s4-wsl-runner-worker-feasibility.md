# Change 0200: Record S4 WSL runner-to-worker feasibility blocker

## What changed

- Updated the bilingual S4 reports, S4 plan status/ordered work, and VST-032–037 backlog row with the read-only runner-to-worker feasibility audit.
- Recorded existing WSL identities: runner UID 997, worker UID 999, signer UID 995. Python and pytest are available, but the unprivileged runner has no sudo or file capabilities for the UID transition.
- Linked the blocker to the existing contracts: `tools/vst/runner.py` passes `user=worker_uid` and `group=worker_gid` to subprocess creation at lines 526–527; `tools.qa.run` refuses to sign a category unless `coverage_state` is `COMPLETE` at lines 322–326.
- Recorded that a disposable signer socket is feasible but insufficient. The partial E2E category cannot produce a signed result; a COMPLETE functional category could be used for report-serialization testing after an approved identity-transition mechanism is available.
- Kept the report-bound E2E selector, trusted deployed signer, run-specific manifest, current-head WSL/POSIX sandbox, report, receipt, and authoritative gate as `NOT_RUN`.
- Preserved operator accountability, Codex execution, and UNKNOWN technical QA runner/gate owner.

## Why

The prior report identified signer/manifest as dependencies but did not record the lower-level OS identity-transition constraint. The read-only feasibility audit shows that creating a local signer socket alone cannot satisfy the subprocess contract.

## Affected paths and contracts

- `reports/S4_QA_AUTOMATION_2026-10-25.ru.html`
- `reports/S4_QA_AUTOMATION_2026-10-25.html`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `core/BACKLOG.md` (VST-032–037)
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, generated `governance/DOCUMENT_REGISTRY.md`

No source, test, category mapping, or system state was changed. The pre-existing `.codex-s4-final-review.patch` was not inspected, modified, staged, or removed.

## Verification state

- Baseline branch HEAD: `123d2b1f5ecdb023631b42ea3c90a1f555ccdc3b`.
- Feasibility facts were supplied by the read-only E2E-agent audit; source behavior was checked at `tools/vst/runner.py:526–527` and `tools/qa/run.py:322–326`.
- No tests, builds, runtime probes, or system changes were performed for this documentation update.
- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py --check reports\S4_QA_AUTOMATION_2026-10-25.ru.html reports\S4_QA_AUTOMATION_2026-10-25.html`: exit 0, `all reports carry the mandated block`.
- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0, wrote 293 lines; `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0, registry current.
- `git diff --check`: exit 0; Git emitted only line-ending normalization warnings for the bilingual HTML reports.

Executor: Codex
