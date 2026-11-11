# U5-5: final package builder for GPT-PM

Module: `tools/vst/final_package.py`. Tests: `tests/vst/test_u5_final_package.py` (written, **NOT_RUN**: running tests is forbidden by the operator for this sprint; nothing was executed, only syntax-parsed).

Acceptance (PROJECT_PLAN U5-5): builds the package with the exact diff, test evidence, review results and head identity; refuses stale evidence; a new commit invalidates it.

## What it is

A pure function. It reads no git, no file, no network and no clock and calls no model: every fact is an argument, `now` included. It checks that the facts agree with each other and with ONE head. It does not check who produced them (all evidence is caller-supplied and unsigned here).

Relation to the global GPT-PM flow: the diff itself is still delivered by PM Bridge (`review.js --base <base_head> --head <head>`, which redacts secrets); this package is the evidence bundle that travels with it. It therefore holds the diff sha256, byte count and path list, never the diff bytes. The reviewer can recompute the digest of the diff PM Bridge shows and compare.

## Public API

| Name | Purpose |
|---|---|
| `build_final_package(*, story_id, base_head, head, diff_bytes, diff_sha256, changed_paths, test_evidence, review_results, receipts, isolation_proof, patch_origin_share, now, allow_not_run=None, declared_limits=(), replay_store_verified=False) -> PackageResult` | decide and build; never raises for input problems, never mutates inputs (deep copies) |
| `PackageResult(verdict, reasons, package, package_sha256)` | verdict READY / REFUSED / BLOCKED; `reasons` are `(code, ascii detail)`; `package` and digest only for READY |
| `verify_package_current(package, current_head, current_diff_sha256, *, package_sha256=None) -> (ok, reasons)` | a new commit (head or diff differs) makes the package not current; also checks that the package is coherent and, when given, re-hashes it |
| `render_scope_note(package) -> str` | deterministic English Markdown from a package |

## Inputs

* `diff_sha256`: the recorded diff digest (for example from the gate evidence). `diff_bytes` must hash to it.
* `test_evidence`: records `{test_id, status, evidence_sha256, head}` plus optional `required` (default True) and `reason`. Status is PASS, FAIL, NOT_RUN or SKIPPED. PASS and FAIL need a digest and the head they were produced at; NOT_RUN and SKIPPED may carry null for both.
* `allow_not_run`: `{test_id: reason}`; the explicit, operator-visible acknowledgement that a NOT_RUN or SKIPPED required test may stay unrun. An id that is not NOT_RUN or SKIPPED is BLOCKED.
* `review_results`: `ReviewLoopResult.to_dict()` (U5-4). Only the verdict, reasons, `final_head`, `replayed`, `declared_coverage`, `story_id` and the last iteration are read; the whole document is hashed (`result_sha256`).
* `receipts`: `{receipt_id, head, receipt_sha256}` plus optional `receipt_type` and `result` (a result other than PASS is refused). The head is the receipt `candidate_head`, as in `tools/vst/gate.py`.
* `isolation_proof`: `worker_gate.build_isolation_proof` output. Its `candidate_head` is stored as `ascii(head)`; both forms are accepted.
* `patch_origin_share`: a `patch_proposals.build_run_record` dict, or None (listed as a derived limit).
* `declared_limits`: strings copied verbatim into the package.
* `replay_store_verified`: set True only by a caller that checked a replayed review result against the pipeline store (see below).

## Verdicts

BLOCKED (malformed or oversized input, no decision possible; first problem only): `BAD_INPUT`, `SIZE_CAP`, `DIFF_UNPARSABLE`, `PACKAGE_TOO_LARGE`, `INTERNAL_ERROR`. Caps: 512 test records, 128 receipts and paths, 128 declared limits, 500 characters per text, 64 review iterations, 512 KiB canonical package, 8 MiB diff (`worker_gate.MAX_DIFF_BYTES`). Texts may not contain control characters.

REFUSED (all reasons listed, no package):

