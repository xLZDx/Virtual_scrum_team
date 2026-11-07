# Change 0436: fix S2 worker privilege, anchor-tail, and subprocess cleanup findings

## What changed

- POSIX worker launches now pass through `/usr/bin/setpriv`, which clears ambient and inheritable capabilities and sets `no_new_privs` before executing the accepted command.
- External-anchor append now durably inserts a line separator when the existing valid JSONL tail lacks its final newline.
- The bounded Git wrapper now places reader startup under process cleanup handling, kills/reaps the child on startup/read failures, and reports reader failures rather than returning partial output as success.
- Updated S2 backlog and sandbox contract/implementation documentation to express the capability invariant and mark targeted runtime regressions pending.

## Why

The exact-head S2 specialist pass found three actionable findings: the WSL runner unit grants ambient `CAP_SETUID`/`CAP_SETGID` but the worker launch had no visible capability drop; the anchor reader accepted a complete last JSON record without a newline while append could concatenate the successor; and bounded Git pipe-reader startup could fail before the timeout/cleanup block, leaving the process unreaped. The capability exploit path is an evidence-based inference, not a runtime reproduction.

## Affected paths

- `tools/vst/runner.py`
- `tools/vst/lifecycle.py`
- `tools/vst/slice.py`
- `tools/vst/schemas/README.md`
- `docs/SANDBOX_SPEC.md`
- `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`
- `core/BACKLOG.md`
- `docs/changes/0436-fix-s2-worker-capabilities-anchor-tail-and-git-cleanup.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and review

- Code review baseline: S2 source/test head `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2` against S2 base `6117ba24b08a260b42402db6da0bf767864e1c04`.
- Reviewers: `security-reviewer`, `database-reviewer`, `reliability-reviewer`, `silent-failure-hunter`, and `architect`; all used GPT-6 Luna at medium effort. The capability boundary was independently raised by security, architecture, and silent-failure review. The anchor tail was independently raised by database, architecture, and silent-failure review. Bounded Git cleanup was independently raised by reliability and silent-failure review.
- The exact E5 evidence records runner ambient `CAP_SETUID`/`CAP_SETGID`, signer UID 995, and key mode 0600. The capability escalation path remains an inference until the designated WSL runtime regression is executed.
- The existing Ubuntu-24.04 WSL installation reports `/usr/bin/setpriv` from util-linux 2.39.3. This was a read-only helper availability query; no worker command or test was run.
- No test, acceptance scenario, build, CI, migration, or runtime execution was performed while making this change. Targeted regression tests are the next phase and are owned by `functional-test-reviewer` / `e2e-runner`.

## Acceptance and next steps

- Code changes address the three findings, but are not yet runtime-proven. Do not describe these fixes as accepted until exact-head functional/E2E evidence and fresh specialist re-reviews exist.
- Keep the process-kill, crash/resume, mutation, and separately policy-excluded timeout selectors `NOT_RUN` unless their specific acceptance is authorized.
- Owner: Codex implements and reconciles; designated test roles author/execute permitted regression tests; operator owns policy disposition; GPT-PM owns the later exact-head gate.

## Attribution

Change: 0436
Executor: Codex
