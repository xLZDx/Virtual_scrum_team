# Change record 0201: Record Temporal server and Python SDK source audit

## What changed

- Extended the S3 candidate audit with the official Temporal server pin and a separately pinned Python worker SDK: server `v1.32.1` / `af08a5e5f2dd40f545f2afac7780daaa6987001e`; SDK `1.34.0` / `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`.
- Recorded MIT and Python-version metadata, server/worker topology, direct and build-tool requirements, the feature-specific server compatibility floor, and limits of the SDK workflow sandbox.
- Recorded the replay-grouping release-note fix alongside upstream issue #1881, while retaining the pinned reproduction as `NOT_RUN`.
- Updated VST-028, the bilingual S3 report, decision log, lesson log and document registry.

## Why

S3 requires immutable candidate identity, license/dependency review, compatibility and security analysis before candidate acquisition. The server pin alone did not identify the separate process/library that implements Temporal application workers.

## Evidence and limits

- Security reviewer: `security-reviewer`, GPT-6 Luna, medium effort. Source audit was read-only; no Temporal source was cloned, installed, built, executed or tested.
- Official pinned sources: server [`README`](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/README.md), [`LICENSE`](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/LICENSE), [`go.mod`](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod); SDK [`release`](https://github.com/temporalio/sdk-python/releases/tag/1.34.0), [`pyproject.toml`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/pyproject.toml), [`README`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/README.md), and [`bridge Cargo.toml`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/Cargo.toml).
- SDK release notes state one feature needs server 1.32.0 or later. This only supports that feature-specific compatibility claim. Full SDK Core submodule/dependency closure, transitive license inventory, general compatibility, effective listener/auth/egress settings and sandbox runtime remain unverified.
- Issue #1881 reports local-activity replay grouping behavior on 1.32.0/1.33.0; release 1.34.0 describes a matching fix but does not identify that issue or demonstrate its exact reproducer. Replay verification remains `NOT_RUN`.
- No reachable exploit in the proposed deployment was established by this source-only review. S2 OS isolation remains mandatory; SDK workflow sandboxing is not containment.
- PM Bridge status/health/job tools returned `Transport closed`. A request ID from other sprint context cannot establish S3 gate status; no exact-head S3 approval is claimed. The current S3 report retains this unresolved gate.

## Ownership and next step

- Accountable task owner: operator for candidate acquisition authorization and final selection.
- Executor: Codex for bounded read-only audit and documentation.
- Technical sandbox/service owner: not identified in the inspected project records.
- Next: finish accessible source/dependency closure; after explicit acquisition authorization and a fresh S2 run-bound probe, test agents may execute the exact replay and worker-boundary scenarios. Keep runtime criteria `NOT_RUN` until then.

## Verification state

Documentation and registry updates only. No tests, checks, build, candidate acquisition, installation, or execution were performed as part of the source audit.
