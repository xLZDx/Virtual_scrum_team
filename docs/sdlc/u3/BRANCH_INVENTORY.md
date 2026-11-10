# U3-1 Branch inventory and landing plan

Read-only map of the five pushed branches against origin/main. Nothing was merged, checked out or changed on those branches.

```
rules_sha256: 1346de42e7e7a66cdc8a3ea7f0418c42dbf7f1037849c7f707ef83f218fddf95
base_ref: origin/main
base_tip: fa26e3cb3bbf93bb5849f6119e1483a539035dd1
branch origin/s4-canonical-continuation tip=3b14f20584fbe8fed1d758753343ea8d132a5706 merge_base=3505f769f9c1c245d368a8318aeb04a76e1c5537 files=724 LAND=0 EVIDENCE_ONLY=355 DROPPED=78 ALREADY_ON_MAIN=291 conflict_prone=78
branch origin/s4-native-qa-runner tip=8f95efcebe487c5da5087a7e0aadbc44d43db31f merge_base=3505f769f9c1c245d368a8318aeb04a76e1c5537 files=197 LAND=0 EVIDENCE_ONLY=179 DROPPED=18 ALREADY_ON_MAIN=0 conflict_prone=18
branch origin/s4-reproducible-qa-automation tip=3b8d80ff5456192c2419d9515b47fb843939ee16 merge_base=3505f769f9c1c245d368a8318aeb04a76e1c5537 files=175 LAND=0 EVIDENCE_ONLY=142 DROPPED=28 ALREADY_ON_MAIN=5 conflict_prone=28
branch origin/s4-e2e-snapshot-20261025-180e330 tip=9fd992f8835b458f99242c2f7fc9e231b7cc3b6b merge_base=3505f769f9c1c245d368a8318aeb04a76e1c5537 files=194 LAND=0 EVIDENCE_ONLY=176 DROPPED=18 ALREADY_ON_MAIN=0 conflict_prone=18
branch origin/s5-bounded-aeve-evidence tip=b954c6f4dc12a83bbcc2b92e1d0f73c454ea3bcf merge_base=3505f769f9c1c245d368a8318aeb04a76e1c5537 files=69 LAND=0 EVIDENCE_ONLY=49 DROPPED=20 ALREADY_ON_MAIN=0 conflict_prone=20
```

The block above is the exact output of `python -I tools/qa/branch_inventory_check.py --print-header`. Verify: `python -I tools/qa/branch_inventory_check.py --inventory docs/sdlc/u3/BRANCH_INVENTORY.md` (exit 0 = every file is classified by exactly one rule and the first fenced block equals the live header: rules hash, base tip, every branch tip, merge-base and per-class totals; any difference is HASH_MISMATCH or STALE_INVENTORY). Rules: `docs/sdlc/u3/branch_inventory_rules.json`.

## Result in one paragraph

No file qualifies for LAND by static evidence. Main already ships its own accepted S4 testing core (tools/qa registry, runner, report, pytest plugin, gate_check no-skip verdict, build_registry, dependencies; tests/qa seeded-failure catalog; tools/uc and tools/vst from U1/U2). Every branch file is either byte-identical to main (ALREADY_ON_MAIN), an edit of a file main also changed (DROPPED, conflict), a clean edit that was read and judged out of U3 scope (EVIDENCE_ONLY), or branch-only material tied to the retired registry schema, WSL runtime or S2/S3/S5 scope (EVIDENCE_ONLY). Uncertain items were classed EVIDENCE_ONLY and carry a `reference_for` note naming the U3 task that may re-derive them; U3-2 executors are new work.

## Totals per branch (file universe = `git diff --name-status --no-renames origin/main...<branch> --`)

