# S5-E GPT-PM code review scope

Task: S5-E (VST-042), exact-head gate and reproducible evidence integration. Base c87ed6e (S5-D accepted), head = current HEAD. Review: tools/vst/gate.py, tools/vst/analyzer_evidence.py (new), and the supporting edits in tools/vst/contracts.py (v3 manifest: mandatory StaticAnalysis slot, static_acceptance_ids) and tools/vst/analyzer_authority.py (verify with consume=False), plus the schema README.

Delivers (plan docs/S5_AEVE_GATE_PLAN_2026-10-24.md E5/E6, AC-9..AC-13): the S5-A fail-closed v3 stubs are replaced by real handling. A v3 manifest must declare a StaticAnalysis slot and static_acceptance_ids; the static slot is satisfied only by analyzer-authority-signed v3 evidence that verifies with the full role-key roster, pinned analyzer/profile identity, frozen catalog (re-hashed against FROZEN_CATALOG_SHA256, required rule set equal to the manifest), scope covering the manifest scope, verifier-owned expected values (run id, nonce, digests), candidate head and epoch equal to the gate's current ones, coverage FULL and derived result PASS. It credits only static_acceptance_ids and cannot satisfy test or review slots. The one-shot nonce is consumed once at the end, only on an APPROVE / APPROVED_WITH_WAIVER verdict without hard reasons. v1/v2 behaviour unchanged; exact version compare. analyzer_evidence builds a deterministic, validated evidence record with derived fields and NOT_RUN/UNSUPPORTED labels, and verify_evidence_record is bound to an expected head and manifest sha256.

Already fixed after three read-only reviewer passes (security 5, python 3, functional-test 4 MAJOR).

Settled, do not reopen: S5-A..D accepted; the gate has no built-in source for the analyzer key, role roster and nonce store, so the caller injects them (analyzer_trust), and the caller must fill the expected values from the runner's own snapshot (documented); OS-level sandbox NOT_RUN. Tests NOT_RUN (operator forbids pytest); evidence is static review only.

Ask: the complete BLOCKER/MAJOR set for this delta only.
