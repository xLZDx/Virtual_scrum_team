# Change 0517: add the bounded S2 dispatch-owner relay contract

## Change summary

Added an unprivileged, systemd socket-activated AF_UNIX relay for the exact S2 signed dispatch
instruction already accepted by the root Supervisor. The relay accepts one bounded canonical JSON
envelope per connection, validates it against a root-owned public trust registry shared with the
Supervisor, forwards it unchanged through the existing `SupervisorClient`, and returns the
validated Supervisor response.
It has fixed configuration, cgroup and socket boundaries; it adds no scheduler, assignment
authority, task queue, disk spool, signer, private key, Store access, Runner access, network path or
automatic retry.

## Why

GPT-PM's provisioning-plan review found a shared GID collision and a missing exact owner service
boundary. A distinct primary GID and a real source-controlled unit contract are required before the
non-secret provisioning plan can be accepted. The Store and root Supervisor remain the only task,
assignment and lease authorities; the relay only carries an already signed exact instruction.

## Affected contracts and files

- `tools/vst/dispatch_owner_service.py` validates the fixed config and public registry, requires
  the exact owner systemd cgroup and socket-activation descriptor, enforces bounded canonical
  framing, and forwards only `{"instruction": envelope}` through the existing verified client.
- `tools/vst/dispatch_instruction.py` defines the single fixed public-registry path; the
  `supervisor_service.py` config schema references that path and the root Supervisor loads the same
  root-owned registry that the owner relay reads, avoiding duplicate key maps.
- `tools/vst/systemd/vst-dispatch-owner.service` fixes the unprivileged UID/group, supplementary
  shared socket group, isolated Python entry point, AF_UNIX-only process and fail-stop behavior.
- `tools/vst/systemd/vst-dispatch-owner.socket` fixes the root-owned shared-group socket, path,
  mode, single service activation and bounded backlog.
- `tools/qa/install_wsl_runtime.ps1` and `tools/qa/install_wsl_runner_runtime.sh` require and
  install the owner module and both unit templates as immutable runtime artifacts. Installation
  still does not enable, start or reload any service.
- `tools/vst/systemd/README.md`,
  `docs/sdlc/evidence/s2-dispatch-owner-service-contract-20261029.md`, and the revised
  `docs/sdlc/evidence/s2-root-runtime-provisioning-plan-20261028.md` document the boundaries,
  source schemas, missing inputs and provisional identity mapping.
- `docs/sdlc/evidence/s2-provisioning-plan-adjudication-20261029.md` records the correlated PM
  review and its four findings; `core/DECISION_LOG.md` and `core/LESSONS_LOG.md` preserve the
  decision and implementation lesson.

## Key decisions

The candidate identity map keeps shared socket access at GID 984, uses dispatcher UID:GID 981:983,
and separates dispatch-owner UID:GID 980:982 with GID 984 only as supplementary membership. The
2026-10-29 read-only WSL `getent` lookups returned exit 1 with empty output for each proposed user,
group and numeric UID/GID. The values are provisional and must be rechecked before separately
authorized account creation.

Owner service config is root-owned, readable by its dedicated primary group, mode `0640`; the
shared public trust registry is root-owned, mode `0644`, with public key files in the existing
root-trusted location contract. The owner service and root Supervisor read the same fixed registry
path; no duplicated key map exists. No private key is placed in either artifact.

## Review and verification state

- GPT-PM provisioning review returned MODIFY with 0 confirmed BLOCKER, 2 MAJOR and 2 MINOR
  findings. Correlation and exact dispositions are recorded in
  `docs/sdlc/evidence/s2-provisioning-plan-adjudication-20261029.md`. This commit implements the
  source correction but does not claim that GPT-PM accepted the revised plan.
- The owner service and units are source artifacts only. No account/group, `/etc` configuration,
  public/private key, runtime installation, systemd daemon reload, enable/start, migration,
  dispatch, network change, E5 attestation, push, PR or merge occurred.
- Tests, checks, builds and CI are `NOT_RUN`; no runtime integration is proven. A designated
  `functional-test-reviewer` must author mapped tests after coding is complete and `e2e-runner`
  must execute them. Specialist review and exact-head GPT-PM review remain outstanding.
- `S2-DISPATCH-M01` remains MAJOR/OPEN. S2 is not approved; S3 stays unstarted. Production
  dispatch remains disabled until an authorized issuer and public key, exact provisioned identity,
  configuration, runtime provenance and allowed runtime evidence exist.

## Ordered next actions

1. Finish source/documentation reconciliation and commit this implementation with the registry
   regenerated from staged Markdown only.
2. Have `functional-test-reviewer` add the owner-service, framing, config, signature, forwarding,
   timeout and refusal tests; then have `e2e-runner` execute mapped tests at the exact source head.
3. Resolve valid findings; run relevant specialist review and obtain the exact-head GPT-PM source
   gate. Ask GPT-PM separately to re-review the exact revised non-secret provisioning plan.
4. Keep all prohibited runtime actions and S2/M01 acceptance closed until their distinct evidence
   and authorization gates are satisfied.
