# S2-4 PM08-05 read-only mount audit outcome

Date: 2026-10-31 (UTC)

## Scope and authorization

- Current task: `S2-4-runtime-owner-runner-qualification` (`REQ-003`).
- Experiment: `s2-ro-hardening-audit-20261101-pm08-05`.
- Authorization: GPT-PM one-shot `S2-4-PM08-AUDIT-ONESHOT-20261101-16`, request `1dd17615-8b62-4d15-9e44-3417176cfba6`.
- Retry cap: `0`; this authorization is consumed and must not be reused.
- Candidate at execution: `a14ad9a10e50e4a1a7f046810112d11456b5222f`.
- Launcher SHA-256: `02c1d55cbf46cf9f16e4fd693e1e7ab08a16da7bc1dd4d5d27ef7d86af83bc8e`.
- Helper SHA-256: `eecc4b9b6feb48ca28c468d0cc9ebe32f120a3f493b8a96ab5e76863cd5ee049`.
- Derived transient unit: `vst-s2-qual-b3ec321a7359c8aa.service`.

Exact command:

```text
python tools/qa/run_s2_runtime_qualification.py --mount-audit-only --experiment-id s2-ro-hardening-audit-20261101-pm08-05 --expected-launcher-sha256 02c1d55cbf46cf9f16e4fd693e1e7ab08a16da7bc1dd4d5d27ef7d86af83bc8e --expected-helper-sha256 eecc4b9b6feb48ca28c468d0cc9ebe32f120a3f493b8a96ab5e76863cd5ee049
```

## Result

- Start: `2026-10-31T22:23:53.952722Z`.
- Finish: `2026-10-31T22:23:53.961299Z`.
- CLI exit: `2`; terminal: `HOLD`.
- One top-level WSL process; not timed out; writer error: `null`; no retry.
- The exact inaccessible-path mismatch was one missing entry: `/init`. `unexpected` was empty. The expected set otherwise matched the observed set.
- The transient unit precheck was `LoadState=not-found`, `ActiveState=inactive`, `SubState=dead`, `MainPID=0`, `Result=success`; it was not already running before this authorized diagnostic.
- The transient `systemctl show` query exited `0` and returned 848 bytes, SHA-256 `a4cbcca4ec81ba7f2a270725b4c138ff76365b52601c6ca23da3c37317fe586a`. The raw property lines were not retained, so effective property values are `NOT_OBSERVED` in durable evidence.
- Outer stdout: 2,543 bytes, SHA-256 `40f6a750fe865bf34a064b3d24e1d0e30024b85e7475cff59144525c363b8eb6`; stderr empty, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- The launcher printed the result to stdout and created no evidence file for this mount-only mode. The mismatch arrays above are transcribed from the designated `e2e-runner` report of that exact invocation; the full raw stdout is not available as a durable repository artifact.
- The helper stopped at the unit-property mismatch before reading mountinfo. Namespace, mount rows, Windows mounts, effective masks, and private `/dev` are therefore `NOT_OBSERVED` for PM08-05.
- No runtime selector, service, key, activation, dispatch, E5 signing, Owner-to-Runner submission, or report-bound TestRun ran.

## Follow-up implementation and evidence

The diagnostic code change was committed as `01a25158fca6e83bbb427271fe632ffebee545b2` and normally pushed to `origin/s2-canonical-continuation` (`a14ad9a..01a2515`). It applies only to explicit `MOUNT_AUDIT_ONLY` mode: a path mismatch is retained while read-only mountinfo is collected, and the result is forced to `HOLD`; normal runtime preflight still stops immediately. `/init` remains in the required target set.

- Focused synthetic tests: `python -m pytest -q tests/vst/test_s2_runtime_qualification_harness.py -k 'pm08_readonly_audit_keeps_mount_inventory_when_init_property_is_missing or pm08_runtime_preflight_still_stops_on_missing_init_property'` — exit `0`, `2 passed`, `59 deselected`, one `pytest-asyncio` deprecation warning. No WSL/runtime execution in these tests.
- Python and security reviewer agents: no concrete findings.
- GPT-PM code review `S2-4-PM08-CODE-REVIEW-20261101-17`: `APPROVE`, 0 BLOCKER / 0 MAJOR / 0 MINOR; approves only the exact code candidate for normal commit/push. It grants no new WSL audit, runtime, TestRun, E5, Owner-to-Runner, service, dispatch, or production authority.
- S2 draft PR: https://github.com/xLZDx/Virtual_scrum_team/pull/2.

