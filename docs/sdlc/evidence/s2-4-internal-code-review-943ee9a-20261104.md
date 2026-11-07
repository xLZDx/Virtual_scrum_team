# S2-4 bounded internal code review — 943ee9a

- Task: `S2-4-runtime-owner-runner-qualification` (REQ-003)
- Reviewed HEAD: `943ee9af3361df74f513e5c4f361a57ca1b2df8f`
- Reviewer: `code-reviewer` agent (read-only)
- Review scope: `assignment_basis.py`; `Store.authenticated_assignment_basis`; `Supervisor.assignment_basis`; the manifest-authorized selector and `test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment`; and the exact bootstrap apply call chain proposed in `s2-4-bootstrap-apply-proposal-20261104.txt`.
- Internal code-review verdict for this bounded scope: no material findings. This Markdown record is **not** the manifest-required signed VST `IndependentReview` receipt.

## Evidence

The selector test verifies that the returned handoff is the exact stored journal object, is not enriched with `payload_sha256`, and has canonical wire bytes equal to the persisted result. The Store path validates an enriched copy and returns the stored result unchanged. These source and test files are unchanged from the accepted test revision `173b7af` through reviewed HEAD `943ee9a`.

The proposed one-shot command calls `tools.vst.bootstrap_runtime.main` with the `apply` operation. Its `apply` function enforces root execution, the reviewed manifest digest, fixed paths, inactive/unconfigured units, and empty systemd jobs/cgroups before applying the selector and six unit files. It does not invoke `tools/qa/apply_s2_runtime_configuration.py`, reload systemd, or start/stop services. This source-level review does not authorize or execute that mutation; the correlated GPT-PM authorization remains absent.

## Separate finding and limits

The wider code delta also contains a reachable stop/restart path in `tools/qa/apply_s2_runtime_configuration.py` (reviewed at lines 894–910 and 953–980). That capability is outside the exact bootstrap command reviewed above, so it is not a finding against this bounded one-shot operation. Keep it visible for the broader runtime-applier scope; do not infer that it is safe for arbitrary active-service configuration applies.

This review was source-only. No tests or runtime commands were executed. The existing selector test uses synthetic fixtures and does not establish production writer identity, key custody, current E5, or a real Owner-to-Runner result.

## Manifest receipt status

`task-manifest.json` requires a `TestRun` receipt in `runtime-tests` and a signed VST `IndependentReview` receipt in `independent-review`. The agent's source-review opinion does not satisfy the cryptographic VST receipt contract: `tools/vst/gate.py` verifies the designated reviewer key/signature and requires a reviewer principal distinct from manifest author `Codex`. No such receipt was emitted in this turn. Runtime qualification remains open.
