# S2-4D apply-child mount remediation review — 2026-11-06

Prior GPT review request `4301af46-7fc8-47dd-a80b-214d669cbab1` returned `MODIFY — 1 MAJOR`: post-remount mount ID was not compared with the created mount ID. The code now compares them and fails before manifest, inventory, or configuration payload processing; guarded cleanup refuses to unmount the replacement ID.

The e2e-runner executed `test_remote_apply_fails_closed_when_mount_id_changes_after_remount`: exit 0, 1 passed, 1 pytest-asyncio deprecation warning. Evidence: `s2-4d-apply-guard-mount-id-replacement-20261106.attempt.json` and adjacent console transcript. Source/test SHA-256 values in the record match the reviewed attachments.

Independent final remediation review request `4301af46-7fc8-47dd-a80b-214d669cbab2` returned `APPROVE — MAJOR-01 CLOSED`, BLOCKER 0, MAJOR 0, no further remediation. It accepted the supplied test evidence and states that config apply and REQ-003 runtime remain NOT_RUN. Earlier Python/security review found and drove fixes for owned mount cleanup on RO remount failure, mount-ID cleanup identity, and host failure on cleanup errors. The prior 12-case focused regression set passed before the final mount-ID guard was added.

Owner: Codex. This evidence is source/test approval only; it is not a runtime TestRun or S2-4D acceptance closure.
