# U4-1 Project-scope role registration

Module: `tools/uc/project_roles.py`. Tests: `tests/uc/test_u4_project_roles.py`.

## Contract

1. **Manifest** (`uc.project-roles.v1`). `scan_project_roles(project_root, project_label)` lists
   `<project>/.claude/agents/*.md` and `<project>/.claude/skills/*/SKILL.md` as entries
   `{kind, name, path, source_sha256, scope: "project"}`, sorted by `(kind, name)`. `path` is repo-relative POSIX.
   - **The label is an explicit required input** (CLI `--project-label`); it never defaults from the folder name,
     so the manifest does not depend on where the checkout lives.
   - **File filters are case-sensitive:** only exact `*.md` in `agents/` and exactly `SKILL.md` in a skill directory.
   - **`source_sha256` is newline-normalized:** a leading BOM is dropped and CRLF / CR become LF before hashing
     the UTF-8 text, so the digest does not depend on the checkout's line endings.
   - **Name:** the frontmatter `name:` value or, without one, the file stem / skill directory name. The two must
     be equal. Pattern `^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9_-])?$` (no trailing dot or space).
   - Refused (`ProjectRolesError.code`): `LINK_REFUSED` (symlink, junction, reparse point, or a file with more than
     one hard link, on the file, its directory, `agents/`, `skills/` or `.claude`), `NOT_A_REGULAR_FILE`,
     `FILE_TOO_LARGE` (> 256 KiB), `NOT_UTF8`, `IO_ERROR`, `TOO_MANY_ENTRIES` (> 2000, counted while listing),
     `DUPLICATE_NAME` (casefolded, across agents and skills, because the router resolves roles by name only),
     `PROJECT_ROOT_MISSING`, `BAD_LABEL`, and `BAD_NAME` for any name problem or frontmatter irregularity:
     bare CR line endings, Unicode line separators (U+0085, U+2028, U+2029, VT, FF, FS/GS/RS) inside the block, an
     unterminated block, a quoted / differently cased / spaced key that normalizes to `name`, a duplicated `name`
     key, an empty value, or a declared name that differs from the file or directory name.
   - Each file is opened once; the descriptor is checked (regular file, one link, not a reparse point) and at most
     the size cap plus one byte is read from it.
2. **Registration.** `register_project_roles(base_table, manifest, mapping=None, matrix=None)` returns a new table:
   the base entries plus one `scope: "project"` entry per manifest item, `class` and `draft_class`
   `LOCAL_PLUS_MODEL`, `coverage_state` `NOT_COVERED_NO_PROFILE`, reason `project-scope role, not mapped yet`.
   The router therefore answers `NOT_COVERED` (`no-aeve-profile`) for it. Adding a role file needs no code change:
   rescan and re-register. Refused: a project name equal (casefolded, trailing dot/space stripped) to a base-table
   name (`NAME_COLLIDES_WITH_GLOBAL_ROLE`); an unmapped name equal to an AEVE profile id
   (`NAME_EQUALS_AEVE_PROFILE`); a base table that already holds project entries; a malformed manifest, base table
   or mapping (`BAD_MANIFEST`, `BAD_BASE_TABLE`, `BAD_MAPPING`, `MALFORMED_INPUT`). Only `ProjectRolesError` escapes.
   Counts are regenerated; a `project_roles` stamp `{schema, project, manifest_sha256}` is added.
3. **Mapping is data.** `uc.project-role-mapping.v1`: `entries[{kind, name, source_sha256, canonical_role,
   executors}]`. `source_sha256` must equal the manifest entry's digest, so a mapping written for an older file
   version is refused (`BAD_MAPPING`). A mapped role becomes `COVERED_PARTIAL` only if the AEVE matrix lists exactly
   those executors for `canonical_role` (`MAPPING_EXECUTORS_NOT_IN_MATRIX`); mapping without a matrix is refused
   (`MATRIX_REQUIRED`); a mapping for a role absent from the manifest is refused (`MAPPING_FOR_UNKNOWN_ROLE`).
