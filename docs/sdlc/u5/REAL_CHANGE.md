# U5-7: one small real change through the pipeline

Outcome (measured, not production-ready): **the change was not applied.** `apply_proposals` returned BLOCKED twice (stage VALIDATE, then stage WORKTREE_CHECK), so the review loop and the final package were NOT_RUN. Nothing in the target worktree was modified by the pipeline. This document reports what was measured; it makes no claim that the pipeline is ready for production use.

Driver: `tools/vst/u5_real_change_driver.py` (reproducible, runs no test). Evidence of the run (not committed, in the session scratchpad): `C:/Users/koros/AppData/Local/Temp/claude/a1d92f0a4c8fdec9/7c226845-5437-4ece-b7f8-718cbe5ae8c8/scratchpad/u5_7/` (`evidence.json`, `g6_patch_v1_full.json`, `g6_patch_v1_narrow.json`).

Setup: target worktree `D:/tmp/scratch_worktrees/vst-u5-real`, branch `u5-7-real-change`, base head `5166f06650687493b6c1ca7c05d40aa1015c53d5` (U5-1..U5-6 code), clean tree before the run. AEVE: read-only checkout `D:/tmp/scratch_worktrees/aeve-real` at `8a9f6c1a684e03eac252b285a96a11d363dbc9e6`, which is the pin in `catalog/role_table.json`. Interpreter `C:/Python314/python.exe -s`. Run time 2026-11-11.

## The change (as proposed; not applied)

File `tests/uc/test_token_baseline.py`, recipe `trailing-whitespace`, scope declared as exactly this file. Four whitespace-only lines hold four spaces at the end (lines 362, 365, 376, 380 of the base file); the proposal turns them into empty lines (two hunks, `@@ -359,10 +359,10 @@` and `@@ -373,11 +373,11 @@`). No code token changes. Why this file: a read-only scan of `git ls-files` for `.py` files found it as the only tracked Python file with trailing-whitespace lines (the scan only counted trailing spaces/tabs; AEVE itself proposes patches for 14 files, mostly final-newline cases the scan did not look for). The change touches a test file; that test was not run.

## Authoring path

AEVE proposal, no model: `aeve.repair.patch.propose_patches_report` on a real `aeve.intelligence.snapshot.capture_snapshot` of the target worktree (tree clean, snapshot COMPLETE). `llm_calls` = 0 and `executed_project_code` = false in both documents. No model wrote or edited the change. A person/agent chose the file and wrote the driver; AEVE produced the diff text.

Two documents were produced from the same snapshot:

| Document | Content | `report_sha256` |
|---|---|---|
| full | 59 proposals over the whole snapshot, `status: PARTIAL` (three `.mjs` files LANGUAGE_NOT_INDEXED), 14 files with a changed patch | `bb3fb28035e62f8483d2622dd695cc4d6b2ad15517e3341366f834882987f14c` |
| narrow | the same snapshot with `source_bytes` cut to the declared file: 1 proposal, no `status` | `672fe287981249c7df5ebfea19dffef871b0f5575fe6d0865b79150e8e7b7804` |

The narrow document is an input selection by the caller, made after the full document was BLOCKED. It does not bypass any gate; both documents went through the same `apply_proposals`.

## Isolation stated

Windows-local, no WSL, no OS sandbox, no process containment (operator decision 2026-11-08). `IsolationContext`: `worktree_root` = the target worktree, `main_checkout_root` = `D:/Repo/Virtual_scrum_team`, `network_requested` = False, `pinned_base_head` = `worktree_head` = base head, real `os.lstat` / `os.path.realpath`. `protected_paths` = default (empty caller list), `allowed_paths` = the one file, `manifest_sha256` = sha256 of `{"task":"U5-7","allowed_paths":[file],"base_head":head}` computed by the driver (no real manifest exists for this run, so it is caller-made).

The `ApplyResult` carries no isolation proof when it stops before the gate result is stored (`gate: null`). To read the statuses, the driver replicated the PRESCREEN call of `apply_proposals` (same arguments, informational, writes nothing; verdict ACCEPTED, reason `DIFFGATE_PASS`, claimed diff sha256 `2b510b88d72ca1a1c6634ee953641b7a1ec2473286aa25eb29ff43999edb43c7`). Its isolation proof, verbatim statuses:

