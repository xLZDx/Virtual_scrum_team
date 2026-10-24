# 0134 S4 correlated transfer and native E2E evidence

## What changed

- Recorded transfer metadata and run-scoped clone/worker permission verification separately from native test execution.
- Recorded the corrected seven-selector native E2E run on the identified snapshot, the initial working-directory invocation error, and the clean post-run status.
- Updated the E2E denominator description, backlog and lesson log; regenerated the document registry.

## Why

The prior corrected native E2E run was blocked by one platform-aware test oracle defect. After that oracle was committed, S4 needed a fresh exact-head snapshot and a scoped read-only worker rerun to establish whether the correction worked on the named POSIX runtime.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-wsl-transfer-452c8ea.md`
- `docs/sdlc/evidence/s4-native-e2e-452c8ea.md`
- `docs/qa/categories.json`
- `core/BACKLOG.md`, `core/LESSONS_LOG.md`, `core/DECISION_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`
- S4 mapped native E2E acceptance for the registry selectors at source HEAD `452c8ea`.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`).
- Technical owner for the signer/report/gate service path remains unknown in the S4 plan; this transfer and test run do not claim those gates.
- Private POSIX username, numeric IDs, and snapshot-root path are omitted. All WSL probes and pytest execution were scoped to returned run ID `e8b68c59c17a449eb2e30803021a37ae`.
- The initial pytest invocation from `/` is recorded as a command setup error; the corrected invocation used the same seven mapped selectors and identified snapshot checkout.

## Verification state

- Source pre-transfer HEAD: `452c8ea8da5545bdce0f584a6b51662b93a33abf`, clean.
- Transfer: `TRANSFERRED`, exact candidate HEAD match, bundle SHA-256 `2d986eb65301d89e2530a13cce8a9924378dd7851c1fa986f78051edd0dd344c`, size `972190` bytes.
- Runner clone ownership/mode scan and worker read/write-denial probe: PASS; details in transfer evidence.
- Native E2E: 7 passed, 0 failed, 0 skipped in 4.05 seconds, no warnings. Exact selectors and environment are in native evidence.
- Post-run worker Git status: clean, zero status bytes, same candidate HEAD.
- Signer, report-bound command, receipt, gate, and broader sandbox acceptance remain `NOT_RUN`.

## Follow-up

1. Resolve the separately provisioned signer socket and authorized report-bound runner before claiming signed receipt/gate acceptance.
2. Keep E2E coverage partial until the remaining S4 acceptance paths have exact-head runtime evidence.
