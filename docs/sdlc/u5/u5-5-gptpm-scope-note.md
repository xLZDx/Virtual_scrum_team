# U5-5 GPT-PM code review scope

Task: U5-5, final package builder for GPT-PM. Base: U5-4 approved head, head = current HEAD. Review the delta only: tools/vst/final_package.py, docs/sdlc/u5/FINAL_PACKAGE.md, tests/vst/test_u5_final_package.py (tests are NOT_RUN; judge by reading), tools/qa/build_registry.py (two map lines), core/DECISION_LOG.md and core/LESSONS_LOG.md entries.

Delivers: `build_final_package`, a pure function (no git, file, network, clock or model; `now` injected) that returns READY, REFUSED or BLOCKED and, for READY, a package bound to one head with `package_sha256` over `contracts.canonical_bytes`. Every piece of evidence (test records, review result final head and last iteration head, receipts, isolation proof, patch origin record) must name the package head, else REFUSED `STALE_EVIDENCE` naming the item. The diff bytes must hash to the recorded digest and parse (`worker_gate.parse_diff_paths`) to exactly the declared path set. The review must be CLEAN and a replayed result needs `replay_store_verified`. A FAIL, an unacknowledged required NOT_RUN or SKIPPED test (`allow_not_run` ids with a reason), a failed or dishonest isolation proof and secret-like evidence text (`receipt_builder._refuse_secrets`) are REFUSED; malformed or oversized input is BLOCKED. NOT_RUN items are listed under `not_run` and never counted as passed; declared limits are copied verbatim next to derived limits. `verify_package_current` refuses a changed head or diff; `render_scope_note` renders deterministic Markdown with no claim stronger than the data. No other U5 module was edited; the new code only imports them.

Interpretation decisions:
- `diff_sha256` (the recorded digest) is an extra required argument: the acceptance text needs something recorded to compare the bytes with.
- The package holds the diff digest and path list, not the diff bytes; PM Bridge delivers the diff by `--base/--head`.
- The diff and the paths are not secret-scanned (the shared pattern matches ordinary identifiers such as `secret_patterns`); everything else is.
- A review result with `replayed` True is refused unless the caller states `replay_store_verified`; the to_dict form cannot show it.
- A required NOT_RUN or SKIPPED test needs an `allow_not_run` reason; a test marked `required: false` is only listed. An acknowledgement for a test that ran is BLOCKED.
- No test record at all is REFUSED `NO_TEST_EVIDENCE`; a package where every test is acknowledged NOT_RUN is READY and says no test has PASS evidence.
- The isolation proof's `candidate_head` is `ascii(head)` in `worker_gate`; both the plain and the ascii form are accepted.
- REFUSED returns no package; BLOCKED reports the first malformed item only.

Limits: nothing was run; evidence is unsigned and provenance is not checked; the review result carries no paths digest; no wiring to the store, PM Bridge or `gate.py`; `docs/qa/categories.json` was not regenerated.

Tests: written, NOT_RUN (running tests is forbidden by the operator). Evidence is static reading and `ast.parse` only.
