# S2 authenticated assignment-basis candidate functional evidence

Date: 2026-10-29  
Scope owner: `functional-test-reviewer` (test design and execution)  
Sprint: S2, REQ-001 / REQ-005 / REQ-006; TP-26 through TP-28 in `docs/sdlc/test-plan.md`  
Current source HEAD: `3d5f6c2048238a79fb92ddf805bc562b4b392a63`

## Result

The final focused source run passed **23 tests**: 21 assignment-basis tests plus two selected existing Store regressions. Python emitted one `pytest_asyncio` deprecation warning (`asyncio.get_event_loop_policy`); it did not fail the run. No full suite, build, lint, provisioning, migration, runtime selector, production service, real peer, or production policy was exercised.

The tests model a possible future operation journal row with synthetic values in an in-memory Store. They do not create an assignment writer, claim that the row was authenticated by a real peer, or establish installed production authorization. The root policy, peer IDs, run ID, generation, task, handoff, and operation are all test fixtures.

## Commands and observed outcomes

Final command, from `D:\Repo\Virtual_scrum_team`:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_persistent_runner_service.py::test_store_completion_appends_the_receipt_chain_and_replays_only_exact_complete_receipt tests/vst/test_s2_persistent_runner_service.py::test_store_refuses_preflight_consumption_before_verified_startup_history
```

Result: **23 passed, exit code 0**, one `pytest_asyncio` deprecation warning. The two existing safe selectors exercise `Store.execution_grant_basis` as part of receipt completion and refuse preflight consumption when startup history is unverified. `test_s2_persistent_runner_service.py` was not run as a whole.

Freshness regression before the source fix, at HEAD `c2b1cd2172a0b5db85247a6f414a4b1568a4fcb0`:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_assignment_basis.py::test_assignment_basis_rejects_consumed_handoff_from_previous_supervisor_run
```

Result: **1 failed, exit code 1**, with `Failed: DID NOT RAISE StoreError`. The disposable Store held an otherwise valid, unexpired handoff and consumed probe for `synthetic-run-1`, while the current Supervisor run ID was `synthetic-run-current`. The source accepted it. The source correction at `3d5f6c2` added the current run and service generation checks inside the same read snapshot; that regression and the matching previous-generation regression pass in the final command.

