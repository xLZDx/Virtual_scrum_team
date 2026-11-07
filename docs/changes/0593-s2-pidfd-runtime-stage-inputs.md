# Change 0593 — Pin refreshed S2 stage inputs after the concrete pidfd fix

Date: 2026-10-30
Owner: Codex
Task: S2-4 exact runtime/config bundle preparation

The delivered compatibility fix a600774649527ff0b33eb81f4d431f8226119b2c must be present in the
runtime used by this qualification. The earlier ef465cd stage remains accepted historical
work; it is not rewritten. New source publication is justified by the concrete missing Python
socket-option name, 45 focused passes and actual kernel-pidfd evidence in change0592.

Prepared with the existing committed prepare_wsl_runtime_plan.py utility:
source plan SHA-256 620e4614929109e2c7689781943bf50e5cf5ad29703d407cb7ebef019cbff29d.
The exact member map includes peer_pidfd.py and the six existing service units.

The e2e-runner collected actual current target metadata, bound to the same source revision:
inventory SHA-256 c61bc6c10a042d207d2d7d15b3d58b8b69e331cad885624b88d1fb980c54c049.
Compiler resolves to /usr/bin/x86_64-linux-gnu-gcc-13, root:root 0755, SHA-256
1b99826121ae6682a634e5efe09bd3e3df58ce58e0b28f849114ab5b89139c26. Observed at
2026-10-30T01:15:38.272815+02:00. Windows mounts are absent, service units inactive/not-found,
and the inspected Store target is absent. These are observations, not production acceptance.

The existing installer requires exact plan and inventory files to be committed, with matching
byte hashes and inventory age at most 300 seconds; this commit preserves those enforced input
identities. Security review checked the unchanged stage-only boundary and exact source plan;
target-bound inputs are rechecked before execution. Existing user GO covers the technical work.

Files: docs/sdlc/evidence/s2-runtime-source-plan-a600774649527ff0b33eb81f4d431f8226119b2c.json;
docs/sdlc/evidence/s2-runtime-target-inventory-a600774649527ff0b33eb81f4d431f8226119b2c.json;
core/DECISION_LOG.md; this change record. No new tests were required or executed for this
metadata commit. Next action: use the strict StageOnly wrapper while inventory is fresh, retain
its actual result, and complete bundle pins. This commit itself installs or activates nothing.
