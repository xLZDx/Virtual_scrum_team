# Change 0606 — Rebind the non-secret S2 runtime configuration candidate

Date: 2026-10-30
Owner: Codex
Backlog task: S2-4.10, ordered child of S2-4

## Acceptance delta

The existing non-secret runtime configuration candidate still named source `a600774`, while the
immutable `80c2b81deac364ed6466600fd46af47aafe805e2` runtime had been staged. Rebind the candidate
to that exact staged source and current run identity so the next ordered task can evaluate a
bounded runtime transition without redoing accepted source work.

## Changes and provenance

The runtime-config files and mapped test were already modified in the worktree at task start. This
task refreshed those in-scope candidate files; it did not create the earlier edits. Unrelated dirty
`core/DECISION_LOG.md`, S2 evidence/approval files, and other project paths were excluded.

- Rebound runtime, task, policy, unit, and helper source references to `80c2b81`.
- Generated a new run ID `s2-runtime-20261030-87d47f635f1c4231ab052a074dba4be8`, nonce
  `0d2bb2c5f977478a924f7ec6629a339d`, and bootstrap request ID
  `3e56a61c5b1e45aea089c305b25e3187`; all are non-secret and remain preparation-only.
- Created the read-only transition candidate with the staged runtime's
  `tools.vst.bootstrap_runtime prepare` at `2026-10-30T03:03Z`, using source plan SHA-256
  `01818efcd23bc20a3a4b408921d7342f5e5f95adc16ad86fe7b2a3b7176e2344` and the inventory SHA-256
  pinned by the staged runtime marker, `5f011ff65577a9363d2c1b60747e586d12042995dc88e8dff8779bdb81b28a66`.
  Candidate transition digest: `dc516f6b7053ec48bf96aaa3ddb3042d87d57f8f7199284e27e98f8203cc7935`.
  The captured canonical output is `docs/sdlc/evidence/s2-runtime-transition-manifest-80c2b81-20261030T0303Z.json`.
  Runtime tree digest: `9c2d41578ada16e9e8e3b957d028802d0a8cca61f652cebe0f88a7bbfae9ece3`.
- Bound the deployment snapshot to the verified incremental S2 Git bundle, SHA-256
  `3005e13bc384f5cc5f769898ac5be31dec3d4da5886800be07a6fcfbf51659053`, 135,364 bytes. The bundle
  advertises the S2 branch at `c59f1c5`, requires the target's existing `a600774` base, and contains
  the pinned `80c2b81` source commit; the deployment manifest specifies checkout `80c2b81`.
- Recomputed cross-bindings: source binding
  `3ca978c4fbd731f14bb5a0d78afa184f3273ade30601b0d0b28f9efe7273bde3`, assignment policy
  `d84fc710f22b73727772ec86dd98b23097f8baaab90828468919ef178b930153`, and task manifest
  `c9dc31dce7419214d88a4da5dd645f5905ef01f8640154d357143f73afdcc860`.
- Refreshed all 34 listed payload byte sizes and SHA-256 values. Removed the historical auxiliary
  content-only digest from the current binding because this repository has no reproducible
  generator for it; the exact Git bundle, source head, archive and metadata-inclusive runtime tree
  remain bound.
- Updated the README's current source statement after test evidence. The bundle remains
  `PREPARED_NOT_INSTALLED`; this task did not select the runtime, install configuration or units,
  start services, initialize Store, or dispatch a task.

Two full WSL inventory captures at `2026-10-30T02:59:40Z` and `03:00:52Z` recorded the staged
runtime/helper absent, while immediate same-distribution read-only `lstat` probes found them
present. Those inconsistent snapshots are preserved but not used as transition inputs. The
official `prepare` command then independently verified the staged runtime marker and generated the
current transition candidate successfully. No private key contents were read or hashed.

## Verification and review

- Functional-test-reviewer command: `python -m pytest -q tests/vst/test_s2_runtime_config_bundle.py`.
- HEAD: `c59f1c51b6996bfcc99f42251dc3f63ee07c958a`; environment: Python 3.14.3.
- Result: **9 passed**, 1 existing pytest-asyncio deprecation warning, exit code 0.
- The focused suite covered source/run binding, all 34 payload hashes, transition/source/policy/task
  digests, and matching run ID/nonce. It does not establish runtime activation or owner-to-Runner
  execution.
- Security reviewer found no actionable BLOCKER/MAJOR. The stale README source reference was fixed.
  One next-task condition remains: the target inventory shows both host-path systemd drop-in
  destinations already exist as root-owned 153-byte files but contains no content hashes. Before
  configuration installation, compare their exact bytes to the candidate and refuse any mismatch;
  do not overwrite an unknown file.

## Next ordered action

S2-4.10 acceptance is the exact, tested 80c2 non-secret candidate. The next task is a read-only hash
comparison for the two existing drop-ins, followed by the separately bounded runtime-selection and
configuration-installation operation. Codex owns both actions. Current-run E5 evidence and the one
permitted real owner-to-Runner journey remain open; restricted process-kill, crash/recovery,
mutation, E8, and policy selectors remain `NOT_RUN`.
