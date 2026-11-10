# S5-B GPT-PM code review scope

Task: S5-B (VST-039), independent analyzer authority and signature binding. Base 76592fa (S5-A accepted), head = current HEAD. Review only tools/vst/analyzer_authority.py (new) and the new label in tools/vst/signing.py.

Delivers (plan docs/S5_AEVE_GATE_PLAN_2026-10-24.md E2, AC-3, AC-4): VST trusted code, not AEVE and not a model, signs the AEVE report with a dedicated analyzer-authority key and domain label. The signed payload binds analyzer id/version/executable digest, profile id/digest, source-tree digest, report digest, manifest digest, run id, nonce, candidate head, epoch and scope. Verify requires the full expected binding, the six other role keys (worker, supervisor, operator, event, reviewer, runner_signer) that must differ from the analyzer key, and an atomic consume_nonce callback; hostile input returns False.

Already fixed after two read-only reviewer passes: optional key roster, optional binding, passive replay protection, wrong exception types.

Settled, do not reopen: gate.py stays fail-closed for v3 until S5-E; AEVE adapter and report production are S5-C/D. Tests NOT_RUN (operator forbids pytest); evidence is static review only.

Ask: the complete BLOCKER/MAJOR set for this delta only.