| Property | Status |
|---|---|
| worktree_separate_from_main_checkout | VERIFIED |
| base_commit_pinned | CALLER_ASSERTED |
| worktree_head_matches_candidate | CALLER_ASSERTED (placeholder candidate head, git not read) |
| network_flag_not_requested | CALLER_ASSERTED (enforcement not verified) |
| paths_normalized | VERIFIED |
| link_and_reparse_point_check_on_changed_paths | VERIFIED (3 components of 1 path inspected at check time) |
| os_sandbox, process_containment, network_enforcement, worker_identity_separation, writes_outside_worktree, resource_limits, short_name_aliases_on_disk, check_time_vs_use_time, rename_and_symlink_evidence_completeness | NOT_VERIFIED |

## Stage outcomes (verbatim)

| Stage | Outcome |
|---|---|
| 1 AEVE proposal | produced both documents; snapshot 5.6 s, proposals 10.9 s (full) |
| 2a `apply_proposals`, full document | verdict BLOCKED, stage VALIDATE, worktree_state UNCHANGED, reason `PROPOSAL_REDACTED`: "diff for 'tests/vst/test_s2_contract_gate.py' contains a redaction marker; it cannot match the file" (0.002 s) |
| 2b `apply_proposals`, narrow document | verdict BLOCKED, stage WORKTREE_CHECK, worktree_state UNCHANGED, reason `UNTRUSTED_GIT_CONFIG`: ".gitattributes sets filter, eol, text, ident or working-tree-encoding" (0.074 s). Cause: the repository's own `.gitattributes` lines 2-3 (`* text=auto`, `*.py text eol=lf`). |
| 3 review loop | NOT_RUN: apply was not ACCEPTED, so there is no candidate change to review |
| 4 final package | NOT_RUN: apply was not ACCEPTED (no diff, no review result of a candidate). Had the earlier stages passed, the expected outcome was REFUSED (`NO_PASS_EVIDENCE`: all required tests NOT_RUN, reason `operator ban on running tests`), which is a code expectation, not a measurement |
| tests | NOT_RUN (operator ban on running tests): `tests/uc/test_token_baseline.py::test_compute_empty_subagent_transcript_is_not_run`, `...::test_compute_unexpected_transcript_after_manifest_created_is_not_run` (the two tests next to the proposed lines) |

The block was recorded as the outcome and not worked around: `.gitattributes` was not edited, the scan was not weakened, and no patch was applied by hand.

Extra real measurement (not a review of the change): the driver sent one `purpose: receipt` request for roles `repo-recon` and `git-worktree-ops` on the unchanged file at base head through `tools/uc/router.review` and the real AEVE CLI (29.4 s). Result `uc.role-result.v1`, exit code 3, both roles PARTIAL: `g1.repository-snapshot` COMPLETE, `g4.worktree-facts` COMPLETE, `g5.layering-shapes` PARTIAL (uncovered: `arc_dynamic_call_sites`, `arc_layer_policy_not_provided`, `arc_no_product_python_file_in_scope`, `graph_uncovered`, `unresolved_or_external_imports`, `aeve-partial`). So the real review path works end to end here, and these roles would not be CLEAN for this file when `g5.layering-shapes` is declared. The first attempt failed (see friction 3 and 4 below) until the AEVE state directory was shortened.

## Real, simulated, NOT_RUN

- Real: AEVE snapshot and `g6.patch.v1` generation; `capture_snapshot`; `apply_proposals` validation, base check and git config/attribute scan against the real worktree; the U5-1 gate prescreen with real `lstat`/`realpath`; one real AEVE review through router and adapter.
- Simulated: nothing in the run. The manifest digest is a caller-made digest.
- NOT_RUN: all tests; stage 3 loop (`run_review_loop`); stage 4 `build_final_package`; the MATERIALIZE stage of `apply_proposals`; the git `apply --cached` / `commit-tree` build stage on a real worktree (stopped earlier); the loop's `verify_report` path.

## Defects and friction found (nothing was fixed in U5 modules)

