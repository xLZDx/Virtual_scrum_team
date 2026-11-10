# U4-1 GPT-PM code review scope

Task: U4-1, project-scope role registration. Base 3c432a8 (main after U3), head = current HEAD (two commits). Review the delta only: tools/uc/project_roles.py, docs/sdlc/u4/PROJECT_ROLES.md, tests/uc/test_u4_project_roles.py (tests are NOT_RUN; judge by reading), the one-line entry in tools/qa/build_registry.py.

Delivers: scan_project_roles(project_root, project_label) builds a deterministic manifest of a project's .claude agents and skills; register_project_roles adds each as NOT_COVERED_NO_PROFILE (class LOCAL_PLUS_MODEL, reason "not mapped yet") unless an explicit data mapping with matching source_sha256 and matrix-listed executors lifts it to COVERED_PARTIAL; validate_extended_table and a validate subcommand require the exact builder shape; the extended table has its own canonical sha256 (equal to router.load_table_with_digest of the written file) so role_table_sha256 changes when a role is added or edited and the existing gate ROLE_TABLE_DRIFT refusal fires until the pin is re-issued. The gate, role_table.py, router.py and AEVE are unchanged.

Already fixed after three read-only reviews (python 3 MAJOR, security 2 MAJOR, tests 2 MAJOR): required explicit project label, newline-normalized digests, no-raise validators, fail-closed frontmatter and normalized name collision checks, exact project-entry validation, descriptor-based bounded reads, redacted messages, mkstemp atomic write, real symlink/junction tests.

Settled, do not reopen: no AEVE change (U4-2..U4-6 not approved); wiring the extended table into the live router run and re-pinning the gate are owner steps outside this task; the race between link pre-check and open is documented and only partly closed; no test, mutation or CI run (pytest forbidden), evidence is static.

Ask: the complete BLOCKER/MAJOR set for this delta only.

## Verification round (after GPT-PM round 1, reply d6aa746b, MAJOR x1)
Base: e004584. Fixed: validate_extended_table takes the mapping document; every COVERED_PARTIAL project entry needs a mapping entry whose kind, name, source_sha256 (equal to the manifest), canonical_role and executors match both the table entry and the AEVE matrix, otherwise a problem string; a mapping entry that matches no manifest entry or is not applied by the table is a problem; the validate subcommand gains --mapping (absent means any COVERED_PARTIAL project entry is invalid); register passes its mapping to the post-build validation; tests include a hand-promoted unmapped role being rejected. Files: tools/uc/project_roles.py, tests/uc/test_u4_project_roles.py, docs/sdlc/u4/PROJECT_ROLES.md. Ask: confirm this MAJOR is resolved and name any regression caused by the fix; nothing else.
