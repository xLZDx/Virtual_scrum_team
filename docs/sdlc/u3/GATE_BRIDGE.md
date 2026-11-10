# U3-5: QA gate bridge

Module: `tools/qa/gate_bridge.py`. Tests: `tests/qa/test_u3_gate_bridge.py` (written, **NOT_RUN**: pytest is forbidden by the operator for this sprint, so no result is claimed).

## Problem

`tools/vst/gate.py` (`_check_artifacts`) already requires every `(path, digest)` in a deciding TestRun receipt's `artifact_digests` to equal `artifact_resolver(path)`, and denies by default when no resolver is supplied. No code built a resolver, and `tools/qa/gate_check.py` is advisory only, so a skipped or uncollected required test could still be offered to the gate.

## Contract

`make_qa_artifact_resolver(repo_root, *, expected_head, registry, fallback=None) -> Callable[[str], str | None]`

- Path is exactly `docs/sdlc/evidence/qa/<category>.{report.jsonl,stdout.txt,stderr.txt}` (strict regex, repo-relative posix) and `<category>` is in the registry's closed category set: all three files are read, the last report line is selected (`select_record`), the stdout/stderr byte ranges recorded in `artifact_ranges` are sliced out (the artifacts are append-only; the range must end at the end of the file), and `check_report(..., expected_head=expected_head, artifact_bytes=...)` decides.
- File reads: no symlink / junction / reparse point on any component, directories on the way, a regular file with one hard link, the opened file must be the lstat'ed file (inode and device), size caps 8 MiB for the report and 32 MiB for stdout/stderr, read into one preallocated buffer.
- The sha256 of the raw file bytes is returned only if the check is `APPROVABLE`, the record's `category` equals the path's category, and the record's `artifact_paths` equal the three fixed paths. The stdout/stderr paths resolve (to the sha256 of their raw file bytes) only as siblings of an approvable report.
- One verified snapshot per category is kept inside a resolver instance and reused while the three files' (size, mtime_ns, inode, mode) are unchanged, so the report, stdout and stderr digests of one receipt come from one snapshot. A changed fingerprint forces a re-read and re-check. Use a new resolver per `evaluate` call.
- Everything else under the QA directory returns `None`: `NON_APPROVING`, any exception, malformed or unknown QA path, and any traversal / absolute / backslash / differently cased spelling. Ownership is computed on both the raw and the `posixpath.normpath`'d form.

### Fallback (allowlist)

A path reaches `fallback(path)` only if all of these hold: it matches `[A-Za-z0-9_./-]+`, is relative, has no empty, `.` or `..` segment, no segment ending in `.`, no `~` and no `:`, `posixpath.normpath(path) == path`, and neither the raw nor the normalized form is QA-owned. Anything else returns `None` without calling the fallback. This blocks Windows aliases such as `qa.`, `qa::$DATA`, `qa::$INDEX_ALLOCATION` and 8.3 names. The fallback result must match `^[0-9a-f]{64}$` or it becomes `None`; an exception becomes `None`.

A fallback that reads files must use the no-link reader `read_regular_file(root, relative_posix_path, cap)` exported by the bridge (same rules as above, raises on any violation). The bridge does not constrain what the fallback does itself.

### Diagnostics

`qa_gate_reasons(repo_root, category, *, expected_head, registry) -> GateCheck` returns the typed verdict the resolver acts on, through the same read code (`_load`). It never raises. Every reason detail is redacted (secret, token, user-path and absolute-path patterns from `tools/qa/run.py`) and bounded to 200 characters. Bridge-specific reason codes: `REPORT_UNREADABLE`, `CATEGORY_PATH_MISMATCH`, `BAD_EXPECTED_HEAD`, `EVIDENCE_TOO_LARGE`; the rest come from `gate_check`.

No new gate authority: the module does not sign, hold keys, change `tools/vst/gate.py`, or offer any waiver path. A `NON_APPROVING` report simply resolves to `None`, so the gate reports a digest mismatch and rejects the receipt.

## Limits

- **Evidence cap lock-out.** The evidence files are append-only. Once any of them exceeds its cap the lane reports `EVIDENCE_TOO_LARGE` and nothing resolves for that category until an operator archive step moves the old evidence out. No rotation or archive tool is implemented.
- The digest binds bytes only. Head binding comes from `check_report` (`candidate_head` and `head_after` equal `expected_head`); the registry binding comes from `registry_sha256`.
- Whether a TestRun receipt's own path list names the QA report at all, and whether the receipt's reported test IDs match the report, is not compared here (the U2-known open limit). A receipt that lists no QA path is unaffected by this resolver.
- The report is candidate-attested evidence (see `TRUST_MODEL` in `tools/qa/run.py`); the bridge detects accidental or naive tampering, not code running inside the pytest process.
- The snapshot fingerprint is metadata-based: a same-size rewrite that preserves mtime and inode would not be noticed inside one resolver instance. The memoized bytes of an approvable category (up to about 72 MiB) stay in memory for the life of the instance.
- Read-then-hash is not atomic against a concurrent writer; each fresh read re-verifies the bytes it hashes.
- On Windows the inode/device comparison relies on `st_ino`/`st_dev` being populated by both `lstat` and `fstat`; if a Python build reports them differently the read fails closed (resolves to `None`).
- Wiring the resolver into the callers of `gate.evaluate` is the caller's job; this task supplies the function only.
- No test, mutation or CI run was performed. Everything above is NOT_RUN.