The exact interim command that also selected the old schema-v5 compatibility regression was:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor tests/vst/test_s2_persistent_runner_service.py::test_store_refuses_preflight_consumption_before_verified_startup_history
```

It returned **19 passed, 3 failed, exit code 1**. Two newly authored freshness assertions expected narrower error-message text than the actual fail-closed message (`assignment handoff belongs to a stale Supervisor run or generation`); those assertion patterns were corrected to the actual contract. The third failure was the exploratory schema-v5 selector asserting `PRAGMA user_version == 5` at `tests/vst/test_s2_persistent_runner_service.py:189`, while the source returned 6. The same selector source blob is unchanged at baseline `9c1be0f` and current HEAD (`695a677baaff2d68163f3f0c6d0af272dfe0aae1`), and baseline `tools/vst/store.py` already declares `SCHEMA_VERSION (6)`. The selector was not edited and is outside TP-26/27; it is recorded for Codex maintenance in `docs/sdlc/backlog.md`. The final passing command instead uses the safe current-source completion and startup-history selectors named above. No assertion was weakened.

## Coverage map

| Acceptance mapping | Test behavior | Result and limit |
|---|---|---|
| TP-26; S2-3/S2-4 candidate; REQ-005/006 | A matching operation ID resolves a closed response from one Store read transaction, bound to handoff, policy, task, owner, epoch, lease, runner, run, probe, generation, and expiry. Snapshot checks compare all SQLite tables before and after. | Passed. Synthetic Store/journal only; no production writer or auth claim. |
| TP-27; S2-3/S2-4 candidate; REQ-005/006 | Malformed/unknown IDs, legacy rows, wrong payload, handoff/task manifest mismatch, policy mismatch, wrong principal, stale epoch/lease/probe/runner, wrong journal actor, duplicate operation event, changed/missing/expired policy provider, wrong RPC role, caller-selected request fields, previous Supervisor run, and previous service generation refuse. | Passed at HEAD `3d5f6c2`. The previous-run behavior was observed accepting before its source fix at `c2b1cd2`. |
| TP-28; S2-1 regression; REQ-001/005 | Existing exact receipt completion invokes `execution_grant_basis`; startup-history guard keeps preflight consumption closed when reconciliation is false. | Both named existing selectors passed. This is focused source regression evidence, not full runner or runtime acceptance. |

The RPC role tests call the narrow dispatch method with synthetic `SupervisorPeer` values; they do not run `AuthenticatedSupervisorAPI`'s POSIX socket, kernel credential, pidfd, cgroup, root-owned file, or systemd boundary. The policy provider is a fixture callable, not a real root-owned configuration. No RPC request can select a task, policy, owner, lease, generation, or peer in the tested schema.

## Revisions and artifact hashes

Source commit under test: `3d5f6c2048238a79fb92ddf805bc562b4b392a63`. The test and test-plan files were authored in the current working tree and are not represented as committed artifacts in this report.

| File | Git blob SHA-1 |
|---|---|
| `tools/vst/assignment_basis.py` | `60d6a47b5354d4a1f5ccf8244724d8b104bd9920` |
| `tools/vst/store.py` | `a1bcb739be2ee022fc18292ff988355610329608` |
| `tools/vst/supervisor.py` | `92bdc6074cda9f659e715da7b0f54b301991d3e0` |
| `tools/vst/supervisor_service.py` | `136593f35d6436878e5117ce36c093edb3496455` |
| `tests/vst/test_s2_assignment_basis.py` | `aa625953e18d339480009fa5c543883800249b55` |
| `docs/sdlc/test-plan.md` | `4a54c692153488c321a3085eb288806e29fd94bd` |
| `docs/sdlc/backlog.md` | `59cd9c610bbd092bd38c6b28fe88532c0f12e254` |

Environment for the result above: Windows host, Python `3.14.3` (`C:\Python314\python.exe`), pytest `8.4.2`.

## POSIX confirmation at the same frozen source HEAD

The same 23 selected cases were then executed in the existing dedicated `Ubuntu-24.04` WSL2 distribution. The source archive was created from committed HEAD `3d5f6c2048238a79fb92ddf805bc562b4b392a63`; the newly authored, still-untracked test module was added as the sole test overlay. No working tree source, existing test, or other uncommitted file was copied. The archive was streamed to WSL stdin; it was extracted to `/run/vst-s2-assignment-basis-3d5f6c2-1j7s9d02` and removed after the run. No Windows mount, checkout, provisioning, source edit, or runtime configuration change was used.

Environment: CPython `3.12.3`, existing pytest `7.4.4` from `/usr/lib/python3/dist-packages`, `vst-runner` UID/GID `997:988`. The interpreter used `-B -I -S`; the tiny bootstrap explicitly added only the isolated archive root and existing pytest package directory because isolated `-S` mode does not load site packages. It invoked the same three selectors listed below, under a transient systemd unit `s2-assignment-basis-3d5f6c2-6e5099ac.service` with `CPUQuota=100%`, `MemoryMax=2G`, `TasksMax=64`, `RuntimeMaxSec=45s`, private `/tmp` (1 GiB), `PrivateNetwork=yes`, `RestrictAddressFamilies=AF_UNIX`, `NoNewPrivileges=yes`, and empty capability bounding/ambient sets. The run completed in 2.637 seconds (pytest itself: 2.01 seconds); unit and outer WSL exit codes were both 0.

Exact effective pytest selection, executed by `/usr/bin/python3.12 -B -I -S -c <isolated bootstrap>` inside that unit:

```text
-q -c /dev/null --rootdir /run/vst-s2-assignment-basis-3d5f6c2-1j7s9d02 -p no:cacheprovider tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_persistent_runner_service.py::test_store_completion_appends_the_receipt_chain_and_replays_only_exact_complete_receipt tests/vst/test_s2_persistent_runner_service.py::test_store_refuses_preflight_consumption_before_verified_startup_history
```

Result: **23 passed, 0 failed, 0 skipped**, exit code 0. The outer transport used `git archive --format=tar 3d5f6c2048238a79fb92ddf805bc562b4b392a63` and streamed the resulting archive plus only `tests/vst/test_s2_assignment_basis.py` to:

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec /usr/bin/python3.12 -B -I -S -c <stdin archive extractor and bounded unit launcher>
```

Archive provenance: committed-source archive SHA-256 `2ff6a8b3de7e9a1ac9d023c01eaf3ff52d643df1f8bdfa36353f602ea8039165`; combined WSL input archive (source archive plus the single test overlay) SHA-256 `765ebc3c0d3571581dd68bf42a3bb7ac0f4191ad4f9e3f2abd8d6fa660ec1794`, 40,550,400 bytes. The overlay test blob SHA-1 remained `aa625953e18d339480009fa5c543883800249b55`. The source commit and source file blob identities listed above were unchanged. The temporary extraction directory was removed by the launcher; `--collect` removed the transient unit.

This confirms the read-only assignment-basis API tests and the two selected Store regressions are compatible with the actual POSIX interpreter and SQLite/runtime environment. It remains synthetic source-level evidence: no authenticated production peer, root policy, assignment writer, runtime service, E5 attestation, restricted selector, or production authorization was exercised. The historical schema-v5 selector failure above remains separately recorded and was not rerun or modified.

## Remaining limits

- S2 assignment writer/source provenance, production trusted policy and peer configuration, authenticated kernel RPC, root custody, current E5, and runtime acceptance remain unproven.
- Process-kill, crash, mutation, E8, and restricted policy selectors remain `NOT_RUN`.
- The candidate read-only response is test-proven only for the synthetic in-memory fixture and the final source revision shown above. It does not close other S2 blockers or authorize a production deployment.