| branch | files | LAND | EVIDENCE_ONLY | DROPPED | ALREADY_ON_MAIN | absent_new | differs_conflict | differs_clean | identical | conflict-prone |
|---|---|---|---|---|---|---|---|---|---|---|
| origin/s4-canonical-continuation | 724 | 0 | 355 | 78 | 291 | 344 | 78 | 11 | 291 | 78 |
| origin/s4-e2e-snapshot-20261025-180e330 | 194 | 0 | 176 | 18 | 0 | 173 | 18 | 3 | 0 | 18 |
| origin/s4-native-qa-runner | 197 | 0 | 179 | 18 | 0 | 176 | 18 | 3 | 0 | 18 |
| origin/s4-reproducible-qa-automation | 175 | 0 | 142 | 28 | 5 | 139 | 28 | 3 | 5 | 28 |
| origin/s5-bounded-aeve-evidence | 69 | 0 | 49 | 20 | 0 | 46 | 20 | 3 | 0 | 20 |

Main states: identical (same mode and blob as main); differs_conflict (main has the path with other content and changed it since the merge-base, or both sides added it: conflict-prone); differs_clean (the branch edited it, main still holds the merge-base content); absent_new (not on main and not at the merge-base); absent_removed_on_main (at the merge-base, removed on main: conflict-prone) and deleted_in_branch. The last two states have no files today and therefore no rule; if one appears the checker reports it as UNCLASSIFIED. Conflict-prone = differs_conflict + absent_removed_on_main.

## What main already has

- `tools/qa`: registry.py, run.py, report.py, pytest_plugin.py, build_registry.py, dependencies.py, gate_check.py (S4-F no-skip/fail-closed verdict), prepare/verify/WSL runtime scripts, worker_exec.c. Same module names as the branches' older versions, so any copy would duplicate or overwrite them.
- `docs/qa/categories.json` (schema 2 registry, large) and `docs/qa/aeve_required_rules.json`.
- `tests/qa`: test_s4a_registry, test_s4b_runner, test_s4d_lanes, test_s4f_gate_check, test_s4_seeded_failure_catalog and `tests/qa/seeded_failure/` (catalog.json plus aeve fixtures).
- `tools/uc` (U1/U2) and the VST modules under `tools/vst`.
- Already landed by identity: 291 files of s4-canonical-continuation (mostly docs/changes and docs/sdlc/evidence for S2, plus some tools/vst S2 modules) and 5 of s4-reproducible-qa-automation are byte-identical to main.

## Clean edits (differs_clean) that were read and not landed

Twelve distinct paths, each with its own explicit rule, were opened and diffed against main: the S3/S4/S5 plan documents (R09b-plan-docs-clean-edit), eight re-stamped HTML reports in s4-canonical-continuation only (R11-reports-clean-edit), and tools/vst/sandbox.py in s4-native-qa-runner and s4-e2e-snapshot (R24-vst-sandbox-clean-edit; POSIX signer-IPC ACL hardening, outside U3 scope). All are EVIDENCE_ONLY. None is LAND because none is U3 testing-core code and none was verified (no tests were run).

## Rules and file counts per branch

Every rule applies to all branches (`branch: *`) and is split by the file's state on main, so one file matches exactly one rule. Counts are files per branch.

