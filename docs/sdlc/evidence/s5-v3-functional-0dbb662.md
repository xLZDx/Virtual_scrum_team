# S5 v3 functional/API evidence

## Run identity

- Candidate HEAD: `0dbb66293fbf9df946b1b1cb5cc9b841d7b9d1ed`
- Worktree: clean before the command.
- OS/shell: Windows PowerShell.
- Python: `3.14.3`
- pytest: `8.4.2`
- Exact command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider tests/vst/test_s5_v3_evidence.py`
- Result: **39 passed, 1 skipped, 0 failed**; 40 cases collected, `1.51s`.
- Warning: one deprecation warning from globally installed `pytest-asyncio` (`asyncio.get_event_loop_policy`); this module contains no asyncio tests.
- Skip: `test_source_tree_digest_rejects_symlink_scope` could not create a symlink; Windows returned WinError `1314` / errno `22` (required privilege unavailable). The symlink case is not runtime-proven on this host.

## Test-to-acceptance map

| Test ID | S5 acceptance | Observable contract |
|---|---|---|
| `test_v1_v2_manifest_and_signed_receipt_golden_hashes_remain_unchanged` | AC-1 | Pins v1 and v2 manifest SHA-256, receipt SHA-256 and signatures; validates both versions unchanged. |
| `test_v2_manifest_cannot_be_upgraded_with_v3_analyzer_policy` | AC-1 | A v2 manifest with v3 policy fields is rejected as unknown. |
| `test_v3_manifest_rejects_malformed_or_unbound_policy` | AC-1 | Missing/extra policy fields, wrong contract version, malformed digest/scope, unknown acceptance ID and unsupported digest scheme fail validation. |
| `test_v3_receipt_requires_exact_rule_partition_and_derived_coverage` | AC-2, AC-7, AC-8 | Omitted/duplicate status, contradictory covered set and false FULL claim fail; an optional unsupported rule does not reduce required coverage. |
| `test_v3_receipt_rejects_missing_extra_and_inconsistent_provenance_fields` | AC-1, AC-4 | Missing/extra receipt fields and a run ID that differs from invocation ID are rejected. |
| `test_v3_required_unsupported_rule_is_non_approving` | AC-7, AC-8, AC-11 | PARTIAL and NOT_COVERED required-rule cases derive INCONCLUSIVE. |
| `test_v3_finding_is_typed_in_scope_and_derives_failure` | AC-7, AC-8, AC-11 | A typed in-scope finding derives FAIL and remains an unresolved gate finding; out-of-scope path and invalid severity fail validation. |
| `test_analyzer_receipt_rejects_every_non_analyzer_signature_root` | AC-3 | Worker, supervisor, operator, runner signer, event and reviewer signatures do not verify as analyzer evidence. |
| `test_analyzer_receipt_signature_requires_its_domain_label` | AC-3 | A signature made with the analyzer key but v2 receipt domain is rejected. |
| `test_exact_v3_analyzer_receipt_contributes_only_policy_acceptance` | AC-9 | Exact fully covered analyzer evidence satisfies its declared `AC-2`; missing TestRun evidence leaves `AC-1` unmet and prevents APPROVE. |
| `test_v3_gate_rejects_replayed_or_policy_mismatched_evidence` | AC-4, AC-10, AC-11 | Wrong candidate head, manifest hash, analyzer identity/digest, profile hash, scope, source digest, report digest or epoch leaves evidence rejected/unmet with a specific gate reason. |
| `test_v3_gate_fails_closed_when_report_or_source_resolver_is_unavailable` | AC-10, AC-11 | Missing, mismatching or raising report-artifact resolution cannot contribute acceptance. |
| `test_v3_gate_fails_closed_when_source_resolver_raises_or_mismatches` | AC-10, AC-11 | Missing, raising or digest-mismatching trusted source resolution cannot contribute acceptance. |
| `test_v3_gate_rejects_replayed_receipt_attempt` | AC-11 | Duplicate attempt-1 receipt is rejected as a broken chain. |
| `test_v3_gate_rechecks_finding_evidence_artifact_digest` | AC-7, AC-8, AC-10 | The gate independently resolves finding evidence and rejects changed evidence bytes. |
| `test_source_tree_digest_is_order_independent_and_changes_with_content` | AC-5, AC-12 | Path order does not affect the deterministic digest; changed bytes produce a different digest. |
| `test_source_tree_digest_rejects_traversal_missing_and_byte_bound` | AC-6, AC-12 | Traversal, missing files, byte-limit excess and file-count excess fail closed. |
| `test_source_tree_digest_rejects_symlink_scope` | AC-6 | Symlink refusal is authored but skipped due WinError 1314 / errno 22 on this host. |
| `test_source_tree_digest_detects_file_mutation_during_read` | AC-5, AC-6 | A same-size file changed while hashing is detected and rejected. |

## Scope and limits

- These are local contract and gate tests with synthetic keys, receipts and temporary source files. They do not execute AEVE, invoke a provider, access a separate analyzer repository, or establish an analyzer capability inventory.
- No bounded analyzer adapter or sandbox is present in this tested path. Analyzer immutability, candidate execution denial, network denial, CPU/memory/time/output enforcement, subprocess policy and real artifact retention remain `NOT_RUN` or `UNSUPPORTED` per the S5 plan.
- Source-tree digest mutation detection is tested; this does not prove an analyzer cannot modify a snapshot. Windows symlink creation was unavailable as recorded above.
- No full pytest suite, build, lint, typecheck, CI, migration, mutation test, package install, external service call or AEVE runtime was run.
