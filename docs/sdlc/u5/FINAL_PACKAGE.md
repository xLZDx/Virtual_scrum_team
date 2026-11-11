# U5-5: final package builder for GPT-PM

Module: `tools/vst/final_package.py`. Tests: `tests/vst/test_u5_final_package.py` (written, **NOT_RUN**: running tests is forbidden by the operator for this sprint; nothing was executed, only syntax-parsed).

Acceptance (PROJECT_PLAN U5-5): builds the package with the exact diff, test evidence, review results and head identity; refuses stale evidence; a new commit invalidates it.

## What it is

A pure function. It reads no git, no file, no network and no clock and calls no model: every fact is an argument, `now` included. It checks that the facts agree with each other and with ONE head. It does not check who produced them (all evidence is caller-supplied and unsigned here).

Relation to the global GPT-PM flow: the diff itself is still delivered by PM Bridge (`review.js --base <base_head> --head <head>`, which redacts secrets); this package is the evidence bundle that travels with it. It therefore holds the diff sha256, byte count and path list, never the diff bytes. The reviewer can recompute the digest of the diff PM Bridge shows and compare.

## Public API

| Name | Purpose |
|---|---|
| `build_final_package(*, story_id, base_head, head, diff_bytes, diff_sha256, changed_paths, test_evidence, required_test_ids, review_results, receipts, isolation_proof, patch_origin_share, now, allow_not_run=None, declared_limits=(), replay_store_verified=False) -> PackageResult` | decide and build; never raises for input problems, never mutates inputs (deep copies) |
| `PackageResult(verdict, reasons, package, package_sha256)` | verdict READY / REFUSED / BLOCKED; `reasons` are `(code, ascii detail)`; `package` and digest only for READY |
| `verify_package_current(package, current_head, current_diff_sha256, package_sha256) -> (ok, reasons)` | a new commit (head or diff differs) makes the package not current; `package_sha256` is required and the package is re-hashed; every embedded head must equal `head` |
| `render_scope_note(package) -> str` | deterministic English Markdown from a package; all evidence-derived text goes through `escape_markdown` |
| `escape_markdown(value) -> str` | one line; backslash-escapes backslash, backtick, `*`, `_`, `[`, `]`, `<`, `>`, `&` and `|`; escapes a leading `#`, `-`, `+`, `=`, `~` or `1.`; control characters become spaces |
| `PackageResult` | immutable; `package` returns a fresh deep copy on every access |

## Inputs

* `diff_sha256`: the recorded diff digest (for example from the gate evidence). `diff_bytes` must hash to it.
* `required_test_ids`: non-empty unique list of test ids from the caller; each needs a record and must be PASS, or NOT_RUN/SKIPPED with an `allow_not_run` reason. Ids are printable ASCII (pytest node ids with spaces and brackets are fine), at most 200 characters.
* `test_evidence`: records `{test_id, status, evidence_sha256, head}` plus optional `reason`. A record cannot carry its own `required` flag (BLOCKED); records outside `required_test_ids` are informational and listed. Status is PASS, FAIL, NOT_RUN or SKIPPED. PASS and FAIL need a digest and the head they were produced at; NOT_RUN and SKIPPED may carry null for both.
* `allow_not_run`: `{test_id: reason}`; the explicit, operator-visible acknowledgement that a NOT_RUN or SKIPPED required test may stay unrun. A reason must be non-empty. An id that is not a NOT_RUN or SKIPPED record is BLOCKED.
* `review_results`: `ReviewLoopResult.to_dict()` (U5-4). `story_id` must equal the package story (None or missing: `REVIEW_STORY_MISMATCH`). Only the verdict, reasons, `iteration_count`, `final_head`, `replayed`, `declared_coverage` and the last iteration are read; the whole document is hashed (`result_sha256`).
* `receipts`: `{receipt_id, head, receipt_sha256}` plus optional `receipt_type`; `result` is required and must be exactly `PASS`, else `RECEIPT_NOT_PASS` (missing: "result missing"). The head is the receipt `candidate_head`, as in `tools/vst/gate.py`.
* `isolation_proof`: `worker_gate.build_isolation_proof` output. Its `candidate_head` is stored as `ascii(head)`; both forms are accepted.
* `patch_origin_share`: a `patch_proposals.build_run_record` dict, or None (listed as a derived limit). When given it must carry `candidate_head` and `diff_sha256` equal to the package head and the recorded digest, verdict `ACCEPTED`, `applied` true and `partial` false; list fields hold plain path strings, overrides small objects of short strings.
* `declared_limits`: strings copied verbatim into the package.
* `replay_store_verified`: set True only by a caller that checked a replayed review result against the pipeline store (see below).

## Verdicts

Refusal details are fixed text plus validated item names (test, receipt and property ids, heads, path names as ASCII-escaped text); unvalidated evidence text is never echoed.

BLOCKED (malformed or oversized input, no decision possible; first problem only): `BAD_INPUT`, `SIZE_CAP`, `DIFF_UNPARSABLE`, `PACKAGE_TOO_LARGE`, `INTERNAL_ERROR`. Caps: 512 test records, 128 receipts and paths, 128 declared limits, 500 characters per text, 64 review iterations, 512 KiB canonical package, 8 MiB diff (`worker_gate.MAX_DIFF_BYTES`). Texts may not contain control characters; a path may not contain a backtick or a newline (BLOCKED for `changed_paths`, `PATH_HAZARD` for a path found in the diff).

REFUSED (all reasons listed, no package):

