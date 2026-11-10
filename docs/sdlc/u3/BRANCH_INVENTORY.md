# U3-1 Branch inventory and landing plan

Read-only map of the five pushed branches against origin/main. Nothing was merged, checked out or changed on those branches.

```
rules_sha256: 66113f6e8b4b5ae39e9d992f2438097f6845a2c5899c28f63100e2e4e95b76fb
base_ref: origin/main
base_tip: fa26e3cb3bbf93bb5849f6119e1483a539035dd1
tip origin/s4-canonical-continuation: 3b14f20584fbe8fed1d758753343ea8d132a5706  (merge-base 3505f769f9c1c245d368a8318aeb04a76e1c5537)
tip origin/s4-e2e-snapshot-20261025-180e330: 9fd992f8835b458f99242c2f7fc9e231b7cc3b6b  (merge-base 3505f769f9c1c245d368a8318aeb04a76e1c5537)
tip origin/s4-native-qa-runner: 8f95efcebe487c5da5087a7e0aadbc44d43db31f  (merge-base 3505f769f9c1c245d368a8318aeb04a76e1c5537)
tip origin/s4-reproducible-qa-automation: 3b8d80ff5456192c2419d9515b47fb843939ee16  (merge-base 3505f769f9c1c245d368a8318aeb04a76e1c5537)
tip origin/s5-bounded-aeve-evidence: b954c6f4dc12a83bbcc2b92e1d0f73c454ea3bcf  (merge-base 3505f769f9c1c245d368a8318aeb04a76e1c5537)
```

Verify: `python -I tools/qa/branch_inventory_check.py --inventory docs/sdlc/u3/BRANCH_INVENTORY.md` (exit 0 = every file classified exactly once; the header hash must equal the rules file hash). Rules: `docs/sdlc/u3/branch_inventory_rules.json`.

## Result in one paragraph

No file qualifies for LAND by static evidence. Main already ships its own accepted S4 testing core (tools/qa registry, runner, report, pytest plugin, gate_check no-skip verdict, build_registry, dependencies; tests/qa seeded-failure catalog; tools/uc and tools/vst from U1/U2). Every branch file is either byte-identical to main (ALREADY_ON_MAIN), an older version of a file main already changed (DROPPED, conflict), or branch-only material tied to the retired registry schema, WSL runtime or S2/S3/S5 scope (EVIDENCE_ONLY). Uncertain items were classed EVIDENCE_ONLY and carry a `reference_for` note naming the U3 task that may re-derive them; U3-2 executors are new work.

## Totals per branch (file universe = `git diff --name-status --no-renames origin/main...<branch>`)

| branch | files | LAND | EVIDENCE_ONLY | DROPPED | ALREADY_ON_MAIN | new on main (absent) | differs from main | identical | conflict-prone |
|---|---|---|---|---|---|---|---|---|---|
| origin/s4-canonical-continuation | 724 | 0 | 344 | 89 | 291 | 344 | 89 | 291 | 78 |
| origin/s4-e2e-snapshot-20261025-180e330 | 194 | 0 | 173 | 21 | 0 | 173 | 21 | 0 | 18 |
| origin/s4-native-qa-runner | 197 | 0 | 176 | 21 | 0 | 176 | 21 | 0 | 18 |
| origin/s4-reproducible-qa-automation | 175 | 0 | 139 | 31 | 5 | 139 | 31 | 5 | 28 |
| origin/s5-bounded-aeve-evidence | 69 | 0 | 46 | 23 | 0 | 46 | 23 | 0 | 20 |

Conflict-prone = path exists on main with different content AND main changed it since the merge-base (a merge would conflict). It is a subset of the files that differ from main.

## What main already has

