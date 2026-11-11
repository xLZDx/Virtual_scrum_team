# U6-2 Measured savings report

Result: **NOT_RUN.** No token or cost saving is reported, because the inputs that would make it measurable do not exist or do not verify. Nothing in this document is estimated.

Tool: `tools/uc/savings_report.py` (function `build_savings_report`, CLI `python -s -m tools.uc.savings_report`). Tests: `tests/vst/test_u6_savings_report.py` (written, **NOT_RUN**: pytest is forbidden by the operator for this sprint). It reuses `tools/uc/token_baseline.py` (manifest hash check, role attribution, token counting) and `tools/uc/measure.py` (optional per-task local-first verdict); it does not recount tokens itself.

## Rule

A number appears only when it comes from files that exist and whose SHA-256 matches the manifest that pins them. Token fields (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`) are always reported separately. Cost needs a price table file with a stated source. A role is compared only when the models used before and after are the same set.

## Inputs checked (2026-11-11, first check; see "Baseline rebuilt" below for the new baseline)

| Input | Path | Found | Verified |
|---|---|---|---|
| U1-1 baseline manifest (old, superseded) | `docs/sdlc/evidence/u1-1-baseline-manifest.json` | yes (1 session `557da842-4774-4321-afaa-c4fe8ecf9f85`, main transcript plus 15 sub-agent transcripts with meta and prefix files) | file read; pinned transcripts do **not** verify, see below |
| U1-1 baseline report | `docs/sdlc/evidence/u1-1-baseline-report.json` | yes (status MEASURED, recorded earlier from that manifest) | not re-derivable now, see below |
| Baseline transcripts | `C:/Users/koros/.claude/projects/D--Repo/557da842-4774-4321-afaa-c4fe8ecf9f85.jsonl` and `.../557da842-4774-4321-afaa-c4fe8ecf9f85/subagents/` | main transcript present, now 6773135 bytes; the manifest pins 6767280 bytes | **HASH_MISMATCH** |
| "Current" (after) manifest | none | **not found**: no file in the repository or under `C:/Users/koros/.claude` is a manifest of a residual-only run | - |
| Paired-task list (`task_id`, `before_session`, `after_session`) | none | **not found** | - |
| Price table with source | none | **not found** | - |

Searches made: Glob of the repository for `*baseline*`, `*measure*`, `*paired*` (only the two U1-1 evidence files above, the scripts and their tests matched); `git ls-files` filtered for `paired`, `current-manifest`, `price` (nothing); a search under `C:/Users/koros/.claude` (depth 2) for `*price*` and `*paired*` (nothing). U1 recorded the same state: the U1-8 row of `PROJECT_PLAN.md` (line 111) says that no real paired measurement exists, that the baseline session set was not chosen, and that the residual-only run does not exist.

## Baseline rebuilt on a closed session (U6-5, 2026-11-11)

The operator chose to rebuild the baseline on closed sessions. The pinned session `557da842-4774-4321-afaa-c4fe8ecf9f85` (the U1-1 baseline) is closed now: its main transcript was last written 2026-11-09 15:04 (about 45 hours before this check; threshold 24 hours), every file under its `subagents/` directory is at least as old, and no running process has the session id on its command line. Its pinned bytes changed once while it was still open, so the old manifest cannot be restored; a new manifest pins the current, closed bytes.

| Item | Value |
|---|---|
| New baseline manifest | `docs/sdlc/evidence/u6-5-baseline-manifest.json` (built by `tools/uc/token_baseline.py build-manifest`; 1 session, 61 files: main transcript 6773135 bytes, sha256 `0088c201c752f194796af5f4ad67e81a957738703b2cbe4df9a06fcdb19482d6`, plus 20 sub-agent transcripts with their meta and prefix files) |
| Hashed copy of the pinned transcripts | `D:/tmp/u6-5-baseline-transcripts/` (same relative layout as the project directory; copied, the originals were not moved or changed) |
| Verification | `python -s tools/uc/token_baseline.py report --manifest docs/sdlc/evidence/u6-5-baseline-manifest.json --project-dir <dir>` returned byte-identical output (`"status": "MEASURED"`, six roles) for `<dir>` = the original project directory and for `<dir>` = the copy; exit 0 both times |
| Old manifest `u1-1-baseline-manifest.json` | kept as history; it still fails `HASH_MISMATCH` and is superseded by the new one |

The copy is outside the repository on purpose: the repository is public and the transcripts hold the whole private conversation. Only the manifest (paths, sizes, hashes) is committed. Putting the copy in the repository needs an operator decision; note also that `.gitattributes` normalises line endings of `*.json` and `text=auto` files, which would change the copied bytes and break the hashes unless the files are marked `-text`.

Baseline roles measured from the verified files (tokens per field, never summed): orchestrator 193 messages, implementation-engineer 140, functional-test-reviewer 28, claude-code-guide 6, silent-failure-hunter 5, python-reviewer 3. The values are in the report output of the command above; they equal the earlier U1-1 report except one more orchestrator message (193 instead of 192), and are not a saving.

### Why there is still no savings figure

- No paired before/after session exists. Of the closed sessions under `C:/Users/koros/.claude/projects/D--Repo` (397 main transcripts at the check, 346 of them at least 24 hours old) the only ones with sub-agents that worked in this repository are `76e068db-...`, `d4e3a3a2-...`, `b6f841c8-...`, `8dd8dfe9-...`, `ffe133a0-...` and `557da842-...`. None of them contains a call to `tools/uc` or `tools.uc` (the entry command is dated 2026-11-08 and these sessions are from 2026-10-15 to 2026-11-09), so none is an "after" session. The only sessions that mention `tools/uc` are the current open ones, which are not closed.
- A before/after pair needs the same story or diff on both sides. No such pair was declared, so no "before" session was chosen for comparability; the single U1-1 session stays the baseline.

Command run (scratchpad outputs, not in the repository):

```
python -s -m tools.uc.savings_report --baseline-manifest docs/sdlc/evidence/u6-5-baseline-manifest.json --current-manifest <path to a nonexistent file> --project-dir D:/tmp/u6-5-baseline-transcripts --paired-tasks <path to a nonexistent file> --out-json <scratch> --out-md <scratch>
{"refusals": ["MISSING_CURRENT"], "status": "NOT_RUN", ...}
```

Exit code 2. This command stops at `MISSING_CURRENT` before the baseline is checked, so it does not itself prove the baseline verifies; that proof is the `token_baseline.py report` run in the table above.

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

1. ~~A baseline that verifies.~~ Done in U6-5: `docs/sdlc/evidence/u6-5-baseline-manifest.json` verifies against the closed session `557da842-...`. Still open: confirm that this session is the wanted baseline, or name other closed sessions (the builder is `python -s tools/uc/token_baseline.py build-manifest --project-dir <dir> --sessions <ids> --out <file>`).
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
