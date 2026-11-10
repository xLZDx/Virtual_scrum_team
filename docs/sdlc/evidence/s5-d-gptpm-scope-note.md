# S5-D GPT-PM code review scope

Task: S5-D (VST-041), truthful rule coverage and finding evidence map. Base 826ac9e (S5-C accepted), head = current HEAD. Review: tools/vst/rule_coverage.py (new), docs/qa/aeve_required_rules.json (frozen catalog), tests/qa/seeded_failure/aeve_fixtures/ (4 synthetic fixture pairs AF-001..AF-004 with index.json). docs/qa/categories.json is generated.

Delivers (plan docs/S5_AEVE_GATE_PLAN_2026-10-24.md section 2, E4: S5.4.1, AC-7, AC-8): a frozen required-rule catalog where a rule is REQUIRED only if linked to a fixture that seeds that very rule (confirmed by one `aeve analyze` run per variant in temp git repos, AEVE HEAD 25a8fea: defective variant yields the expected finding, clean variant does not); mandatory pin FROZEN_CATALOG_SHA256 and dependency digests (S4 catalog, fixture index) verified on load; fixture integrity checks (hashes, line, paths); build_static_coverage producing v3 StaticAnalysis fields: FULL only if every required rule is SUPPORTED_AND_CHECKED, omitted/duplicate/unknown/overlapping statuses and malformed findings raise typed CoverageError, empty findings never mean clean unless coverage is FULL.

Already fixed after two read-only reviewer passes (python-reviewer 6 MAJOR, functional-test-reviewer 3 MAJOR).

Settled, do not reopen: gate wiring is S5-E; signing S5-B; adapter S5-C; AEVE scans the whole git root so unrelated uncovered files prevent FULL (documented); only 4 rules are required, others optional. Tests NOT_RUN (operator forbids pytest); the module was not executed; evidence is static review plus the fixture confirmation runs.

Ask: the complete BLOCKER/MAJOR set for this delta only.

## Verification round (after GPT-PM round 1, reply 6e459700, MAJOR x1)
Base: 3cd5ad3. Fixed: load_catalog now raises CATALOG_PIN_MISMATCH unless expected_sha256 equals FROZEN_CATALOG_SHA256 (one added check at the start of load_catalog in tools/vst/rule_coverage.py). Ask: verify this one correction and direct regressions only.
