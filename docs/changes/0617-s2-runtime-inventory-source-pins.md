# S2-4.12b — reconcile runtime inventory source pins

Date: 2026-10-30
Task: S2-4 runtime owner-to-Runner qualification
Owner: Codex (implementation and coordination); GPT-PM (exact-head review/runtime authorization)

## Acceptance delta

GPT-PM source review approved validator/applier commit `f9f488f332275b5d49924d0d5e7cf26fc1c5a27f` under request `842284ce-6e87-4a4e-91a1-253ac89eb74b`. The normal push succeeded (`1b5dd9d..f9f488f`). GPT-PM then authorized exactly one new inventory and a conditional apply/preflight/TestRun sequence under request `733857ce-024e-42ab-b65a-25e12162dc38`, correlated reply `6402ed93-9fb2-5569-8710-50b32034b531`, bound to that HEAD and exact hashes.

The one inventory invocation produced raw JSON at `docs/sdlc/evidence/s2-runtime-target-inventory-f9f488f.json` (SHA-256 `d4dc31bcd0eb97478677a844b80c2f7ccfbb9d176a8197b52c4a7ea7cdb340a9`). The committed verifier ran once and refused before apply: it expected a stale applier SHA, while the authorized inventory and committed applier were bound to the current SHA. The qualification transcript is `docs/sdlc/evidence/s2-runtime-owner-runner-qualification-f9f488f.json` (SHA-256 `9fd5ce690dd15d116a1af3aac0c1da904776ebd9e69e83488eece0e62e924b56`). No configuration apply, root preflight, durable claim, probe, or TestRun occurred. The candidate tuple remains unclaimed and unapplied.

The raw inventory also records that PID 1 namespace collection attempted `/proc/1/ns/mount` and returned `FileNotFoundError`; the required Linux proc namespace path is `/proc/1/ns/mnt`. The inventory therefore lacks mount namespace and complete PID 1 UID/GID fields and would not satisfy the acceptance gate even after fixing the stale digest. This is a collector command defect, not evidence that the namespace is unavailable. The old installed bootstrap identity is the exact consumed baseline tuple, as required; the candidate collision field is false.

## Change

The validator no longer hard-codes a potentially stale applier digest. It derives validator and applier SHA-256 values from the exact expected Git HEAD blobs, requires each working file to be byte-identical to that blob, and requires the inventory source identity to carry those exact hashes. This keeps source pins aligned with each approved revision and refuses dirty or mismatched source.

## Verification and review

The designated `functional-test-reviewer` ran only:

```text
python -m pytest -q tests/vst/test_s2_runtime_config_inventory.py
31 passed, 1 existing pytest-asyncio deprecation warning; exit 0
```

The role reports Python 3.14.3 and HEAD `f9f488f332275b5d49924d0d5e7cf26fc1c5a27f`; the latest validator/test changes were uncommitted working-tree changes at that HEAD. Code and security reviewers found no concrete issue in dynamic exact-blob pinning. Tests were not run by the primary agent.

## Current disposition and next action

S2-4.12b remains open. The source correction is not yet committed, approved at the new exact HEAD, or pushed. After that delivery, Codex must obtain a new bounded runtime authorization because the previous authorization's one inventory invocation and one verifier invocation have both been used. `e2e-runner` then owns one fresh collector run with `/proc/1/ns/mnt`, complete PID 1 UID/GID from `/proc/1/status`, all required identity/fingerprint fields, full raw JSON persistence, and exact source pins. Run the committed verifier once. Apply only if it returns PASS and every authorized predicate passes; otherwise stop with exact evidence and no retry.

The restricted process-kill, crash, mutation, E8, and policy selectors remain `NOT_RUN`. No S2-5 or later sprint task is started by this record.

## Fresh authorized attempt and collector fix

The first fresh authorization in this turn was GPT-PM request
`53f946da-755c-4859-adca-6bfd64fb2293`, correlated reply
`09ac688e-5ded-5b7b-aa9c-5e6a69e13ff7`, bound to the same HEAD and source pins. Its sole read-only
inventory had SHA-256 `7a7e97b1e9a7dedbfd57592c3df66fea7ff6847c0a6ff3e77d6e49abd5b168d0`; it omitted
`readiness.units`, so the sole validator run refused with `inventory does not contain exactly the
nine required VST units`. No apply, preflight, claim/probe or TestRun ran. The exact artifacts are
`docs/sdlc/evidence/s2-runtime-target-inventory-2e6a796.json` and
`docs/sdlc/evidence/s2-runtime-owner-runner-qualification-2e6a796.json` (wrapper SHA-256
`da3746a03202be2c9c177a3483a56749a99ac8c60ac7c116e9b2ed5fc73be028`).