### origin/s4-canonical-continuation

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R01-identical | `**` | identical | 291 | ALREADY_ON_MAIN | Blob hash equals the blob at the same path on origin/main; nothing to land. | - |
| R02-core-logs | `core/**` | absent_new/differs_conflict | 4 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent_new/differs_conflict | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent_new | 210 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R05-change-records-conflict | `docs/changes/**` | differs_conflict | 1 | DROPPED | Change record number already used on main with other content. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent_new | 113 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R07-evidence-conflict | `docs/sdlc/evidence/**` | differs_conflict | 10 | DROPPED | Evidence file at a path where main holds different content, for example the docs/sdlc/evidence/qa lane outputs. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent_new | 5 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09-sdlc-docs-conflict | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | differs_conflict | 13 | DROPPED | Plan/design/state document changed on both sides since the merge-base with different content. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R09b-plan-docs-clean-edit | `docs/*.md` | differs_clean | 3 | EVIDENCE_ONLY | Read: S3, S4 and S5 plan documents edited on the branch with status narrative of the old branch (S4 'implemented, acceptance open', REJECT dispositions, continuation notes) that describes the older docs/qa/categories.json registry and tools/qa/build_registry.py; main's S4 was accepted separately with a different registry, so landing would add contradictory status text. Not a code asset and no U3 scope.; flags: CLEAN_EDIT_NOT_LANDED | - |
| R10-reports-new | `reports/**` | absent_new | 4 | EVIDENCE_ONLY | Generated HTML status snapshots that do not exist on main; regenerable artifacts, not landed. | - |
| R11-reports-clean-edit | `reports/**` | differs_clean | 8 | EVIDENCE_ONLY | Read: the S0/S1, status and baseline HTML reports were re-stamped on the branch (the Git line now reads 's4-canonical-continuation @ 4e0deef') plus blank-line padding. Main did not change them, but landing would put a stale branch name and hash into main's reports; generated artifacts are regenerated, not merged.; flags: CLEAN_EDIT_NOT_LANDED | - |
| R12-docs-qa-new | `docs/qa/**` | absent_new | 1 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs_conflict | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R15-qa-seeded-fixtures | `tools/qa/fixtures.py`, `tests/qa/test_s4_seeded_failure*.py` | absent_new | 2 | EVIDENCE_ONLY | Hash-bound seeded-failure fixture validator and tests built on the branch registry; main has its own accepted seeded-failure catalog and tests. Compatibility with main's registry is unproven, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-6 |
| R16-qa-matrix | `tools/qa/matrix.py` | absent_new | 1 | EVIDENCE_ONLY | Exact-head platform-matrix report validator against the branch registry and report formats; unproven against main's report envelope, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-4 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent_new | 1 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs_conflict | 9 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R19-qa-tests-new | `tests/qa/**` (except `tests/qa/test_s4_pass_line_parser.py`, `tests/qa/test_s4_seeded_failure*.py`) | absent_new | 7 | EVIDENCE_ONLY | Tests for the old branch runner, registry and worker; they target code that is not landed. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs_conflict | 16 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs_conflict | 23 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch/supervisor modules where main also changed the file since the merge-base. S2/S3/S5 scope; resolving needs a manual three-way merge in a VST sprint, not U3. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |

### origin/s4-e2e-snapshot-20261025-180e330

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R02-core-logs | `core/**` | absent_new/differs_conflict | 4 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent_new/differs_conflict | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent_new | 124 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent_new | 31 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent_new | 2 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09b-plan-docs-clean-edit | `docs/*.md` | differs_clean | 2 | EVIDENCE_ONLY | Read: S3, S4 and S5 plan documents edited on the branch with status narrative of the old branch (S4 'implemented, acceptance open', REJECT dispositions, continuation notes) that describes the older docs/qa/categories.json registry and tools/qa/build_registry.py; main's S4 was accepted separately with a different registry, so landing would add contradictory status text. Not a code asset and no U3 scope.; flags: CLEAN_EDIT_NOT_LANDED | - |
| R10-reports-new | `reports/**` | absent_new | 2 | EVIDENCE_ONLY | Generated HTML status snapshots that do not exist on main; regenerable artifacts, not landed. | - |
| R12-docs-qa-new | `docs/qa/**` | absent_new | 2 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs_conflict | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R14-qa-pass-line | `tools/qa/pytest_pass_plugin.py`, `tests/qa/test_s4_pass_line_parser.py` | absent_new | 2 | EVIDENCE_ONLY | Trusted PASS-line emitter and its parser test. The parser test needs the quiet-dot change in tools/vst/contracts.py, which conflicts with main and alters a hash-pinned parser; main already has a no-skip verdict in tools/qa/gate_check.py. Re-derive in U3-5 if needed.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-5 |
| R15-qa-seeded-fixtures | `tools/qa/fixtures.py`, `tests/qa/test_s4_seeded_failure*.py` | absent_new | 1 | EVIDENCE_ONLY | Hash-bound seeded-failure fixture validator and tests built on the branch registry; main has its own accepted seeded-failure catalog and tests. Compatibility with main's registry is unproven, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-6 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent_new | 2 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs_conflict | 4 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R19-qa-tests-new | `tests/qa/**` (except `tests/qa/test_s4_pass_line_parser.py`, `tests/qa/test_s4_seeded_failure*.py`) | absent_new | 5 | EVIDENCE_ONLY | Tests for the old branch runner, registry and worker; they target code that is not landed. | - |
| R20-vst-tests-new | `tests/vst/**` | absent_new | 1 | EVIDENCE_ONLY | S2/S3/S5 tests for unlanded VST changes; outside U3 scope. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs_conflict | 2 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R22-vst-tools-new | `tools/vst/**` | absent_new | 1 | EVIDENCE_ONLY | Worker capability-drop helper and S5 source-tree code; S2/S3/S5 scope, not U3. | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs_conflict | 6 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch/supervisor modules where main also changed the file since the merge-base. S2/S3/S5 scope; resolving needs a manual three-way merge in a VST sprint, not U3. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R24-vst-sandbox-clean-edit | `tools/vst/sandbox.py` | differs_clean | 1 | EVIDENCE_ONLY | Read: identical edit in s4-native-qa-runner and s4-e2e-snapshot (+80/-4). Adds require_no_extended_acl and stricter ancestor/ACL checks for the signer IPC path (POSIX hardening of the VST worker sandbox). Main did not change the file, so it applies cleanly, but it is S2/S3 sandbox security code outside the U3 testing-core scope and unverifiable here without POSIX tests (none were run); it does not touch tools/qa. Candidate for a separate VST hardening item, not U3.; flags: CLEAN_EDIT_NOT_LANDED | - |

### origin/s4-native-qa-runner

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R02-core-logs | `core/**` | absent_new/differs_conflict | 4 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent_new/differs_conflict | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent_new | 126 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent_new | 32 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent_new | 2 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09b-plan-docs-clean-edit | `docs/*.md` | differs_clean | 2 | EVIDENCE_ONLY | Read: S3, S4 and S5 plan documents edited on the branch with status narrative of the old branch (S4 'implemented, acceptance open', REJECT dispositions, continuation notes) that describes the older docs/qa/categories.json registry and tools/qa/build_registry.py; main's S4 was accepted separately with a different registry, so landing would add contradictory status text. Not a code asset and no U3 scope.; flags: CLEAN_EDIT_NOT_LANDED | - |
| R10-reports-new | `reports/**` | absent_new | 2 | EVIDENCE_ONLY | Generated HTML status snapshots that do not exist on main; regenerable artifacts, not landed. | - |
| R12-docs-qa-new | `docs/qa/**` | absent_new | 2 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs_conflict | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R14-qa-pass-line | `tools/qa/pytest_pass_plugin.py`, `tests/qa/test_s4_pass_line_parser.py` | absent_new | 2 | EVIDENCE_ONLY | Trusted PASS-line emitter and its parser test. The parser test needs the quiet-dot change in tools/vst/contracts.py, which conflicts with main and alters a hash-pinned parser; main already has a no-skip verdict in tools/qa/gate_check.py. Re-derive in U3-5 if needed.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-5 |
| R15-qa-seeded-fixtures | `tools/qa/fixtures.py`, `tests/qa/test_s4_seeded_failure*.py` | absent_new | 1 | EVIDENCE_ONLY | Hash-bound seeded-failure fixture validator and tests built on the branch registry; main has its own accepted seeded-failure catalog and tests. Compatibility with main's registry is unproven, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-6 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent_new | 2 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs_conflict | 4 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R19-qa-tests-new | `tests/qa/**` (except `tests/qa/test_s4_pass_line_parser.py`, `tests/qa/test_s4_seeded_failure*.py`) | absent_new | 5 | EVIDENCE_ONLY | Tests for the old branch runner, registry and worker; they target code that is not landed. | - |
| R20-vst-tests-new | `tests/vst/**` | absent_new | 1 | EVIDENCE_ONLY | S2/S3/S5 tests for unlanded VST changes; outside U3 scope. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs_conflict | 2 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R22-vst-tools-new | `tools/vst/**` | absent_new | 1 | EVIDENCE_ONLY | Worker capability-drop helper and S5 source-tree code; S2/S3/S5 scope, not U3. | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs_conflict | 6 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch/supervisor modules where main also changed the file since the merge-base. S2/S3/S5 scope; resolving needs a manual three-way merge in a VST sprint, not U3. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R24-vst-sandbox-clean-edit | `tools/vst/sandbox.py` | differs_clean | 1 | EVIDENCE_ONLY | Read: identical edit in s4-native-qa-runner and s4-e2e-snapshot (+80/-4). Adds require_no_extended_acl and stricter ancestor/ACL checks for the signer IPC path (POSIX hardening of the VST worker sandbox). Main did not change the file, so it applies cleanly, but it is S2/S3 sandbox security code outside the U3 testing-core scope and unverifiable here without POSIX tests (none were run); it does not touch tools/qa. Candidate for a separate VST hardening item, not U3.; flags: CLEAN_EDIT_NOT_LANDED | - |

