# U6-2 GPT-PM scope note

Base: 8b654cc (U6-1 approved). Task U6-2: measured savings report against the U1-1 baseline.

- tools/uc/savings_report.py: builds a per-role before/after report from hash-pinned manifests and declared paired sessions. Reuses token_baseline and measure. Nothing is estimated; the four token fields stay separate; cost only from a price table with a non-empty source and one model per role. Roles with model mismatch, unknown model, or one-sided presence in any task are refused as a whole.
- docs/sdlc/u6/SAVINGS_REPORT.md: the report for this program is NOT_RUN. Reasons are facts: no after-side manifest, paired-task file or price table exists, and the U1-1 baseline manifest fails HASH_MISMATCH (the pinned main transcript grew from 6767280 to 6773135 bytes). Two real CLI runs (MISSING_CURRENT, HASH_MISMATCH) are quoted.
- Operator inputs still needed for a real measurement: closed baseline sessions and a rebuilt manifest, an after-side manifest, a paired-task file, a price table with source.
- Tests are NOT_RUN (operator prohibition); reviewed statically by python-reviewer and functional-test-reviewer; one remediation batch applied (13 minors, no BLOCKER/MAJOR).
- Known limits: pairing is declared by the caller and not proven; pre-existing first output not restored if the second replace fails; a file changed and restored between reads is not detected.
- tools/qa/build_registry.py and docs/qa/categories.json: registry bookkeeping only.