GPT-PM request `a2bd39ce-8ae4-4416-9b82-56382a610c92`, correlated reply
`80091d4f-cbf2-5c72-af15-7ef9a48020bf` (PM Bridge job
`73fc347e-9e50-475c-96dd-ae0759e3e76a`), authorized one new inventory and one committed-validator
run on HEAD `2e6a796eaa04664812cf1266322b083f18770fa1`, with apply/preflight/TestRun conditional
on every prior step passing. No repeat was permitted. The new read-only inventory recorded D:
as read-only 9p, matching source pins, boot and PID 1 identity, accounts, all 26 baseline fingerprints,
nine systemd units and the unclaimed candidate. Its SHA-256 is
`acb6b116aa66f4ba764a9e7c9ad505b90574323ed16129a71a61a970956e151c`. The single validator run
refused with `REFUSE: selected runtime path differs from the pinned S2 runtime`: the observed
selector was recorded at the inventory top level but omitted from `readiness.runtime_selector`.
The selector value itself matched the pinned candidate. This was a collector serialization defect;
no target predicate failure was established. No apply, root preflight, claim/probe or TestRun ran.
The exact inventory and full qualification transcript are
`docs/sdlc/evidence/s2-runtime-target-inventory-a2bd39ce.json` and
`docs/sdlc/evidence/s2-runtime-owner-runner-qualification-a2bd39ce.json` (wrapper SHA-256
`ef84d142d52e0fe8c19364d360bc91209fdcc7bf3525709cd017fd419538a87c`).

To avoid more hand-assembled runtime JSON, this task adds
`tools/qa/collect_s2_runtime_config_inventory.py` (current SHA-256
`453fe70732c7309158cab7a0876b6bb7347b895056969ef87dbf988dd8cfa838`). It assembles all required readiness fields from
one capture, validates complete unit/identity observations, rejects source-pin mismatches and
failed command results, and derives Ubuntu version from the captured `/etc/os-release`. The
functional-test-reviewer ran `python -m pytest -q tests/vst/test_s2_runtime_inventory_collector.py`
at HEAD `2e6a796eaa04664812cf1266322b083f18770fa1`: 35 passed, one existing pytest-asyncio
deprecation warning, exit 0 (Python 3.14.3). The code reviewer found and verified closure of three
source-pin/command-result/distro issues and one fail-open probe-identity issue; the security review
also found two LOW issues, now fixed: Git subprocesses strip inherited `GIT_*` overrides and verify
the resolved checkout root, while `getent` output is redacted before observation serialization.
Both code and security reviewers re-reviewed the final source and found no remaining material
finding.

S2-4.12b remains open. The collector change, focused tests, and both fresh-attempt evidence files
form the current task delta. The next actions are one task commit, exact-head GPT-PM code review,
normal push, then a new one-shot runtime authorization bound to the pushed HEAD and collector SHA. The
next `e2e-runner` attempt must execute the committed collector itself, persist its raw stdout before
running the committed verifier once, and stop on the first refusal or failure. No S2-5 or later
task starts until S2-4.12b and the rest of S2-4 meet acceptance.

## Exact-head review finding and current remediation

GPT-PM review request `cf7a9515-0cd8-47d2-a0cb-1c351a3ef1e0`, bound to local HEAD
`1a7dca5527dbe48324426f9b5f56621e85a6279b`, returned HOLD / MAJOR-01. The collector populated
`units` and `runtime_selector` inside `readiness`, but kept six other validator-required fields
only at the inventory top level: `store_present`, `preflight_present`, `attestation_present`,
`container_sockets`, `candidate_identity_collision`, and `installed_bootstrap_identity`. The
committed validator calls `_validate_readiness(inventory["readiness"])` and checks all six there,
so a new runtime inventory would deterministically fail despite valid top-level observations.

The current correction adds `assemble_inventory()` as the single persisted-schema path.
It receives each captured state once, validates the boolean/socket/identity shapes, writes the six
fields into `readiness`, and writes those same values at top level. `main()` now uses this assembler.
The functional-test-reviewer updated helper tests and added an integration regression through this
production assembly path and the real validator. Missing and contradictory cases cover all eight
duplicated readiness fields. The focused command
`python -m pytest -q tests/vst/test_s2_runtime_inventory_collector.py` returned 52 passed, one
existing pytest-asyncio deprecation warning, exit 0, Python 3.14.3, at HEAD
`1a7dca5527dbe48324426f9b5f56621e85a6279b`. The code reviewer re-reviewed the updated integration
contract and found no actionable B/M issue; security review reports no actionable B/M finding. The
functional-test-reviewer then reran the same command at committed HEAD
`b927a438a72d14a31229c9d0ad7514a19606c98e`: 52 passed, one existing pytest-asyncio deprecation
warning, exit 0, Python 3.14.3. A later task-record-only amendment did not change collector or test
bytes. The implementation and tests are committed locally, but the task is not PM-approved, pushed,
or run on the target.