### origin/s4-reproducible-qa-automation

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R01-identical | `**` | identical | 5 | ALREADY_ON_MAIN | Blob hash equals the blob at the same path on origin/main; nothing to land. | - |
| R02-core-logs | `core/**` | absent_new/differs_conflict | 4 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent_new/differs_conflict | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent_new | 104 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent_new | 21 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R07-evidence-conflict | `docs/sdlc/evidence/**` | differs_conflict | 9 | DROPPED | Evidence file at a path where main holds different content, for example the docs/sdlc/evidence/qa lane outputs. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent_new | 2 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09b-plan-docs-clean-edit | `docs/*.md` | differs_clean | 3 | EVIDENCE_ONLY | Read: S3, S4 and S5 plan documents edited on the branch with status narrative of the old branch (S4 'implemented, acceptance open', REJECT dispositions, continuation notes) that describes the older docs/qa/categories.json registry and tools/qa/build_registry.py; main's S4 was accepted separately with a different registry, so landing would add contradictory status text. Not a code asset and no U3 scope.; flags: CLEAN_EDIT_NOT_LANDED | - |
| R10-reports-new | `reports/**` | absent_new | 2 | EVIDENCE_ONLY | Generated HTML status snapshots that do not exist on main; regenerable artifacts, not landed. | - |
| R12-docs-qa-new | `docs/qa/**` | absent_new | 1 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs_conflict | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R15-qa-seeded-fixtures | `tools/qa/fixtures.py`, `tests/qa/test_s4_seeded_failure*.py` | absent_new | 2 | EVIDENCE_ONLY | Hash-bound seeded-failure fixture validator and tests built on the branch registry; main has its own accepted seeded-failure catalog and tests. Compatibility with main's registry is unproven, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-6 |
| R16-qa-matrix | `tools/qa/matrix.py` | absent_new | 1 | EVIDENCE_ONLY | Exact-head platform-matrix report validator against the branch registry and report formats; unproven against main's report envelope, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-4 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent_new | 1 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs_conflict | 4 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R19-qa-tests-new | `tests/qa/**` (except `tests/qa/test_s4_pass_line_parser.py`, `tests/qa/test_s4_seeded_failure*.py`) | absent_new | 5 | EVIDENCE_ONLY | Tests for the old branch runner, registry and worker; they target code that is not landed. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs_conflict | 5 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs_conflict | 4 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch/supervisor modules where main also changed the file since the merge-base. S2/S3/S5 scope; resolving needs a manual three-way merge in a VST sprint, not U3. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |

### origin/s5-bounded-aeve-evidence

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R02-core-logs | `core/**` | absent_new/differs_conflict | 3 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent_new/differs_conflict | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent_new | 29 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent_new | 6 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent_new | 2 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09b-plan-docs-clean-edit | `docs/*.md` | differs_clean | 3 | EVIDENCE_ONLY | Read: S3, S4 and S5 plan documents edited on the branch with status narrative of the old branch (S4 'implemented, acceptance open', REJECT dispositions, continuation notes) that describes the older docs/qa/categories.json registry and tools/qa/build_registry.py; main's S4 was accepted separately with a different registry, so landing would add contradictory status text. Not a code asset and no U3 scope.; flags: CLEAN_EDIT_NOT_LANDED | - |
| R10-reports-new | `reports/**` | absent_new | 2 | EVIDENCE_ONLY | Generated HTML status snapshots that do not exist on main; regenerable artifacts, not landed. | - |
| R12-docs-qa-new | `docs/qa/**` | absent_new | 1 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs_conflict | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R14-qa-pass-line | `tools/qa/pytest_pass_plugin.py`, `tests/qa/test_s4_pass_line_parser.py` | absent_new | 1 | EVIDENCE_ONLY | Trusted PASS-line emitter and its parser test. The parser test needs the quiet-dot change in tools/vst/contracts.py, which conflicts with main and alters a hash-pinned parser; main already has a no-skip verdict in tools/qa/gate_check.py. Re-derive in U3-5 if needed.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-5 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent_new | 2 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs_conflict | 4 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R20-vst-tests-new | `tests/vst/**` | absent_new | 2 | EVIDENCE_ONLY | S2/S3/S5 tests for unlanded VST changes; outside U3 scope. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs_conflict | 2 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |
| R22-vst-tools-new | `tools/vst/**` | absent_new | 1 | EVIDENCE_ONLY | Worker capability-drop helper and S5 source-tree code; S2/S3/S5 scope, not U3. | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs_conflict | 9 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch/supervisor modules where main also changed the file since the merge-base. S2/S3/S5 scope; resolving needs a manual three-way merge in a VST sprint, not U3. Main and the branch both changed this path since the merge-base (or both added it) with different content; copying it would overwrite main's version or conflict, and the branch edit is not rebased onto main.; flags: CONFLICT_WITH_MAIN | - |

## Conflict-prone files (main also changed them)

83 distinct paths. Short branch names: cc=s4-canonical-continuation, nq=s4-native-qa-runner, rq=s4-reproducible-qa-automation, sn=s4-e2e-snapshot-20261025-180e330, s5=s5-bounded-aeve-evidence.