- `tools/qa`: registry.py, run.py, report.py, pytest_plugin.py, build_registry.py, dependencies.py, gate_check.py (S4-F no-skip/fail-closed verdict), prepare/verify/WSL runtime scripts, worker_exec.c. Same module names as the branches' older versions, so any copy would duplicate or overwrite them.
- `docs/qa/categories.json` (schema 2 registry, large) and `docs/qa/aeve_required_rules.json`.
- `tests/qa`: test_s4a_registry, test_s4b_runner, test_s4d_lanes, test_s4f_gate_check, test_s4_seeded_failure_catalog and `tests/qa/seeded_failure/` (catalog.json plus aeve fixtures).
- `tools/uc` (U1/U2) and the VST modules under `tools/vst`.
- On the identical-to-main side: 291 files of s4-canonical-continuation (mostly docs/changes and docs/sdlc/evidence for S2, plus tools/vst S2 modules) and 5 of s4-reproducible-qa-automation are already byte-identical, so that part of the branches is already landed.

## Rules and file counts per branch

Every rule applies to all branches (`branch: *`) and is split by the file's state on main, so one file matches exactly one rule. Counts are files per branch.

### origin/s4-canonical-continuation

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R01-identical | `**` | identical | 291 | ALREADY_ON_MAIN | Blob hash equals the blob at the same path on origin/main; nothing to land. | - |
| R02-core-logs | `core/**` | absent/differs | 4 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent/differs | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent | 210 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R05-change-records-conflict | `docs/changes/**` | differs | 1 | DROPPED | Change record number already used on main with other content. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent | 113 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R07-evidence-conflict | `docs/sdlc/evidence/**` | differs | 10 | DROPPED | Evidence file at a path where main holds different accepted evidence (for example docs/sdlc/evidence/qa lane outputs). Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent | 5 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09-sdlc-docs-conflict | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | differs | 16 | DROPPED | Older version of a plan/design/state document that main already holds in a newer form. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R10-reports-new | `reports/**` | absent | 4 | EVIDENCE_ONLY | Generated HTML status snapshots; regenerable artifacts, not landed. | - |
| R11-reports-conflict | `reports/**` | differs | 8 | DROPPED | Older generated report at a path main regenerated since. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R12-docs-qa-new | `docs/qa/**` | absent | 1 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R15-qa-seeded-fixtures | `tools/qa/fixtures.py`, `tests/qa/test_s4_seeded_failure*.py` | absent | 2 | EVIDENCE_ONLY | Hash-bound seeded-failure fixture validator and tests built on the branch registry; main has its own accepted seeded-failure catalog and tests. Compatibility with main's registry is unproven, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-6 |
| R16-qa-matrix | `tools/qa/matrix.py` | absent | 1 | EVIDENCE_ONLY | Exact-head platform-matrix report validator against the branch registry and report formats; unproven against main's report envelope, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-4 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent | 1 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs | 9 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R19-qa-tests-new | `tests/qa/**` (except `tests/qa/test_s4_pass_line_parser.py`, `tests/qa/test_s4_seeded_failure*.py`) | absent | 7 | EVIDENCE_ONLY | Tests for the old branch runner, registry and worker; they target code that is not landed. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs | 16 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs | 23 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch modules; S2/S3/S5 scope and main's tools/vst is accepted and newer. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |

### origin/s4-e2e-snapshot-20261025-180e330

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R02-core-logs | `core/**` | absent/differs | 4 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent/differs | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent | 124 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent | 31 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent | 2 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09-sdlc-docs-conflict | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | differs | 2 | DROPPED | Older version of a plan/design/state document that main already holds in a newer form. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R10-reports-new | `reports/**` | absent | 2 | EVIDENCE_ONLY | Generated HTML status snapshots; regenerable artifacts, not landed. | - |
| R12-docs-qa-new | `docs/qa/**` | absent | 2 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R14-qa-pass-line | `tools/qa/pytest_pass_plugin.py`, `tests/qa/test_s4_pass_line_parser.py` | absent | 2 | EVIDENCE_ONLY | Trusted PASS-line emitter and its parser test. The parser test needs the quiet-dot change in tools/vst/contracts.py, which conflicts with main and alters a hash-pinned parser; main already has a no-skip verdict in tools/qa/gate_check.py. Re-derive in U3-5 if needed.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-5 |
| R15-qa-seeded-fixtures | `tools/qa/fixtures.py`, `tests/qa/test_s4_seeded_failure*.py` | absent | 1 | EVIDENCE_ONLY | Hash-bound seeded-failure fixture validator and tests built on the branch registry; main has its own accepted seeded-failure catalog and tests. Compatibility with main's registry is unproven, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-6 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent | 2 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs | 4 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R19-qa-tests-new | `tests/qa/**` (except `tests/qa/test_s4_pass_line_parser.py`, `tests/qa/test_s4_seeded_failure*.py`) | absent | 5 | EVIDENCE_ONLY | Tests for the old branch runner, registry and worker; they target code that is not landed. | - |
| R20-vst-tests-new | `tests/vst/**` | absent | 1 | EVIDENCE_ONLY | S2/S3/S5 tests for unlanded VST changes; outside U3 scope. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs | 2 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R22-vst-tools-new | `tools/vst/**` | absent | 1 | EVIDENCE_ONLY | Worker capability-drop helper and S5 source-tree code; S2/S3/S5 scope, not U3. | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs | 7 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch modules; S2/S3/S5 scope and main's tools/vst is accepted and newer. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |

### origin/s4-native-qa-runner

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R02-core-logs | `core/**` | absent/differs | 4 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent/differs | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent | 126 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent | 32 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent | 2 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09-sdlc-docs-conflict | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | differs | 2 | DROPPED | Older version of a plan/design/state document that main already holds in a newer form. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R10-reports-new | `reports/**` | absent | 2 | EVIDENCE_ONLY | Generated HTML status snapshots; regenerable artifacts, not landed. | - |
| R12-docs-qa-new | `docs/qa/**` | absent | 2 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R14-qa-pass-line | `tools/qa/pytest_pass_plugin.py`, `tests/qa/test_s4_pass_line_parser.py` | absent | 2 | EVIDENCE_ONLY | Trusted PASS-line emitter and its parser test. The parser test needs the quiet-dot change in tools/vst/contracts.py, which conflicts with main and alters a hash-pinned parser; main already has a no-skip verdict in tools/qa/gate_check.py. Re-derive in U3-5 if needed.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-5 |
| R15-qa-seeded-fixtures | `tools/qa/fixtures.py`, `tests/qa/test_s4_seeded_failure*.py` | absent | 1 | EVIDENCE_ONLY | Hash-bound seeded-failure fixture validator and tests built on the branch registry; main has its own accepted seeded-failure catalog and tests. Compatibility with main's registry is unproven, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-6 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent | 2 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs | 4 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R19-qa-tests-new | `tests/qa/**` (except `tests/qa/test_s4_pass_line_parser.py`, `tests/qa/test_s4_seeded_failure*.py`) | absent | 5 | EVIDENCE_ONLY | Tests for the old branch runner, registry and worker; they target code that is not landed. | - |
| R20-vst-tests-new | `tests/vst/**` | absent | 1 | EVIDENCE_ONLY | S2/S3/S5 tests for unlanded VST changes; outside U3 scope. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs | 2 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R22-vst-tools-new | `tools/vst/**` | absent | 1 | EVIDENCE_ONLY | Worker capability-drop helper and S5 source-tree code; S2/S3/S5 scope, not U3. | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs | 7 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch modules; S2/S3/S5 scope and main's tools/vst is accepted and newer. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |

### origin/s4-reproducible-qa-automation

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R01-identical | `**` | identical | 5 | ALREADY_ON_MAIN | Blob hash equals the blob at the same path on origin/main; nothing to land. | - |
| R02-core-logs | `core/**` | absent/differs | 4 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent/differs | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent | 104 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent | 21 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R07-evidence-conflict | `docs/sdlc/evidence/**` | differs | 9 | DROPPED | Evidence file at a path where main holds different accepted evidence (for example docs/sdlc/evidence/qa lane outputs). Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent | 2 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09-sdlc-docs-conflict | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | differs | 3 | DROPPED | Older version of a plan/design/state document that main already holds in a newer form. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R10-reports-new | `reports/**` | absent | 2 | EVIDENCE_ONLY | Generated HTML status snapshots; regenerable artifacts, not landed. | - |
| R12-docs-qa-new | `docs/qa/**` | absent | 1 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R15-qa-seeded-fixtures | `tools/qa/fixtures.py`, `tests/qa/test_s4_seeded_failure*.py` | absent | 2 | EVIDENCE_ONLY | Hash-bound seeded-failure fixture validator and tests built on the branch registry; main has its own accepted seeded-failure catalog and tests. Compatibility with main's registry is unproven, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-6 |
| R16-qa-matrix | `tools/qa/matrix.py` | absent | 1 | EVIDENCE_ONLY | Exact-head platform-matrix report validator against the branch registry and report formats; unproven against main's report envelope, so conservative class.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-4 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent | 1 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs | 4 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R19-qa-tests-new | `tests/qa/**` (except `tests/qa/test_s4_pass_line_parser.py`, `tests/qa/test_s4_seeded_failure*.py`) | absent | 5 | EVIDENCE_ONLY | Tests for the old branch runner, registry and worker; they target code that is not landed. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs | 5 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs | 4 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch modules; S2/S3/S5 scope and main's tools/vst is accepted and newer. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |

### origin/s5-bounded-aeve-evidence

| rule | path globs | main state | files | class | reason | lands in / reference for |
|---|---|---|---|---|---|---|
| R02-core-logs | `core/**` | absent/differs | 3 | DROPPED | Branch-era state/decision/lesson logs; main's core logs carry the U1/U2 history and are authoritative. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R03-doc-registry | `governance/DOCUMENT_REGISTRY.md` | absent/differs | 1 | DROPPED | Generated file; it is regenerated on main by tools/build_document_registry.py, never merged. | - |
| R04-change-records-new | `docs/changes/**` | absent | 29 | EVIDENCE_ONLY | Per-commit change records of the retired record-per-commit process; kept on the branch ref as history, not landed. | - |
| R06-evidence-new | `docs/sdlc/evidence/**` | absent | 6 | EVIDENCE_ONLY | Recorded S2/S3/S4/S5 run outputs, reviews and snapshots bound to old heads; history only, not product behavior. | - |
| R08-sdlc-docs-new | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | absent | 2 | EVIDENCE_ONLY | S2/S3/S4 design and plan documents outside U3 scope; kept as design reference. | - |
| R09-sdlc-docs-conflict | `docs/sdlc/**`, `docs/*.md` (except `docs/sdlc/evidence/**`) | differs | 3 | DROPPED | Older version of a plan/design/state document that main already holds in a newer form. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R10-reports-new | `reports/**` | absent | 2 | EVIDENCE_ONLY | Generated HTML status snapshots; regenerable artifacts, not landed. | - |
| R12-docs-qa-new | `docs/qa/**` | absent | 1 | EVIDENCE_ONLY | Branch-era fixture/seeded-failure/API inventory data bound to the old registry schema and old test selectors; main keeps its own catalog in tests/qa/seeded_failure/catalog.json. Reference only. | ref: U3-6 |
| R13-docs-qa-conflict | `docs/qa/**` | differs | 1 | DROPPED | Old categories registry (small, old schema) versus main's schema 2 registry at the same path. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R14-qa-pass-line | `tools/qa/pytest_pass_plugin.py`, `tests/qa/test_s4_pass_line_parser.py` | absent | 1 | EVIDENCE_ONLY | Trusted PASS-line emitter and its parser test. The parser test needs the quiet-dot change in tools/vst/contracts.py, which conflicts with main and alters a hash-pinned parser; main already has a no-skip verdict in tools/qa/gate_check.py. Re-derive in U3-5 if needed.; flags: DUPLICATES_MAIN_TOOLS_QA | ref: U3-5 |
| R17-qa-wsl-root | `tools/qa/**` (except `tools/qa/pytest_pass_plugin.py`, `tools/qa/fixtures.py`, `tools/qa/matrix.py`) | absent | 2 | EVIDENCE_ONLY | WSL snapshot transfer, root harness and requirements.in for the WSL runtime path; runtime-bootstrap scope, not U3. | - |
| R18-qa-tools-conflict | `tools/qa/**` | differs | 4 | DROPPED | Older branch implementation of modules main already ships and has accepted (registry, runner, report, plugin, dependencies, WSL scripts). Landing it would silently duplicate or regress main's tools/qa. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN, DUPLICATES_MAIN_TOOLS_QA | - |
| R20-vst-tests-new | `tests/vst/**` | absent | 2 | EVIDENCE_ONLY | S2/S3/S5 tests for unlanded VST changes; outside U3 scope. | - |
| R21-vst-tests-conflict | `tests/vst/**` | differs | 2 | DROPPED | Branch edits of S2/S3 VST tests matching the branch's own tools/vst changes. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |
| R22-vst-tools-new | `tools/vst/**` | absent | 1 | EVIDENCE_ONLY | Worker capability-drop helper and S5 source-tree code; S2/S3/S5 scope, not U3. | - |
| R23-vst-tools-conflict | `tools/vst/**` | differs | 9 | DROPPED | Branch edits of VST runner/store/gate/pilot/dispatch modules; S2/S3/S5 scope and main's tools/vst is accepted and newer. Same path exists on main with different content, so copying it would overwrite or conflict with main.; flags: CONFLICT_WITH_MAIN | - |

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

