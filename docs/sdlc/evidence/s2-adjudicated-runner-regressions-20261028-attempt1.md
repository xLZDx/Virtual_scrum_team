# S2 adjudicated runner regression test attempt 1

## Scope and source identity

| Field | Value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` |
| Branch / committed base HEAD | `s4-canonical-continuation` / `378df7260d8654f396ae1b45eaa9462d4bb4b88f` |
| Interpreter | `C:\Python314\python.exe` (Python 3.14.3; queried with `C:\Python314\python.exe --version`) |
| Test command | `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py` |
| Result | **54 passed, 1 failed, 0 skipped; exit 1; 1 deprecation warning** |
| Failure | `tests/vst/test_s2_persistent_runner_service.py::test_effects_resolved_operator_record_allows_only_a_separately_authorized_successor` |
| Failure location | `tests/vst/test_s2_persistent_runner_service.py:1313`; `Store.execution_grant_basis()` raised `StoreError: receipt attempt gap lacks terminal no-execution evidence` at `tools/vst/store.py:1386` |
| Test file SHA-256 at run | `6dee066eede9fdd439c753af4c3c5af19760534e437333b66910384eafcef438` |
| Tracked binary diff SHA-256 at run | `89db971788b8a322380fa8e12d00df455c77cec5ddec5903f73a612440a10fd6` |
| Protected pre-existing evidence | `docs/sdlc/evidence/s2-functional-test-run.md` was not read or modified and is excluded from this fingerprint. |

Source and test file identities at the run:

| Path | SHA-256 |
|---|---|
| `tools/vst/store.py` | `ca1153a128e1dedc83aedcb837e2521d663637af8eca2388ac4c5e0bdf2a222a` |
| `tools/vst/gate.py` | `05da518929bb21f0d52383f4fb8742a482cbc17dc2c9a705780ea89799dde620` |
| `tools/vst/execution_grant.py` | `f99810d04664f6d95e336be2138001c2e255e6ae9e8eb531b806d745fc4c7c43` |
| `tools/vst/supervisor.py` | `d6ed3463d3a830a4cf46424a9e3fb8d9d79b173b559e03184646d9fa7e3ec55f` |
| `tools/vst/supervisor_service.py` | `684eabcca773fe54a6fcaab7936e05b8bcad2940f6dca128c6644ad8e3c83a78` |
| `tools/vst/runner_service.py` | `a4357d4757e8a4a307b0c952c5df4eda73773b64af4eecf53ad5a8fdddfe1d7f` |
| `tools/vst/systemd/vst-runner.service` | `4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be` |
| `tests/vst/test_s2_persistent_runner_service.py` | `6dee066eede9fdd439c753af4c3c5af19760534e437333b66910384eafcef438` |
| `tests/vst/test_s2_runner_lifecycle.py` | `fbed70655086bb84f2ba0fc2b203756f3c83778edd49f1d60e1c85f02ec29394` |

## Acceptance mapping and observed outcome

| Acceptance behavior | State | Evidence / limitation |
|---|---|---|
| A terminal `NO_EXECUTION` disposition is bound to its exact claim and blocks later reservation | Focused module included this regression; aggregate run passed except the failure listed above | The test module completed 54 cases successfully, but quiet output did not map each passing dot to a node ID. This run did not exercise a live Supervisor RPC or installed service. |
| A verified no-execution gap can be followed by a receipt while preserving the actual receipt hash chain | Partially exercised | The newly authored safe pre-spawn receipt-gap scenario was in the focused module. Exact per-node outcome was not collected in quiet mode; overall module had one unrelated-to-that-case failure listed below. No final acceptance claim is made. |
| An unresolved/reserved predecessor cannot be skipped using caller-supplied gate evidence | Focused module included these regressions; aggregate run passed except the failure listed above | Store-derived gate behavior only; no external service or process boundary was exercised. |
| A pre-reservation runner failure terminalizes the exact pending claim without reserving or spawning | Focused module included this regression; aggregate run passed except the failure listed above | The test used an in-memory Store/fake callbacks and did not establish actual child-process or systemd behavior. |
| Owner/lease authority must cover the full manifest timeout and completion margin at grant issue, claim, and reserve | Focused module included boundary regressions; aggregate run passed except the failure listed below | In-memory Store and fake clock only. |
| Operator reconciliation is versioned and restricted to a configured operator peer | Focused module included a framed RPC unit-path regression; aggregate run passed except the failure listed below | Fake peer credentials/cgroup; no live UID, PIDFD, socket, account, or key provisioning was exercised. Endpoint remains inactive in deployment. |
| A separately authorized successor after a signed `EFFECTS_RESOLVED` resolution can eventually produce its receipt | **FAIL** | After reconciliation was accepted and attempt 2 acquired under normal lease/preflight rules, `execution_grant_basis()` rejected it because there was no prior receipt for attempt 1. This conflicts with the existing test’s accepted successor contract and needs source/contract resolution before further selectors run. |

The warning was pytest-asyncio’s deprecation notice for `asyncio.get_event_loop_policy`, scheduled for removal in Python 3.16.

## Test stop and remaining scope

This was the only command run in this pass. After the failure, no E1, E2, or E6 selector groups were started. Further test execution is paused pending source-owner resolution of the failed EFFECTS_RESOLVED retry path. No full suite, checks, build, CI, migration, runtime/systemd, provisioning, prohibited process/crash/recovery/mutation/E8/policy scenario, commit, or push was run by this pass.
