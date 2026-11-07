# Change 0523: clarify S2 latch storage-failure limits

## Why

While reconciling the 0522 fail-stop correction, the records needed to distinguish a confirmed
socket stop from a durable admission fence. If latch persistence fails, the socket is inactive at
the confirmation point, but the absent file cannot block a later explicit start or a future boot.
The prior shorthand that same-boot admission "remains closed" overstated the evidence.

## What changed

- Updated S2 state, service contract, admission-fence adjudication, runtime provisioning plan and
  systemd README to state that without a persisted latch, only the observed inactive socket state is
  established; a later explicit start is not guarded and cross-reboot safety is unproven.
- Recorded the required operational boundary: durable root-controlled `/etc` must be healthy and
  the persistent fence must exist before any later start or reboot. This is a runtime dependency,
  not evidence supplied by the source template.
- Corrected current S2 status to record that `git diff --check` passed, while application tests,
  systemd unit validation and runtime behavior remain pending the designated executor/review.
- No implementation code changed in this documentation correction. The protected existing test-run
  artifact was not read or modified.

## Verification and acceptance

- `git diff --check` passed for the documentation correction before staging; this change is
  documentation-only.
- The designated test executor is running the focused S2 suite against source HEAD
  `34bd7dc1b085789341b29937655af52e07f2ddbd`; its outcome is pending and is not claimed here.
- Root helper invocation, `/etc` writes, account/group creation, service activation, dispatch, E5,
  push, PR and merge remain not performed. S2 is not approved and S3 remains unstarted.
- Codex owns the record and follow-up; GPT-PM owns M03 adjudication; the operator owns any future
  privileged runtime recovery.