## PM08-06 follow-up

- Authorization: GPT-PM one-shot `S2-4-PM08-AUDIT-ONESHOT-20261101-18`, request `7a0d114a-b652-4cf0-8f0e-bc3405987581`, bound to HEAD `01a25158fca6e83bbb427271fe632ffebee545b2`; retry cap `0`.
- Experiment `s2-ro-hardening-audit-20261101-pm08-06` ran exactly once in mount-audit-only mode after source/HEAD/unit/evidence-path preflight passed.
- Artifact: `docs/sdlc/evidence/s2-ro-hardening-audit-20261101-pm08-06.json`, 8,529 bytes, SHA-256 `964d27b8381c83df5597b148e40c5011095545e1fe9c4a7d65f5755a1ab4cdfc`.
- The raw artifact remains as a local working-tree file. The repository's text normalization changes its bytes, so it is not staged or included in a commit; its original hash remains the integrity reference.
- Result: inner CLI exit `2`, terminal `HOLD`, reason `helper has unexpected open file descriptors`; no retry. It preserved the `/init` mismatch (`missing=["/init"]`, no unexpected paths) but still stopped before mountinfo. FD names, mountinfo, effective masks and private `/dev` remain `NOT_OBSERVED`.
- The observed false/ambiguous FD check was based on `Path.iterdir()` over `/proc/self/fd`, which can enumerate its own temporary iterator descriptor. This is an implementation-based hypothesis; PM08-06 did not retain the numeric FD list.
- New delta `165f8ae877fcdc71a91739cfe411c44bf9db82f2` replaces that enumeration with `os.listdir` plus `fstat`: only a descriptor already closed at inspection (`EBADF`) is ignored; a still-open unexpected FD is recorded and remains `HOLD`.
- The designated `e2e-runner` ran five focused synthetic selectors at base HEAD `01a25158fca6e83bbb427271fe632ffebee545b2`: `5 passed, 58 deselected, 1 pytest-asyncio deprecation warning`. Python and security reviewers found no concrete issue. GPT-PM code review `S2-4-PM08-CODE-REVIEW-20261101-19` approved the exact source/test hashes for commit/push only (0 BLOCKER / 0 MAJOR / 0 MINOR). Commit `165f8ae` was normally pushed to `origin/s2-canonical-continuation` (`01a2515..165f8ae`).

## Current status and next step

## PM08-07 follow-up

- Authorization: GPT-PM one-shot `S2-4-PM08-AUDIT-ONESHOT-20261101-20`, request `9b57793b-36a4-44f4-873d-c165693bb493`, bound to HEAD `f0bda6abc06dd9dc759ebcada3b3754609083b5e`; retry cap `0`.
- Preflight passed for exact HEAD/branch/upstream and source hashes. Experiment `s2-ro-hardening-audit-20261101-pm08-07` used one exact mount-audit-only command; no retry.
- Inner CLI exit: `2`; stdout `0` bytes, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; stderr `108` bytes, SHA-256 `a000dfbbb93505288b28547ebda5b3ebb9c639b6e11364668e957214725c73cb`.
- No valid JSON stdout was emitted, so the authorized artifact `s2-ro-hardening-audit-20261101-pm08-07.json` was not created. The executor did not retain the stderr text; the refusal reason is `NOT_VERIFIED`, not inferred. PM08-07 is consumed and cannot be retried.
- After the run, local read-only checks confirmed the helper and launcher working-tree SHA-256 values still match the committed expected values and the pinned mount-decoder baseline commit exists. These checks do not identify the refusal reason.
- No mountinfo, effective masks, private `/dev`, runtime selector/TestRun, service, configuration/key, E5, Owner-to-Runner, dispatch, or production evidence was produced.

## Current status and next step

## PM08-08 follow-up