- CONFLICT_WITH_MAIN: path exists on main with different content; not landed.
- DUPLICATES_MAIN_TOOLS_QA: the file would add a second mechanism next to main's accepted tools/qa or its seeded-failure catalog.

## Checker summary (output of one run, rules file unchanged)

```json
{
  "base_ref": "origin/main",
  "base_tip": "fa26e3cb3bbf93bb5849f6119e1483a539035dd1",
  "branches": {
    "origin/s4-canonical-continuation": {
      "class_counts": {
        "ALREADY_ON_MAIN": 291,
        "DROPPED": 89,
        "EVIDENCE_ONLY": 344,
        "LAND": 0
      },
      "conflict_prone_count": 78,
      "conflict_prone_truncated": false,
      "files": 724,
      "main_state_counts": {
        "absent": 344,
        "differs": 89,
        "identical": 291
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "3b14f20584fbe8fed1d758753343ea8d132a5706"
    },
    "origin/s4-e2e-snapshot-20261025-180e330": {
      "class_counts": {
        "ALREADY_ON_MAIN": 0,
        "DROPPED": 21,
        "EVIDENCE_ONLY": 173,
        "LAND": 0
      },
      "conflict_prone_count": 18,
      "conflict_prone_truncated": false,
      "files": 194,
      "main_state_counts": {
        "absent": 173,
        "differs": 21
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "9fd992f8835b458f99242c2f7fc9e231b7cc3b6b"
    },
    "origin/s4-native-qa-runner": {
      "class_counts": {
        "ALREADY_ON_MAIN": 0,
        "DROPPED": 21,
        "EVIDENCE_ONLY": 176,
        "LAND": 0
      },
      "conflict_prone_count": 18,
      "conflict_prone_truncated": false,
      "files": 197,
      "main_state_counts": {
        "absent": 176,
        "differs": 21
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "8f95efcebe487c5da5087a7e0aadbc44d43db31f"
    },
    "origin/s4-reproducible-qa-automation": {
      "class_counts": {
        "ALREADY_ON_MAIN": 5,
        "DROPPED": 31,
        "EVIDENCE_ONLY": 139,
        "LAND": 0
      },
      "conflict_prone_count": 28,
      "conflict_prone_truncated": false,
      "files": 175,
      "main_state_counts": {
        "absent": 139,
        "differs": 31,
        "identical": 5
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "3b8d80ff5456192c2419d9515b47fb843939ee16"
    },
    "origin/s5-bounded-aeve-evidence": {
      "class_counts": {
        "ALREADY_ON_MAIN": 0,
        "DROPPED": 23,
        "EVIDENCE_ONLY": 46,
        "LAND": 0
      },
      "conflict_prone_count": 20,
      "conflict_prone_truncated": false,
      "files": 69,
      "main_state_counts": {
        "absent": 46,
        "differs": 23
      },
      "merge_base": "3505f769f9c1c245d368a8318aeb04a76e1c5537",
      "tip": "b954c6f4dc12a83bbcc2b92e1d0f73c454ea3bcf"
    }
  },
  "ok": true,
  "rule_count": 23,
  "rules_sha256": "66113f6e8b4b5ae39e9d992f2438097f6845a2c5899c28f63100e2e4e95b76fb",
  "schema_version": 1
}
```
