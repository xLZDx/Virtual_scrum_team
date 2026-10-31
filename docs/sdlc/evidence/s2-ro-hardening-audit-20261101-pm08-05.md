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