- Authorization: GPT-PM one-shot `S2-4-PM08-AUDIT-ONESHOT-20261101-21`, request `d1a534cf-8520-4b55-a395-edaf8e33464e`, bound to HEAD `d9014a7a99c16dd5e9f78a941c0be1c5acc65fc6`; retry cap `0`.
- The designated executor reports that it invoked the exact PM08-08 command once, but the `functions.exec` result carrying its metadata was truncated before the runner recovered it. The permitted artifact path `s2-ro-hardening-audit-20261101-pm08-08.json` is absent.
- Exit code, timestamps, stdout/stderr byte counts and hashes, exact stderr, terminal result, and mount facts are `UNKNOWN` because the executor could not recover them. No JSON artifact was recorded. PM08-08 is consumed; do not retry.
- The executor has been asked to inspect whether its tool output/cell can be recovered, without rerunning. No execution fact beyond the reported consumed invocation and absent artifact is upgraded to verified evidence.

## Current status and next step

S2-4 remains `IN PROGRESS`; S2-5 is queued and not started. PM08-05 through PM08-08 are all consumed and must not be retried. Before seeking another one-shot diagnostic, fix the executor's output-capture boundary so required run metadata and bounded stderr text survive tool output limits; inspect the exact PM08-08 tool result if recoverable. Any later runtime attempt needs a new exact PM decision bound to its then-current pushed HEAD. Runtime selector/TestRun, service activation, current E5, Owner-to-Runner, dispatch and S2-4 closure remain open. Owner: Codex for evidence and coordination; GPT-PM for adjudication.

## PM08-09 follow-up (2026-11-01)

- Authorization: GPT-PM decision `S2-4-PM08-AUDIT-ONESHOT-20261101-27`, request `6de57b2c-b114-43e4-a916-b33f7fd44f74`, bound to HEAD `470de5372866a33898e455a8d06931bd977d36e7`; one diagnostic invocation, retry cap `0`. It supersedes the incorrect helper-hash text in decision `-26`. GPT-PM independently verified the exact helper SHA-256 `d4b54e03ef3ab7a5739acf6402adeeb3cf02b329e0954abb6adfd53c33509ff1` and launcher SHA-256 `02c1d55cbf46cf9f16e4fd693e1e7ab08a16da7bc1dd4d5d27ef7d86af83bc8e`.
- The designated `e2e-runner` performed one read-only preflight under decision `S2-4-PM08-PREFLIGHT-20261101-25`: exit `0`; exact unit `vst-s2-qual-d28cb8218254859e.service` was `not-found/inactive/dead`, PID `0`, result `success`; relevant systemd jobs and matching process command lines were empty. The exact compact preflight JSON was recovered from the executor's existing tool result; no retry occurred.
- PM08-09 diagnostic command ran exactly once with the exact `--mount-audit-only` selector and approved hashes. Exit `2`, terminal `HOLD`, no timeout; outer captured stdout `77,896` bytes, SHA-256 `d43f070f3d3477feee31cdfa1ad4d725661898942b8e84ab27df33cdc1252c2b`; stderr `0` bytes (empty SHA-256); the helper exited `2`, stdout `38,482` bytes, SHA-256 `6f3c09b1a65db3ba5f2c3489d1f5b9da0da99389b817d22a4be3d2f6b3d1811a`. No runtime selector or VST service start occurred.
- The executor's parsed in-memory report summary was `HOLD`: the inaccessible-path property omitted `/init`; mountinfo showed the unmasked `/init` rootfs row; effective-mask checks reported `/init`, `/proc/latency_stats`, and `/proc/mtrr` missing or ambiguous; private `/dev/pts` contained unexpected character entries `0` and `1`. These are executor-reported parsed findings; the full captured stdout was not retained byte-for-byte in the repository.
- The authorized path `docs/sdlc/evidence/s2-ro-hardening-audit-20261101-pm08-09.json` was created, but its bytes do not match the captured stdout: local read-only measurement found `80,223` bytes, SHA-256 `c4731ca05bc1d6ac55f9263b427bb0d61245b2226f9e9f8471e9843f12847713`, versus the captured stdout `77,896` bytes / `d43f...`. The artifact parses as JSON, but raw-output integrity is **NOT VERIFIED**; do not treat it as the exact stdout artifact or stage it. Cause is `UNKNOWN`; the file is preserved, with no deletion or retry.
- Static comparison of the parsed mount rows and the helper's current mask-type constants suggests `/proc/latency_stats` and `/proc/mtrr` may be classified as directories although the reported effective masks are regular-file masks. This is an implementation hypothesis pending trustworthy exact-output evidence; no source change was made. The `/init` mismatch and extra `/dev/pts` entries also remain unresolved.
- GPT-PM decisions `-22`/`-27` authorize only the one consumed diagnostic. They explicitly do not authorize the manifest TestRun/runtime selector, service activation, config/key reads, E5, Owner-to-Runner, dispatch, production, S2-4 closure, or S2-5. No TestRun was run under these decisions.

