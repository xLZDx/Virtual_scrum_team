# Change 0519: align dispatch-owner test parameters with the test signature

## Why

The first focused collection attempt at S2 change 0518 HEAD `65c29f7b70023c7611f86b4a6ea77d90c3231423`
stopped with pytest exit code 1 before executing any test. The exact collection error was that
`test_s2_owner_service_rejects_untrusted_systemd_activation_descriptor` declared only `env` but its
`pytest.mark.parametrize` also supplied an unused `reason` argument.

## What changed

The functional-test-reviewer changed the parameter list to `env` and represented each of the three
environment cases as a single value. The accepted IDs remain `wrong-activation-pid`,
`extra-activation-fd`, and `wrong-activation-name`. Product code, expected behavior and test cases
were not changed.

## Verification state

- Initial exact-head attempt: focused pytest collection exited 1 with one collection error and zero
  test bodies executed. The error was a test-source signature mismatch, not a product failure.
- The corrected test source has not yet been executed. `e2e-runner` owns the next focused run on this
  commit.
- The existing protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not read,
  staged or modified.
- No source, environment, dependency, systemd unit, runtime state, migration, key or external
  service was changed.

## Acceptance and ownership

This closes only the test collection defect. It does not establish S2-PROV-M03 behavior or any test
pass. The functional-test-reviewer owns test authoring; e2e-runner owns execution; Codex owns evidence
and coordination. S2 remains NOT APPROVED and S3 remains unstarted.