4. **Validation.** `validate_extended_table(table, inventory, manifest, matrix, probe_record)` returns a list of
   problem strings and never raises. It runs the unchanged `role_table.validate_role_table` on the global entries,
   then requires every project entry to equal, key for key, what the builder produces: unmapped (exact key set,
   class and draft_class `LOCAL_PLUS_MODEL`, `class_upgraded_by_evidence` false, `model_remainder_hint` empty, exact
   reason, no executors, no profile) or mapped (`COVERED_PARTIAL`, exactly the matrix's executors, exact mapped
   reason). It also checks path and source digest against the manifest, no missing or extra entries, the stamp and
   the counts. **Authorization comes only from the mapping document, never from the table entry itself:** the
   function takes an optional `mapping` (same `uc.project-role-mapping.v1` format; None means no mapping). Every
   `COVERED_PARTIAL` project entry needs a mapping entry whose kind, name, `source_sha256` (equal to the manifest's),
   `canonical_role` and executors match both the table entry and the matrix; otherwise the problem is
   `COVERED_PARTIAL without a matching mapping entry`. A mapping entry that matches no manifest entry, or whose
   role the table does not map, is also a problem, and a malformed mapping is a problem string, not an exception.
   A hand-edited unmapped entry promoted to `COVERED_PARTIAL` therefore fails, and a properly mapped table
   validates only when the same mapping is supplied. `validate_manifest` cross-checks kind against path and name against the file or directory name, and
   never raises.
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
python tools/uc/project_roles.py scan     --project-root <repo> --project-label <label> (--print | --out manifest.json)
python tools/uc/project_roles.py register --project-root <repo> --project-label <label> --base-table catalog/role_table.json \
    --aeve-root <AEVE> --inventory catalog/inventory.json [--mapping mapping.json] (--print | --out table.json)
python tools/uc/project_roles.py validate --project-root <repo> --project-label <label> --table table.json \
    --aeve-root <AEVE> --inventory catalog/inventory.json [--mapping mapping.json]
```

`register` validates its own output against the mapping it was given. `validate --mapping` is optional; without it
a table with any `COVERED_PARTIAL` project entry is invalid.

`--print` writes nothing and prints a JSON summary (manifest digest, or table digest, counts and stamp). `validate`
also checks that the table file bytes are the canonical serialization, so the reported digest is the file digest.
Exit codes: 0 success; 1 refused or invalid (`{"status": "REFUSED", "code", "detail"}` or problem lines plus
`INVALID: n problem(s)`); 2 blocked: AEVE probe failure, or unreadable / malformed input files (`code`
`INPUT_ERROR`). The CLI catches `OSError`, `ValueError`, `KeyError`, `TypeError`, `AttributeError`,
`RecursionError`; no traceback is the normal failure mode.
`--out` is refused when it equals any input path or lies inside `<project>/.claude` (`OUT_IS_INPUT`,
`OUT_INSIDE_ROLE_DIRECTORY`); the write goes through `tempfile.mkstemp` in the output directory and `os.replace`,
and the temporary file is removed in a `finally`.
Output hygiene: names and labels are never echoed raw. Untrusted text is shown as a short plain `repr` (at most 40
printable characters, no credential-shaped text per `tools/uc/secret_patterns.py`) or as `<len=N sha256=PREFIX>`;
printed problem lines are stripped of control characters and withheld if credential-shaped.

## Evidence status

NOT_RUN. Nothing in this task was executed: no pytest, no Python, no CLI invocation, no registry rebuild. The module
and tests are statically written only. The test module is registered in `MAIN_TEST_FILE_CATEGORIES` in
`tools/qa/build_registry.py`; the registry itself was not regenerated.

## Limits

- The tests use a synthetic base table and matrix and a stubbed AEVE probe; they do not exercise a real AEVE checkout
  or the committed `catalog/role_table.json`. Symlink, junction and hard-link tests `pytest.skip` when the host
  cannot create them (junctions need Windows `mklink /J`).
- Link detection uses `lstat`, `os.path.isjunction`, the reparse attribute and a descriptor `fstat`
  (`st_nlink == 1`). `os.open` follows a link that appears between the pre-check and the open; the descriptor
  check catches reparse points and hard links but not an ordinary symlink swapped in that window. The scan is a
  point-in-time read and the digests bind the content that was read.
- `catalog/inventory.json` (builder `tools/catalog/extract_inventory.py`) is untouched; project roles live only in
  the manifest and the extended table. The frontmatter reader here is stricter than the inventory parser and is a
  separate minimal implementation, so a file the inventory accepts can be refused here.
- A mapped role is always class `LOCAL_PLUS_MODEL`; the model remainder is not narrowed. Mapping can only produce
  `COVERED_PARTIAL`; `MODEL_ONLY` / `OUT_OF_SCOPE` classification of project roles is not supported.
- Global-part messages produced by `role_table.validate_role_table` echo table text; the CLI sanitizes printed
  lines but that module was not changed.
- Re-pinning the gate value and wiring the extended table into the live router invocation are owner steps and are
  not done here.
