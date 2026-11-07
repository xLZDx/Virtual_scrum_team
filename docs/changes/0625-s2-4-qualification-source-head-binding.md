# S2-4 qualification source HEAD binding

## Acceptance delta

GPT-PM's correlated one-shot review request `a1333e6f-716a-4ea7-9c21-c792142b1992` returned HOLD because it could not independently verify the exact runtime execution chain, including that the host qualification launcher was bound to a pushed source identity. Local exact-source inspection then established a concrete mismatch: the launcher attempted to retrieve `tools/qa/run_s2_runtime_qualification.py` and `tools/qa/s2_runtime_qualification_wsl.py` from runtime source HEAD `80c2b81deac364ed6466600fd46af47aafe805e2`, but neither path exists in that Git tree.

## Implementation

`tools/qa/run_s2_runtime_qualification.py` now treats deployed runtime source and the host qualification code as separate immutable inputs. The authorization identity includes a full `qualification_source_head`; `source_pins.runtime` exactly matches the runtime archive; `source_pins.qualification` contains exactly the two launcher files. The launcher requires the qualification HEAD to equal the current repository HEAD, then checks both the committed Git blobs and safely read working files against the authorized digests. The streamed WSL protocol source is checked against its qualification pin. This closes the source-identity mismatch that prevented independent verification; it does not establish runtime acceptance or grant execution authority.

## Task-mapped verification

The designated `functional-test-reviewer` ran five focused mock-only selectors at base HEAD
`16549bb8f10113b2f05f41b3aa390bad80dab97e`: **5 passed, 0 failed**, exit 0, one
pytest-asyncio deprecation warning. Exact command, test identities, hashes and limitations are in
`docs/sdlc/evidence/s2-4-qualification-head-pins-20261030.json` and `.txt`. The test cases cover
closed identity schema, exact launcher pin coverage, runtime archive separation, committed-blob
and working-tree equality, and refusal before attempt/WSL invocation for a wrong expected HEAD.
Git and WSL are mocked; current runtime, live WSL/service state, authorization consumption and
candidate identity execution remain **NOT_RUN**.

Read-only `code-reviewer` and `security-reviewer` reviews of this exact source delta found no
material correctness or trust-boundary findings. Neither reviewer ran tests.
`git diff --check` passed after the implementation and test edits. This change has not yet been
committed or pushed at the time this record is written.

## Remaining S2-4 acceptance

S2-4 remains **IN PROGRESS**. Fresh current-run E5 provenance and a real permitted Owner-to-Runner
result with its report-bound TestRun are still absent. GPT-PM did not grant the requested runtime
authorization; no runtime or authorization-consuming action was run. The previously consumed
authorization `8ee40d1a-27a4-4e1b-9129-292a58959aa3` remains unusable.

## Owner and next action

Owner: **Codex**. Record this delta and focused evidence in the checkpoint, commit only the S2-4
implementation, its assigned tests, and task evidence/change record, then perform a normal push
through the enforced hook. After the pushed qualification HEAD is known, seek a fresh correlated
GPT-PM decision for the same bounded one-shot runtime scope. Only `e2e-runner` may execute the
approved runtime test. If authorization is again held or the safe preflight refuses, preserve the
exact result and keep S2-4 current; do not start S2-5.
