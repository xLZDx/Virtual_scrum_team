# U4-1 Project-scope role registration

Module: `tools/uc/project_roles.py`. Tests: `tests/uc/test_u4_project_roles.py`.

## Contract

1. **Manifest** (`uc.project-roles.v1`). `scan_project_roles(project_root)` lists
   `<project>/.claude/agents/*.md` and `<project>/.claude/skills/*/SKILL.md` as entries
   `{kind, name, path, source_sha256, scope: "project"}`, sorted by `(kind, name)`. `path` is repo-relative POSIX.
   The name is the frontmatter `name:` or the file stem / skill directory name (same rule as
   `tools/catalog/extract_inventory.py`). Refused (`ProjectRolesError.code`): `LINK_REFUSED` (symlink, junction or
   reparse point on the file, its directory, `.claude`), `FILE_TOO_LARGE` (> 256 KiB), `NOT_UTF8`, `BAD_NAME`
   (`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`), `DUPLICATE_NAME` (unique across agents and skills, because the router
   resolves roles by name only), `TOO_MANY_ENTRIES` (> 2000), `PROJECT_ROOT_MISSING`, `BAD_LABEL`.
2. **Registration.** `register_project_roles(base_table, manifest, mapping=None, matrix=None)` returns a new table:
   the base entries plus one `scope: "project"` entry per manifest item, `class` `LOCAL_PLUS_MODEL`,
   `coverage_state` `NOT_COVERED_NO_PROFILE`, reason `project-scope role, not mapped yet`. The router therefore
   answers `NOT_COVERED` (`no-aeve-profile`) for it. Adding a role file needs no code change: rescan and
   re-register. A project name equal to any base-table name is refused (`NAME_COLLIDES_WITH_GLOBAL_ROLE`).
   Counts are regenerated; a `project_roles` stamp `{schema, project, manifest_sha256}` is added.
3. **Mapping is data.** `uc.project-role-mapping.v1`: `entries[{kind, name, canonical_role, executors}]`. A mapped
   role becomes `COVERED_PARTIAL` only if the AEVE matrix lists exactly those executors for `canonical_role`
   (`MAPPING_EXECUTORS_NOT_IN_MATRIX` otherwise); mapping without a matrix is refused (`MATRIX_REQUIRED`); a mapping
   for a role absent from the manifest is refused.
4. **Validation (stricter than the matrix, never looser).** `validate_extended_table(table, inventory, manifest,
   matrix, probe_record)` runs the unchanged `role_table.validate_role_table` on the global entries, then checks
   every project entry against the manifest (path, source digest, no missing or extra entries), forbids coverage
   the matrix does not list, forbids executors on `NOT_COVERED_*`, and checks the stamp and counts.
5. **Hash and drift.** `table_sha256(table)` is the sha256 of `serialize_table(table)` (the same bytes
   `role_table.py build` writes). Written to a file and loaded with `router.load_table_with_digest`, the router
   emits exactly this value as `role_table_sha256` in `uc.role-result.v1`. Adding, removing or editing any project
   role file changes `source_sha256`, the manifest digest and the table digest.
   The gate (`tools/vst/gate.py`, U2 hard refusal `ROLE_TABLE_DRIFT`) compares the receipt's `role_table_sha256`
   with the gate-owned `analyzer_trust["pinned"]["role_table_sha256"]` by strict equality. No gate code changed:
   after a role is added, a receipt carrying the new digest against the old pin is refused with `ROLE_TABLE_DRIFT`;
   the pin is re-issued deliberately by the pin owner from the new `table_sha256`.

## CLI

```
python tools/uc/project_roles.py scan --project-root <repo> --print            # or --out manifest.json
python tools/uc/project_roles.py register --project-root <repo> --base-table catalog/role_table.json \
    --aeve-root <AEVE> --inventory catalog/inventory.json [--mapping mapping.json] (--print | --out table.json)
```

`--print` writes nothing and prints a JSON summary (manifest digest, or table digest, counts and stamp).
`register` validates before writing; invalid output exits 1, a refused scan exits 1, an AEVE probe failure exits 2.
`--out` writes the manifest (scan) or the serialized table (register) atomically.

## Evidence status

NOT_RUN. Nothing in this task was executed: no pytest, no Python, no CLI invocation, no registry rebuild. The module
and tests are statically written only. The test module is added to `MAIN_TEST_FILE_CATEGORIES` in
`tools/qa/build_registry.py`; the registry itself was not regenerated.

## Limits

- The tests use a synthetic base table and matrix; they do not exercise a real AEVE checkout or the committed
  `catalog/role_table.json`. The CLI `register` path (AEVE probe) is not covered by tests.
- Link detection uses `lstat`/`os.path.isjunction`/reparse attribute; races between scan and use are not closed
  (scan is a point-in-time read, the digests bind the content that was read).
- `catalog/inventory.json` (global inventory builder `tools/catalog/extract_inventory.py`) is untouched; project
  roles live only in the manifest and the extended table.
- A mapped role is always class `LOCAL_PLUS_MODEL`; the model remainder is not narrowed. Mapping can only produce
  `COVERED_PARTIAL`; `MODEL_ONLY` / `OUT_OF_SCOPE` classification of project roles is not supported.
- Frontmatter `name:` parsing is a minimal copy of the inventory rule (scalar top-level key only), not an import.
- Re-pinning the gate value and wiring the extended table into the live router invocation are operator/owner steps and
  are not done here.
