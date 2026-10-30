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
