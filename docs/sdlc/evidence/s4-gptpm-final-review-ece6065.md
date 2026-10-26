# GPT-PM final review — S4 exact head `ece6065`

## Correlation and parser receipt

- Project: `virtual_scrum_team` (registered project conversation ID returned by review tool: `6ade65b6-4540-83ed-a375-768eb199b547`).
- Review range: `3b8d80ff5456192c2419d9515b47fb843939ee16..ece606584a7c0dd86e76ce475d6f6728c6804508`.
- Review request ID: `5d258643-62e4-45cd-8360-ba624a2ed491`.
- Correlated reply ID: `612b234a-d0ca-5ea7-96bd-3ca1a67ee791`.
- Review input SHA-256: `d9c7a08ba70a6d97505771282e483b257f1b605af00a559082499bc60e370b18`.
- `review.js` receipt: `ok=true`, `review_status=RAN`, `correlated=true`, `final=false`, `final_overridden=true`, parser verdict `UNRECOGNIZED`. The raw correlated reply below explicitly says `VERDICT: REJECT`; no approval is recorded.
- The scope note sent with this request is `s4-gptpm-review-scope-ece6065.md`.

## Raw correlated reply

```text
ChatGPT said:

REQUEST_ID: 5d258643-62e4-45cd-8360-ba624a2ed491

VERDICT: REJECT — S4 acceptance remains incomplete. No new confirmed BLOCKER/MAJOR source defect in the supplied AC-16/AC-17 implementation.

Project: Virtual_scrum_team
Review range: 3b8d80ff5456192c2419d9515b47fb843939ee16..ece606584a7c0dd86e76ce475d6f6728c6804508
Review: adversarial, read-only.

Findings
MAJOR-01 — OPEN | 52 mandatory selectors remain NOT_RUN

Evidence: docs/qa/categories.json, tools/qa/build_registry.py, tools/qa/matrix.py, core/BACKLOG.md:VST-037.

Reachable action: An operator attempts to close S4 using only the passing executable selectors.

Contract impact: The existing Definition of Done still includes 52 policy-prohibited selectors. Neither their absence from execution nor their explicit NOT_RUN records constitutes acceptance.

Required correction: Obtain an applicable policy authorization or accepted signed waiver, then produce a new exact-head matrix. Do not execute or reclassify the excluded selectors under the present authorization.

Disposition: OPEN, unchanged from the previous review. This is an acceptance blocker, not a newly discovered source defect.

MAJOR-02 — SOURCE REMEDIATED; RUNTIME NOT VERIFIED | Dependency-content provenance

Evidence:

tools/qa/dependencies.py:61–337

tools/qa/run.py, dependency preflight, launch and post-execution checks

tools/qa/matrix.py, category schema-v3 validation

tests/qa/test_s4_dependency_provenance.py

The revised implementation now:

Selects wheel bytes using the exact lock SHA-256.

Validates wheel metadata and RECORD contents.

Compares the installed target inventory and file contents with the verified wheels.

Rechecks provenance immediately before launching pytest.

Rechecks after execution and records mismatches as non-approving.

Binds dependency hashes and target digests into the category reports and matrix.

These changes address the previously identified version-only verification defect.

Remaining limitation: dependency_execution_integrity: NOT_VERIFIED accurately acknowledges that same-identity mutation followed by restoration during execution is not excluded by pre/post snapshots.

Required evidence: Execute the report-bound runner on the corrected exact candidate with an existing trusted wheelhouse. Verify both successful and negative provenance outcomes. Preserve the declared execution-integrity limitation.

Disposition: Source-level remediation supported; runtime closure NOT VERIFIED. No separate new source MAJOR is established by the stated limitation.

AC-16 — WSL worker identity
SOURCE REVIEWED — RUNTIME NOT_RUN

Reviewed:

tools/qa/worker_exec.c

tools/qa/install_wsl_worker_helper.sh

tests/qa/test_s4_functional_worker_identity.py

tools/qa/registry.py

tools/qa/root_harness.py

docs/S4_WSL_WORKER_UID_HELPER_DESIGN.md

The helper implements the specified fixed identity transition from UID/GID 997:988 to 999:989, clears supplementary groups and inherited descriptors, drops saved credentials, and uses a fixed Python executable with a sanitized environment.

Its -c script argument remains caller-controlled. That is part of the documented design: the helper delegates execution to the fixed worker identity, rather than restricting execution to one immutable script. It must therefore be treated as a deliberate trust-boundary delegation, not as proof that only the AC-16 test can execute through it.

No additional source defect is confirmed from the supplied diff.

However, the helper was not installed, and the WSL functional selector has not executed. Therefore, the UID/GID, file-denial, socket-denial, and runtime helper-identity guarantees remain unverified.

Evidence assessment

Requirement: AC-16 helper implementation — Source reviewed
Requirement: AC-16 WSL report-bound test — NOT_RUN
Requirement: AC-17 dependency-content verification — Source reviewed
Requirement: AC-17 focused Windows tests — 7/7 reported PASS
Requirement: AC-16/17 focused E2E contracts — 2/2 reported PASS
Requirement: AC-17 full report-bound runtime — NOT_RUN
Requirement: In-execution dependency immutability — NOT_VERIFIED
Requirement: Existing 52 policy selectors — NOT_RUN
Requirement: Updated full S4 matrix — NOT PASSED

The reported 7/7 and 2/2 results are supplied execution evidence. I did not independently reproduce those runs or verify the complete Git checkout at the requested HEAD.

Required next steps

Resolve the existing trusted wheelhouse path. The installed dependency target is not a substitute.

Establish the authorized WSL helper installation prerequisites, including /usr/bin/cc, without bypassing environmental restrictions.

Install the exact-head helper through the documented immutable-source procedure.

Run AC-16 through the ordinary WSL report-bound functional category.

Run AC-17 through the required report-bound profiles, validating the schema-v3 dependency evidence.

Regenerate the exact-head 15-reference matrix.

Address the 52 policy exclusions through the separate authorized policy or waiver process.

Final disposition

AC-16/AC-17 source review: No newly substantiated BLOCKER or MAJOR defect.

Previous MAJOR-02: Source remediation accepted provisionally; runtime verification outstanding.

Previous MAJOR-01: OPEN — 52 mandatory policy exclusions.

S4 final gate: REJECT / NOT CLOSED.

No push, PR, merge, helper installation, downloads, policy changes, or external system modifications were performed.
```

## Reconciliation against observed evidence

The raw reply's statement that no helper installation occurred is consistent with no binary being installed; a delegated installer attempt at exact candidate `ece6065` did reach compilation and stopped with `/usr/bin/env: '/usr/bin/cc': No such file or directory`. The installed helper path remains absent. The agent found no `cc`, `gcc` or `clang`, no installed `gcc`/`build-essential`, and no matching package in `/var/cache/apt/archives`; no package or network action was taken. This is the exact runtime dependency preventing helper installation.

The S4 registry generator records 52 unchanged policy `NOT_RUN` rows. The existing `D:\Temp\virtual_scrum_team_qa_f4ef8e7` path is an installed dependency target, not a wheelhouse; no trusted existing wheelhouse path has been established. Accordingly, the verdict is a rejection of S4 acceptance, not an approval to promote or merge.
