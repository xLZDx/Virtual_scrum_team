# S2-4 launcher adjudication and bounded remediation — 2026-10-30

Project: `Virtual_scrum_team`  
Task: `S2-4.12c`  
Repository evidence HEAD: `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`  
GPT-PM request: `98594d0e-1fb5-40ba-9ad5-148a3413e4e8`  
Reply timestamp: `2026-10-30T12:10:17.135Z`

## Decision

GPT-PM returned `HOLD — Exact Launcher Not Approved` and `GO` for only two launcher-only
remediations. It determined the existing runtime tuple is valid for conditional reuse: the prior
host failure happened before Python, so the tuple need not be regenerated solely for that failure.
Reuse still requires fresh exact HEAD, source-pin, boot/runtime, configuration and candidate-state
checks. This decision did **not** authorize another WSL invocation.

## Findings and authorized delta

1. **MAJOR-01 — exact mountpoint:** `findmnt --target /mnt/d` can report the containing
   filesystem when `/mnt/d` itself is not mounted. Use exact mountpoint detection, then verify
   source `D:`, filesystem `9p`, and read-only options.
2. **MAJOR-02 — isolated import path:** under `python3.12 -I -S -c`, the current directory is
   excluded from imports. The wrapper must establish an explicit verified import path to the
   pinned repository after verifying source identity, without weakening isolated mode or editing
   application/runtime source.

The only authorized changes are to
`docs/sdlc/evidence/s2-runtime-qual-b3a9b780-launcher.py`: exact mountpoint detection and an
explicit verified repository import root after all six source pins pass. Preserve exact source
HEAD `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`, all six pins, and the existing run ID,
bootstrap request ID, nonce and runtime selector.

## Corrected launcher state

Codex changed both `findmnt` calls from `--target` to `--mountpoint`. After all six pinned blobs
and working files pass the exact-source predicates, the wrapper resolves `/mnt/d/Repo/Virtual_scrum_team`,
inserts only that exact path into `sys.path`, and verifies the import root. It retains
`python3.12 -I -B -S -c`. No application, test, Store, runtime configuration, key, tuple, or Git
HEAD change was made by this remediation.

## Focused remediation verdict

GPT-PM replied under request `43bc1ebf-523d-4e3a-a077-f0b959cf214f` with
`APPROVED — BOTH MAJOR FINDINGS RESOLVED`. GPT-PM independently calculated the corrected launcher
SHA-256 as `d4cd4b3d4eacc1ca620223db7ec997821106528e345a6110531ca1a8d32511d5` and reported a hash
match. It verified the two `findmnt` option replacements and five-line import-path block as the
entire delta, with all tuple and six source pins unchanged. MAJOR-01 and MAJOR-02 are RESOLVED;
direct regressions received `PASS — STATIC REVIEW`.

This review did not run runtime behavior and did not authorize another Windows/WSL invocation.
The prior `b3a9b780` authorization remains consumed. GPT-PM's next-action decision is to request
a new single-use runtime authorization that names the approved corrected launcher hash.

Corrected launcher SHA-256: `d4cd4b3d4eacc1ca620223db7ec997821106528e345a6110531ca1a8d32511d5`.  
Runtime invocation: **NOT RUN / NOT AUTHORIZED by this review**.  
S2-4: **IN PROGRESS**. S2-5: **QUEUED**. Overall S2: **NOT APPROVED**. Production: **NOT APPROVED**.

## Separate runtime authorization request

Codex sent request `c7fe8392-72a3-4c81-91ee-8bfe8b3e4382` for a new single-use, zero-retry
runtime authorization referencing the approved hash and preserving the adjudicated tuple and six
pins. It requests only the previously bounded fresh status → preflight → durable claim/probe → one
exact-selector TestRun chain, with immediate stop on any failure or ambiguity. It does not request
or authorize any prohibited selector, mutation, migration, credential/key inspection, production
activation or deployment. At report generation time, the reply is pending and no runtime invocation
has occurred.

## Next step

GPT-PM performs one focused review of MAJOR-01, MAJOR-02 and their direct launcher regressions.
Only after that review may Codex seek a separate bounded runtime authorization. Do not run the
launcher using the consumed `b3a9b780` authorization. If later authorized, preserve the zero-retry
boundary and stop at the first missing, failed or ambiguous predicate.