| Code | When |
|---|---|
| `STALE_EVIDENCE` | an item names another head (or, for the run record, none); the detail starts with the item: `test:<id>`, `receipt:<id>`, `review_results.final_head`, `review_results.iterations[-1].head`, `isolation_proof.candidate_head`, `patch_origin_share.candidate_head` |
| `DIFF_HASH_MISMATCH` | `diff_bytes` do not hash to `diff_sha256`, or the run record has no or another diff digest (one reason per cause; the same code and detail is never listed twice) |
| `PATHS_UNDERSTATED` / `PATHS_EXTRA` | the parsed diff changes paths missing from `changed_paths` / `changed_paths` lists paths the diff does not change |
| `PATH_HAZARD`, `DIFF_SPECIAL_MODE`, `EMPTY_DIFF` | `worker_gate.path_hazards` found a hazard; a link, submodule or non-standard mode; the diff names no path |
| `REVIEW_NOT_CLEAN`, `REVIEW_INCONSISTENT`, `REVIEW_STORY_MISMATCH` | verdict is not CLEAN (reason codes listed); a CLEAN claim without a CLEAN last iteration, `findings == []`, `truncated` false, no reasons, `iteration_count == len(iterations)` and complete declared coverage; another or no story |
| `REVIEW_REPLAYED` | `replayed` is True and `replay_store_verified` is not |
| `TEST_FAILED`, `MISSING_REQUIRED_TEST`, `NO_PASS_EVIDENCE`, `NOT_RUN_UNACKNOWLEDGED` | any FAIL; a required id without a record; no record is PASS (also when every test is NOT_RUN and acknowledged); a required NOT_RUN or SKIPPED test without an `allow_not_run` reason |
| `RECEIPT_NOT_PASS` | a receipt result missing or other than PASS |
| `SHARE_NOT_ACCEPTED` | run record verdict is not ACCEPTED, `applied` is false or `partial` is true |
| `PROOF_DISHONEST`, `ISOLATION_FAILED` | `worker_gate.proof_is_honest` is False; a property is FAILED |
| `SECRET_IN_EVIDENCE` | `receipt_builder._refuse_secrets` (shared `tools/uc/secret_patterns.py`) matches free text; the detail names the section only. The scan runs first and ends the decision, so no other detail can echo secret-like input |

A diff that cannot be parsed is BLOCKED, unless another refusal exists already; then both are listed (REFUSED wins, as in the worker gate).

## What the package holds

`schema`, `story_id`, `head`, `base_head`, `valid_for_head` (explicitly equal to `head`), `created_at` (= `now`), `diff` (sha256, bytes, sorted changed paths, renames), `tests` (required ids, sorted records, `passed`, `failed`, `not_run`, counts), top-level `not_run` (a separate copy) (status, required, reason, acknowledged reason; never counted as passed), `allow_not_run`, `review` (verdict, final head, iteration count, replayed flags, declared coverage, last iteration, result digest), `receipts`, `isolation` (all properties with status and detail, proof digest), `patch_origin_share` (counts, fractions, overrides, record digest) or null, `evidence_digests`, `declared_limits` (verbatim) and `derived_limits` (no provenance, diff bytes absent, every not-run test, every isolation property that is not VERIFIED, replay, missing receipts or origin record).

## Secret scan scope

Only free text is scanned: test and acknowledgement reasons, review reasons and iteration ids and reasons, receipt type and result, isolation details, run-record verdict and overrides, declared limits. Identifiers (story id, test ids, receipt ids, heads, digests, paths, property names) are validated by shape and are not scanned, because the shared pattern matches ordinary names such as `secret_patterns` or `test_token_validation`. The diff is never in the package.

`package_sha256 = sha256(contracts.canonical_bytes(package))`. It is deterministic for the same inputs and the same `now`; lists are sorted, so input order does not matter. `now` is part of the package, so the same facts at another time give another digest.

## Invalidation

The package is valid for `valid_for_head` only. `verify_package_current` returns `HEAD_CHANGED` and `DIFF_CHANGED` for a new commit, `PACKAGE_INCONSISTENT` when `valid_for_head` or any embedded head (review final head and last iteration head, isolation proof, PASS/FAIL test records, receipts, run record) differs from `head` or is missing, `PACKAGE_TAMPERED` when the package does not hash to the required `package_sha256`, `BAD_INPUT` when `package_sha256` or the current values are malformed, and `PACKAGE_MALFORMED` for a foreign object. GPT-PM approval stays bound to HEAD by the hook; this function is the same rule for the package.

## Scope note rendering

`render_scope_note` lists head, base, diff digest, changed paths, review, PASS records, NOT_RUN items (with "No claim is made for these items"), receipts, isolation properties, origin share, declared and derived limits and digests. Evidence-derived text is escaped (`escape_markdown`); only validated hex values sit in code spans. It says "PASS record" for a recorded PASS and never uses a pass claim for NOT_RUN or SKIPPED items.

## Known gaps

* Evidence is not signed and its provenance is not checked; a caller can still hand over consistent but false facts. The review result and run record are hashed, not verified.
* The review result does not carry the reviewed paths digest (`ReviewLoopResult.to_dict` has none), so the package cannot prove that the review covered exactly this diff beyond head equality. Left to a later U5-4 follow-up.
* `replayed` is refused by default because the dict does not say whether the store facts were checked; the caller confirms with `replay_store_verified`.
* A secret in an identifier, a path name or the diff text is not caught here (see Secret scan scope; PM Bridge redacts the diff it sends).
* The required test list comes from the caller; the builder cannot know whether it is complete.
* Receipts are accepted as id, head, digest and result; signatures are not verified here.
* No concrete wiring to the pipeline store, PM Bridge or `gate.py` is provided.
