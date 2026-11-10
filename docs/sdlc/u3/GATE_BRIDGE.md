# U3-5: QA gate bridge

Module: `tools/qa/gate_bridge.py`. Tests: `tests/qa/test_u3_gate_bridge.py` (written, **NOT_RUN**: pytest is forbidden by the operator for this sprint, so no result is claimed).

## Problem

`tools/vst/gate.py` (`_check_artifacts`) already requires every `(path, digest)` in a deciding TestRun receipt's `artifact_digests` to equal `artifact_resolver(path)`, and denies by default when no resolver is supplied. No code built a resolver, and `tools/qa/gate_check.py` is advisory only, so a skipped or uncollected required test could still be offered to the gate.

## Contract

`make_qa_artifact_resolver(repo_root, *, expected_head, registry, fallback=None) -> Callable[[str], str | None]`

- Path is exactly `docs/sdlc/evidence/qa/<category>.{report.jsonl,stdout.txt,stderr.txt}` (strict regex, repo-relative posix) and `<category>` is in the registry's closed category set: all three files are read (regular files only, no symlink/junction/reparse point on any component, one hard link, size caps 8 MiB for the report and 32 MiB for stdout/stderr), the last report line is selected (`select_record`), the stdout/stderr byte ranges recorded in `artifact_ranges` are sliced out (the artifacts are append-only), and `check_report(..., expected_head=expected_head, artifact_bytes=...)` decides.
- The sha256 of the raw file bytes is returned only if the check is `APPROVABLE`, the record's `category` equals the path's category, and the record's `artifact_paths` equal the three fixed paths. The stdout/stderr paths resolve (to the sha256 of their raw file bytes) only as siblings of an approvable report.
- Everything else returns `None`: `NON_APPROVING`, any exception, a malformed or unknown QA path, a traversal / absolute / backslash / differently-cased spelling of the QA directory (these are QA-owned and never reach the fallback).
- A path outside the QA directory goes to `fallback(path)` when given (exception or non-string result becomes `None`), otherwise `None`.

`qa_gate_reasons(repo_root, category, *, expected_head, registry) -> GateCheck` returns the typed verdict the resolver acts on, through the same read code (`_load`). It never raises. Bridge-specific reason codes: `REPORT_UNREADABLE`, `CATEGORY_PATH_MISMATCH`, `BAD_EXPECTED_HEAD`; the rest come from `gate_check`.

No new gate authority: the module does not sign, hold keys, change `tools/vst/gate.py`, or offer any waiver path. A `NON_APPROVING` report simply resolves to `None`, so the gate reports a digest mismatch and rejects the receipt.

## Limits

- The digest binds bytes only. Head binding comes from `check_report` (`candidate_head` and `head_after` equal `expected_head`); the registry binding comes from `registry_sha256`.
- Whether a TestRun receipt's own path list names the QA report at all, and whether the receipt's reported test IDs match the report, is not compared here (the U2-known open limit). A receipt that lists no QA path is unaffected by this resolver.
- The report is candidate-attested evidence (see `TRUST_MODEL` in `tools/qa/run.py`); the bridge detects accidental or naive tampering, not code running inside the pytest process.
- Read-then-hash is not atomic against a concurrent writer; each resolver call re-verifies the bytes it hashes, so a returned digest always belongs to bytes that passed the check at that moment.
- Wiring the resolver into the callers of `gate.evaluate` is the caller's job; this task supplies the function only.
- No test, mutation or CI run was performed. Everything above is NOT_RUN.