1. **Structural conflict, `tools/vst/patch_proposals.py:658-662` (`_scan_attribute_text`, called by `_scan_attributes` at line 665) versus `.gitattributes:2-3`.** AEVE's patch recipes only cover `.py` sources (`aeve/repair/patch.py` skips other suffixes); this repository pins `*.py text eol=lf`; U5-2 refuses any `eol`/`text` attribute. So no AEVE patch can be applied in this repository by the current U5-2. Fixing it means a design decision (read the effective attributes with `git check-attr` instead of a text scan, or accept `text eol=lf` when the file has no CR), not a local patch. Not changed in U5. **Status 2026-11-11: FIXED in code (task for register item R-27).** The operator chose to allow the safe line-ending attributes (`text`, `eol`, `-text`, `text=auto`) and keep blocking `filter`, `ident`, `working-tree-encoding`, `crlf`, `export-subst`, `diff=`/`merge=` drivers; the scan stays a text scan, `git check-attr` is not used. See PATCH_PROPOSALS.md, step on the trusted repository. The U5-7 driver has not been re-run: the real AEVE-driven change is still NOT_RUN, and the new tests are NOT_RUN (operator ban).
2. **`patch_proposals.py:221` (inside document validation): all-or-nothing.** One diff with a redaction marker (any file, here `tests/vst/test_s2_contract_gate.py`) blocks the whole document although the declared scope is another file. There is no per-file selection; the caller has to narrow the AEVE snapshot first, as the driver did.
3. **`tools/uc/adapter.py:226` versus `:242-243`: wrong reason on an AEVE ERROR answer.** The required-key check runs before the status check, so AEVE's `status: ERROR, reason: REVIEW_LEDGER_WRITE_FAILED, ledger_persisted: false` (no `iteration_id`) is reported as `AEVE_CONTRACT_VIOLATION: response lacks iteration_id`. The real cause had to be found by calling the AEVE CLI directly.
4. **State-directory path length.** With a deep state dir (the session scratchpad) the AEVE ledger file path exceeds the Windows 260-character limit and `os.replace` in AEVE `review_store._write` fails with WinError 3. The router/adapter do not check the path length. The driver takes a short `--state-dir` (`D:/tmp/u5-7-aeve-state` was used).
5. **Receipt needs a clean tree, apply leaves a dirty tree (static finding, not exercised because apply was blocked).** `tools/uc/router.py:368,371` and `adapter.py:239` make `purpose: receipt` require a clean tree, while `apply_proposals` writes an unstaged modification and makes no commit (PATCH_PROPOSALS.md, MATERIALIZE). Also its `candidate_head` is an identifier that cannot be resolved after the call. So an ACCEPTED candidate has no commit that a receipt review can name, and `build_final_package` (one head for review, isolation proof and run record) would find different heads. A commit step between apply and review is missing from the pipeline.
6. **`review_loop.verify_report` has no real implementation (static finding).** The `uc.role-result.v1` contract carries no signature and nothing in `tools/` signs router results; the E2E harness used an invented HMAC. A real loop needs a caller predicate; the driver's stage 3 passes one that returns False (unverified), which would make every real report `SIGNATURE_UNVERIFIED`.
7. **`ApplyResult.gate` is null for a BLOCKED result after a passed prescreen.** The isolation proof of the prescreen is lost; the driver had to replicate the call to read it.
8. **AEVE snapshot of an untracked file.** `capture_snapshot` refuses a worktree that holds any untracked file (`DIRTY_WORKTREE_REQUIRES_EXPLICIT_OPT_IN`), including the driver itself. The driver therefore runs from a copy outside the worktree, or with `--allow-dirty-snapshot` (then the snapshot and its documents are PARTIAL).

## Timings (one run, wall clock)

Snapshot 5.6 s; both proposal documents 10.9 s; `apply_proposals` 0.002 s (full) and 0.074 s (narrow); one real AEVE review 29.4 s; whole driver 47.2 s.

## Reproduce

Use a clean worktree at the base head, `PYTHONPATH=<target worktree>;<aeve>/src`, and run the driver from a copy outside the worktree:
`C:/Python314/python.exe -s u5_real_change_driver.py --worktree <target> --aeve <aeve> --target-file tests/uc/test_token_baseline.py --out <dir> --state-dir <short dir>`. A second run on a worktree where the change was applied would see a dirty file. The script never starts a test runner.

## Limits

This is one run of one tiny change, on one machine. The outcome is measured, not production-ready. Stages 3 and 4 and the write stage of U5-2 stay unproven in a real run. Findings 5 and 6 come from reading code, not from a run. All tests are NOT_RUN by operator ban.
