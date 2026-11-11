# U6-2 Measured savings report

Result: **NOT_RUN.** No token or cost saving is reported, because the inputs that would make it measurable do not exist or do not verify. Nothing in this document is estimated.

Tool: `tools/uc/savings_report.py` (function `build_savings_report`, CLI `python -s -m tools.uc.savings_report`). Tests: `tests/vst/test_u6_savings_report.py` (written, **NOT_RUN**: pytest is forbidden by the operator for this sprint). It reuses `tools/uc/token_baseline.py` (manifest hash check, role attribution, token counting) and `tools/uc/measure.py` (optional per-task local-first verdict); it does not recount tokens itself.

## Rule

A number appears only when it comes from files that exist and whose SHA-256 matches the manifest that pins them. Token fields (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`) are always reported separately. Cost needs a price table file with a stated source. A role is compared only when the models used before and after are the same set.

## Inputs checked (2026-11-11)

| Input | Path | Found | Verified |
|---|---|---|---|
| U1-1 baseline manifest | `docs/sdlc/evidence/u1-1-baseline-manifest.json` | yes (1 session `557da842-4774-4321-afaa-c4fe8ecf9f85`, main transcript plus 15 sub-agent transcripts with meta and prefix files) | file read; pinned transcripts do **not** verify, see below |
| U1-1 baseline report | `docs/sdlc/evidence/u1-1-baseline-report.json` | yes (status MEASURED, recorded earlier from that manifest) | not re-derivable now, see below |
| Baseline transcripts | `C:/Users/koros/.claude/projects/D--Repo/557da842-4774-4321-afaa-c4fe8ecf9f85.jsonl` and `.../557da842-4774-4321-afaa-c4fe8ecf9f85/subagents/` | main transcript present, now 6773135 bytes; the manifest pins 6767280 bytes | **HASH_MISMATCH** |
| "Current" (after) manifest | none | **not found**: no file in the repository or under `C:/Users/koros/.claude` is a manifest of a residual-only run | - |
| Paired-task list (`task_id`, `before_session`, `after_session`) | none | **not found** | - |
| Price table with source | none | **not found** | - |

Searches made: Glob of the repository for `*baseline*`, `*measure*`, `*paired*` (only the two U1-1 evidence files above, the scripts and their tests matched); `git ls-files` filtered for `paired`, `current-manifest`, `price` (nothing); a search under `C:/Users/koros/.claude` (depth 2) for `*price*` and `*paired*` (nothing). U1 recorded the same state: the U1-8 row of `PROJECT_PLAN.md` (line 111) says that no real paired measurement exists, that the baseline session set was not chosen, and that the residual-only run does not exist.

## Commands run and output (abridged)

Interpreter `C:/Python314/python.exe -s`, `PYTHONPATH` = the repository root, run from the repository root. Output files went to the session scratchpad, not into the repository. The only abridgement: the scratchpad directory (`C:/Users/koros/AppData/Local/Temp/claude/a1d92f0a4c8fdec9/7c226845-5437-4ece-b7f8-718cbe5ae8c8/scratchpad/u6_2`) is written `$S`, and `$P` stands for `C:/Users/koros/.claude/projects/D--Repo`. Runs 2 and 3 were repeated after the remediation batch (new refusal codes, atomic output); the output was identical.

1. Existing U1-1 tool on the baseline manifest:

```
python -s tools/uc/token_baseline.py report --manifest docs/sdlc/evidence/u1-1-baseline-manifest.json --project-dir C:/Users/koros/.claude/projects/D--Repo
{"detail": "557da842-4774-4321-afaa-c4fe8ecf9f85.jsonl", "reason": "HASH_MISMATCH", "status": "NOT_RUN"}
```

Exit code 2. The main transcript of the baseline session changed after the manifest pinned it (the session file is 5855 bytes larger than the pinned 6767280 bytes; file modification time Nov 9 15:04). Under the rule, the old baseline numbers in `u1-1-baseline-report.json` can no longer be confirmed from the files and must not be used as a current baseline.

2. This report generator, no current manifest and no paired-task file:

```
python -s -m tools.uc.savings_report --baseline-manifest docs/sdlc/evidence/u1-1-baseline-manifest.json --current-manifest $S/none-current.json --project-dir $P --paired-tasks $S/none-pairs.json --out-json $S/A.json --out-md $S/A.md
{"out_json": "$S\\A.json", "out_md": "$S\\A.md", "refusals": ["MISSING_CURRENT"], "status": "NOT_RUN"}
```

(`$S/none-current.json` and `$S/none-pairs.json` do not exist.)

Exit code 2.

3. Same, with the baseline manifest given as the current manifest (to show the verification step):

```
python -s -m tools.uc.savings_report --baseline-manifest docs/sdlc/evidence/u1-1-baseline-manifest.json --current-manifest docs/sdlc/evidence/u1-1-baseline-manifest.json --project-dir $P --paired-tasks $S/none-pairs.json --out-json $S/B.json --out-md $S/B.md
{"out_json": "$S\\B.json", "out_md": "$S\\B.md", "refusals": ["HASH_MISMATCH"], "status": "NOT_RUN"}
```

Exit code 2. The generated report body: status NOT_RUN, refusal `HASH_MISMATCH` (baseline manifest, `557da842-4774-4321-afaa-c4fe8ecf9f85.jsonl`), "No numbers are shown: nothing was measured", `roles` empty. Cost: NOT_RUN (`NO_MEASUREMENT`).

## Savings figures

| Item | Status |
|---|---|
| Tokens per role against the U1-1 baseline | NOT_RUN: baseline transcripts do not match their pinned hashes (HASH_MISMATCH); no after-side manifest; no paired tasks |
| Cost per role | NOT_RUN: no price table with a source; also no measured tokens |
| Local-first verdicts per role | NOT_RUN: no paired run and no role result |

## What the operator must provide

1. A baseline that verifies. Either restore the exact baseline transcript bytes, or choose the baseline sessions again and rebuild the manifest with `python -s tools/uc/token_baseline.py build-manifest --project-dir <dir> --sessions <ids> --out <file>` once the sessions are closed (a running or resumed session keeps growing and invalidates its own pin).
2. The "after" side: for each paired task, a second closed session in which the entry command ran first and the model handled only the residual slice, pinned by its own manifest (same builder). The two sessions of one task must cover the same story or diff, and must contain only that task's work.
3. A paired-task file, a JSON list of `{"task_id": "...", "before_session": "<id in the baseline manifest>", "after_session": "<id in the current manifest>", "role_result": "<optional path to the entry command's role result>"}`.
4. For cost only: a price table JSON (`source`, `currency`, `unit_tokens`, per-model prices for the four token fields) from a source the operator names. No price is built into the tool.
5. The same model for the same role on both sides; a role with a different or unrecorded model is refused (`MODEL_MISMATCH` / `MODEL_UNKNOWN`).

Then run:

```
python -s -m tools.uc.savings_report --baseline-manifest <file> --current-manifest <file> --project-dir <dir> --paired-tasks <file.json> [--price-table <file.json>] --out-json <file> --out-md <file>
```

and replace this document with the generated markdown plus the command line and its output.

## Limits that apply to any future measurement

- The number of paired tasks is stated in the report; with a handful of pairs there is no variance estimate and no statistical claim.
- Same-model requirement as above.
- Sign convention: `delta` = after - before (negative means fewer tokens or lower cost after); `saving` = before - after, per field (positive means fewer). Neither is summed across fields.
- A role paired in one task but present on one side only in another is refused as a whole (`ROLE_ONE_SIDED`).
- Cache fields depend on cache warmth and session order; they are reported separately and never merged with the other fields into one saving figure.
- The unit of pairing is a whole session; unrelated work inside a session is counted.
- Roles present on one side only are listed as unpaired and carry no numbers.
- Cost covers only roles with exactly one model that has a price row.