## Current status and next step

S2-4 remains **IN PROGRESS**; S2-5 remains queued. PM08-09 is consumed and must not be repeated. Owner: Codex for the next task-local acceptance/evidence step; GPT-PM for the required separate runtime/TestRun authorization and exact source adjudication. Next: reconcile current S2-4 state and prerequisites from in-scope records, then obtain a distinct exact decision for the manifest's report-bound TestRun; do not start another WSL invocation or claim runtime/E5/Owner-to-Runner acceptance under PM08-27.

## Post-PM08-09 source correction and code-only delivery (2026-11-01)

- The current-turn source delta corrected the two mask-type classifications (`/proc/latency_stats`, `/proc/mtrr` are regular files), added `/init` to the launcher's static mask set so it matches the WSL helper, and removed the optional `-` prefix from every `InaccessiblePaths` target. Missing, ambiguous, or malformed masks remain fail-closed; `/dev/pts` remains a separate required exact `devpts` mount.
- The designated `e2e-runner` reported three focused local harness groups at base HEAD `470de5372866a33898e455a8d06931bd977d36e7` plus the exact worktree delta: parity/launcher **3 passed**, mount/security **32 passed**, and prestart allowlist **6 passed**; each command exited `0` with one `pytest-asyncio` deprecation warning. The initial expanded attempt had six AST-fixture failures; the fixture dependency closure was corrected and those selectors were rerun successfully. No primary-session test execution occurred. No WSL, report-bound TestRun, E5, service activation, or Owner-to-Runner run occurred.
- GPT-PM request `46fce9d5-781e-480e-b21e-6463961068a0`, decision `S2-4-PM08-CODE-REVIEW-20261101-29`, returned **APPROVE**, 0 BLOCKER / 0 MAJOR / 0 MINOR for the three exact attached files, code commit/push only. Approved attachment SHA-256 values: launcher `11e2eea024fa5bfae7d7899d1ea05e20fb358b1e845a88167d0e95fbaa426d5a`; WSL helper `8cf5a4bbe089170f90ff0ef1cf78eb984935de4dc772842af03a9b6f0fd427a2`; harness tests `e29c2f0823bd1ec9040f54859916d53136cd0b7a9825b824639202a1750c1e91`. Local exact-byte verification matched all three hashes before commit.
- Commit `67361bb` (`Fix S2 runtime qualification mask targets`) was created on `s2-canonical-continuation` and pushed normally; output was `470de53..67361bb  s2-canonical-continuation -> s2-canonical-continuation`. The approved delta contained exactly those three files. Existing dirty backlog/reports and untracked evidence were not included.
- Runtime acceptance remains open. Decision `-29` expressly grants no WSL diagnostic, report-bound manifest TestRun, E5, Owner-to-Runner, activation, production, or task closure. The current manifest still has `base_head=ee69f9fbf074a4c73d2d5d1da81c627a57d06071` and only `tests/vst/test_s2_assignment_basis.py` in `change_scope.allowed_paths`. A read-only diff-gate preflight found 32 tracked changed paths and 131 nonignored untracked paths from that base in the current checkout; with the existing one-path scope, a report-bound TestRun cannot produce a passing diff gate from this state. Do not launch it before reconciling the scope and checkout without dropping or broadly admitting unrelated files.

## Current status and next step

The mask/launcher source correction is implemented, focused-tested, internally reviewed, GPT-PM approved for code-only delivery, committed and pushed as `67361bb`. S2-4 remains **IN PROGRESS**: current run-bound E5, report-bound TestRun, and real Owner-to-Runner evidence remain `NOT_RUN`; PM08-09 is consumed and its `HOLD` is not replaced by this source correction. Codex owns reconciling the report-bound manifest scope and preparing a safe current-source runtime evidence request; GPT-PM owns adjudication of any manifest/runtime contract change and exact one-shot permission. S2-5 remains queued and S3 unstarted.