| Code | When |
|---|---|
| `STALE_EVIDENCE` | an item names another head; the detail starts with the item: `test:<id>`, `receipt:<id>`, `review_results.final_head`, `review_results.iterations[-1].head`, `isolation_proof.candidate_head`, `patch_origin_share.candidate_head` |
| `DIFF_HASH_MISMATCH` | `diff_bytes` do not hash to `diff_sha256`, or the run record names another diff digest |
| `PATHS_UNDERSTATED` / `PATHS_EXTRA` | the parsed diff changes paths missing from `changed_paths` / `changed_paths` lists paths the diff does not change |
| `PATH_HAZARD`, `DIFF_SPECIAL_MODE`, `EMPTY_DIFF` | `worker_gate.path_hazards` found a hazard; a link, submodule or non-standard mode; the diff names no path |
| `REVIEW_NOT_CLEAN`, `REVIEW_INCONSISTENT`, `REVIEW_STORY_MISMATCH` | verdict is not CLEAN (reason codes listed); a CLEAN claim without a CLEAN last iteration, no findings, no reasons and complete declared coverage; another story |
| `REVIEW_REPLAYED` | `replayed` is True and `replay_store_verified` is not |
| `TEST_FAILED`, `NO_TEST_EVIDENCE`, `NOT_RUN_UNACKNOWLEDGED` | any FAIL; no record at all; a required NOT_RUN or SKIPPED test without an `allow_not_run` reason |
| `RECEIPT_NOT_PASS` | a receipt result other than PASS |
| `PROOF_DISHONEST`, `ISOLATION_FAILED` | `worker_gate.proof_is_honest` is False; a property is FAILED |
| `SECRET_IN_EVIDENCE` | `receipt_builder._refuse_secrets` (shared `tools/uc/secret_patterns.py`) matches evidence text; the detail names the section |

A diff that cannot be parsed is BLOCKED, unless another refusal exists already; then both are listed (REFUSED wins, as in the worker gate).

## What the package holds

`schema`, `story_id`, `head`, `base_head`, `valid_for_head` (explicitly equal to `head`), `created_at` (= `now`), `diff` (sha256, bytes, sorted changed paths, renames), `tests` (sorted records, `passed`, `failed`, `not_run`, counts), top-level `not_run` (status, required, reason, acknowledged reason; never counted as passed), `allow_not_run`, `review` (verdict, final head, iteration count, replayed flags, declared coverage, last iteration, result digest), `receipts`, `isolation` (all properties with status and detail, proof digest), `patch_origin_share` (counts, fractions, overrides, record digest) or null, `evidence_digests`, `declared_limits` (verbatim) and `derived_limits` (no provenance, diff bytes absent, every not-run test, every isolation property that is not VERIFIED, replay, missing receipts or origin record, no PASS evidence).

`package_sha256 = sha256(contracts.canonical_bytes(package))`. It is deterministic for the same inputs and the same `now`; lists are sorted, so input order does not matter. `now` is part of the package, so the same facts at another time give another digest.

## Invalidation

The package is valid for `valid_for_head` only. `verify_package_current` returns `HEAD_CHANGED` and `DIFF_CHANGED` for a new commit, `PACKAGE_INCONSISTENT` when `valid_for_head` or any embedded head differs from `head`, `PACKAGE_TAMPERED` when `package_sha256` is given and does not match, and `PACKAGE_MALFORMED` for a foreign object. GPT-PM approval stays bound to HEAD by the hook; this function is the same rule for the package.

## Scope note rendering

`render_scope_note` lists head, base, diff digest, changed paths, review, PASS records, NOT_RUN items (with "No claim is made for these items"), receipts, isolation properties, origin share, declared and derived limits and digests. It says "PASS record" for a recorded PASS and never uses a pass claim for NOT_RUN or SKIPPED items.

## Known gaps

* Evidence is not signed and its provenance is not checked; a caller can still hand over consistent but false facts. The review result and run record are hashed, not verified.
* The review result does not carry the reviewed paths digest (`ReviewLoopResult.to_dict` has none), so the package cannot prove that the review covered exactly this diff beyond head equality.
* `replayed` is refused by default because the dict does not say whether the store facts were checked; the caller confirms with `replay_store_verified`.
* The shared secret pattern also matches ordinary identifiers (`secret_patterns`, `token_validation`). Paths are therefore not scanned and the diff is never scanned (it is not in the package); a secret in a path name or in the diff text is not caught here (PM Bridge redacts the diff it sends).
* Receipts are accepted as id, head, digest and result; signatures are not verified here.
* No concrete wiring to the pipeline store, PM Bridge or `gate.py` is provided.