| path | in branches |
|---|---|
| `core/BACKLOG.md` | cc, sn, nq, rq, s5 |
| `core/DECISION_LOG.md` | cc, sn, nq, rq, s5 |
| `core/LESSONS_LOG.md` | cc, sn, nq, rq, s5 |
| `core/STATE.md` | cc, sn, nq, rq |
| `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` | cc |
| `docs/SANDBOX_SPEC.md` | cc |
| `docs/changes/0538-complete-s2-dispatch-owner-transport-source.md` | cc |
| `docs/qa/categories.json` | cc, sn, nq, rq, s5 |
| `docs/sdlc/S2_DELEGATED_MACHINE_TRUST_DESIGN.md` | cc |
| `docs/sdlc/S2_FINAL_PERMITTED_SELECTOR_PLAN.md` | cc |
| `docs/sdlc/S2_ORIGINAL_EPIC_COVERAGE_MATRIX.md` | cc |
| `docs/sdlc/STATE.md` | cc |
| `docs/sdlc/backlog.md` | cc |
| `docs/sdlc/design.md` | cc |
| `docs/sdlc/evidence/qa/api.report.jsonl` | cc, rq |
| `docs/sdlc/evidence/qa/api.stderr.txt` | cc, rq |
| `docs/sdlc/evidence/qa/api.stdout.txt` | cc, rq |
| `docs/sdlc/evidence/qa/functional.report.jsonl` | cc, rq |
| `docs/sdlc/evidence/qa/functional.stderr.txt` | cc, rq |
| `docs/sdlc/evidence/qa/functional.stdout.txt` | cc, rq |
| `docs/sdlc/evidence/qa/integration.report.jsonl` | cc, rq |
| `docs/sdlc/evidence/qa/integration.stderr.txt` | cc, rq |
| `docs/sdlc/evidence/qa/integration.stdout.txt` | cc, rq |
| `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md` | cc |
| `docs/sdlc/requirements.md` | cc |
| `docs/sdlc/review-record.md` | cc |
| `docs/sdlc/state.json` | cc |
| `docs/sdlc/test-plan.md` | cc |
| `docs/sdlc/verify-evidence.md` | cc |
| `governance/DOCUMENT_REGISTRY.md` | cc, sn, nq, rq, s5 |
| `tests/vst/test_e4_runner.py` | rq |
| `tests/vst/test_s2_assignment_basis.py` | cc |
| `tests/vst/test_s2_bootstrap_runtime.py` | cc |
| `tests/vst/test_s2_dispatch_owner_latch.py` | cc |
| `tests/vst/test_s2_dispatch_owner_service.py` | cc |
| `tests/vst/test_s2_e8_synthetic_lifecycle.py` | cc |
| `tests/vst/test_s2_machine_source_contracts.py` | cc |
| `tests/vst/test_s2_persistent_runner_service.py` | cc |
| `tests/vst/test_s2_runner_lifecycle.py` | cc, rq |
| `tests/vst/test_s2_runtime_bundle.py` | cc |
| `tests/vst/test_s2_sandbox_probe.py` | cc, rq |
| `tests/vst/test_s2_source_staging_plan.py` | cc |
| `tests/vst/test_s2_stage_only_install.py` | cc |
| `tests/vst/test_s2_store_backed_pubsub.py` | cc |
| `tests/vst/test_s2_store_lifecycle.py` | cc |
| `tests/vst/test_s3_worker_adapter.py` | cc, sn, nq, rq, s5 |
| `tests/vst/test_s3_worker_pilot_e2e.py` | cc, sn, nq, rq, s5 |
| `tools/qa/__init__.py` | sn, nq, s5 |
| `tools/qa/build_registry.py` | cc, rq |
| `tools/qa/dependencies.py` | cc |
| `tools/qa/install_wsl_runner_runtime.sh` | cc |
| `tools/qa/install_wsl_runtime.ps1` | cc |
| `tools/qa/install_wsl_worker_helper.sh` | cc |
| `tools/qa/prepare_wsl_runtime_plan.py` | cc |
| `tools/qa/pytest_plugin.py` | cc, rq |
| `tools/qa/registry.py` | cc, sn, nq, rq, s5 |
| `tools/qa/requirements.lock` | sn, nq, s5 |
| `tools/qa/run.py` | cc, sn, nq, rq, s5 |
| `tools/vst/bootstrap_runtime.py` | cc |
| `tools/vst/contracts.py` | sn, nq, s5 |
| `tools/vst/dispatch_issuance.py` | cc |
| `tools/vst/dispatch_owner_client.py` | cc |
| `tools/vst/dispatch_owner_service.py` | cc |
| `tools/vst/dispatch_owner_transport.py` | cc |
| `tools/vst/dispatcher_service.py` | cc |
| `tools/vst/execution_grant.py` | cc |
| `tools/vst/gate.py` | cc, s5 |
| `tools/vst/machine_authorization.py` | cc |
| `tools/vst/pilot.py` | cc, sn, nq, rq, s5 |
| `tools/vst/root_dispatch_issuer.py` | cc |
| `tools/vst/runner.py` | cc, sn, nq, s5 |
| `tools/vst/runner_service.py` | cc |
| `tools/vst/runtime_bundle.py` | cc |
| `tools/vst/schemas/README.md` | cc, s5 |
| `tools/vst/signer.py` | cc |
| `tools/vst/signing.py` | s5 |
| `tools/vst/slice.py` | cc, sn, nq, rq, s5 |
| `tools/vst/store.py` | cc, sn, nq, rq, s5 |
| `tools/vst/supervisor.py` | cc |
| `tools/vst/supervisor_service.py` | cc |
| `tools/vst/systemd/README.md` | cc |
| `tools/vst/systemd/vst-supervisor.service` | cc |
| `tools/vst/worker_adapter.py` | cc, sn, nq, rq, s5 |

