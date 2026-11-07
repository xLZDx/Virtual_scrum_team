# Change 0521: record focused S2 admission-fence test results

## Why

The S2-0518 source and mapped test coverage required a report-bound functional run after coding was
committed. The designated e2e-runner exercised the exact committed synthetic source snapshot and
reported the attempt history, environment, command, test source hashes and limitations.

## What changed

- Added `docs/sdlc/evidence/s2-0518-admission-fence-test-run-20261029.md` with three exact-head
  attempts: an initial collection defect at `65c29f7`, a later 100-pass/5-test-defect run at
  `a1fa0b0`, and the accepted **105 passed, 0 failed** run at
  `cec0dbf3249b5734bdae52f644ac790e07d869f8`.
- Recorded the exact pytest command, WSL/Python/pytest/OpenSSL versions, synthetic-key cleanup,
  temporary non-Git archive procedure, all six test-source SHA-256 hashes, failure classifications,
  and what runtime/production evidence the test run does not establish.
- Regenerated the generated document registry to include the report and this change record.

## Verification state

- The accepted test execution belongs to code/test commit `cec0dbf`; this commit adds report and
  registry documentation only. No source or test bytes changed after that run.
- The protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not read, staged,
  modified or removed.
- Systemd unit validation/activation, `/etc` latch write, production key/coordinator, E5, real
  dispatch, restricted selectors, push, PR and merge remain unverified or not performed.

## Acceptance and ownership

The test result satisfies only the focused synthetic source cases. `S2-PROV-M03` still requires
independent code/reliability/security review and exact-head GPT-PM adjudication; `S2-DISPATCH-M01`
and full S2 remain open. `e2e-runner` owns execution; Codex owns the evidence/record; GPT-PM owns the
focused adjudication. S2 remains NOT APPROVED and S3 remains unstarted.