## Flags used

- CONFLICT_WITH_MAIN: path exists on main with different content that main also changed; not landed.
- DUPLICATES_MAIN_TOOLS_QA: the file would add a second mechanism next to main's accepted tools/qa or its seeded-failure catalog.
- CLEAN_EDIT_NOT_LANDED: branch edit that applies cleanly (main did not change the file) but was read and not landed, for the stated reason.

## Checker summary (output of one run, rules file unchanged)

```json
{
  "base_ref": "origin/main",
  "base_tip": "fa26e3cb3bbf93bb5849f6119e1483a539035dd1",
  "branches": {
    "origin/s4-canonical-continuation": {
      "class_counts": {
        "ALREADY_ON_MAIN": 291,
        "DROPPED": 78,
        "EVIDENCE_ONLY": 355,
        "LAND": 0
      },
      "conflict_prone_count": 78,
      "conflict_prone_truncated": false,
      "files": 724,
      "main_state_counts": {
        "absent_new": 344,
        "differs_clean": 11,
        "differs_conflict": 78,
        "identical": 291
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "3b14f20584fbe8fed1d758753343ea8d132a5706"
    },
    "origin/s4-e2e-snapshot-20261025-180e330": {
      "class_counts": {
        "ALREADY_ON_MAIN": 0,
        "DROPPED": 18,
        "EVIDENCE_ONLY": 176,
        "LAND": 0
      },
      "conflict_prone_count": 18,
      "conflict_prone_truncated": false,
      "files": 194,
      "main_state_counts": {
        "absent_new": 173,
        "differs_clean": 3,
        "differs_conflict": 18
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "9fd992f8835b458f99242c2f7fc9e231b7cc3b6b"
    },
    "origin/s4-native-qa-runner": {
      "class_counts": {
        "ALREADY_ON_MAIN": 0,
        "DROPPED": 18,
        "EVIDENCE_ONLY": 179,
        "LAND": 0
      },
      "conflict_prone_count": 18,
      "conflict_prone_truncated": false,
      "files": 197,
      "main_state_counts": {
        "absent_new": 176,
        "differs_clean": 3,
        "differs_conflict": 18
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "8f95efcebe487c5da5087a7e0aadbc44d43db31f"
    },
    "origin/s4-reproducible-qa-automation": {
      "class_counts": {
        "ALREADY_ON_MAIN": 5,
        "DROPPED": 28,
        "EVIDENCE_ONLY": 142,
        "LAND": 0
      },
      "conflict_prone_count": 28,
      "conflict_prone_truncated": false,
      "files": 175,
      "main_state_counts": {
        "absent_new": 139,
        "differs_clean": 3,
        "differs_conflict": 28,
        "identical": 5
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "3b8d80ff5456192c2419d9515b47fb843939ee16"
    },
    "origin/s5-bounded-aeve-evidence": {
      "class_counts": {
        "ALREADY_ON_MAIN": 0,
        "DROPPED": 20,
        "EVIDENCE_ONLY": 49,
        "LAND": 0
      },
      "conflict_prone_count": 20,
      "conflict_prone_truncated": false,
      "files": 69,
      "main_state_counts": {
        "absent_new": 46,
        "differs_clean": 3,
        "differs_conflict": 20
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "b954c6f4dc12a83bbcc2b92e1d0f73c454ea3bcf"
    }
  },
  "ok": true,
  "rule_count": 25,
  "rules_sha256": "1346de42e7e7a66cdc8a3ea7f0418c42dbf7f1037849c7f707ef83f218fddf95",
  "schema_version": 1
}
```
