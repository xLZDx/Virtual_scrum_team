# Change 0379: S4 wheelhouse and compiler recheck

## What changed

- Added a read-only current-turn inventory of the recorded S4 wheelhouse and WSL compiler to the prerequisite evidence.

## Why

The S4 acceptance plan names a trusted offline wheelhouse and Ubuntu compiler as prerequisites. This record makes the current availability and identity boundary explicit without claiming that their presence proves acceptance.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-prerequisite-provisioning-20261026.md`
- S4 offline dependency provenance and AC-16 helper-build prerequisites.

## Verification and scope

- The six wheelhouse SHA-256 values were read from `D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse` and matched the exact six digests recorded in the provisioning evidence and QA lock.
- Read-only WSL commands were `wsl.exe -d Ubuntu-24.04 -- /usr/bin/gcc --version`, `wsl.exe -d Ubuntu-24.04 -- /usr/bin/cc --version`, and `wsl.exe -d Ubuntu-24.04 -- /usr/bin/id`.
- Observed GCC/CC `13.3.0`; default WSL command identity was UID/GID 0:0. This is not worker-identity or sandbox evidence.
- No download, installation, compilation, helper installation, test, or source-code change occurred in this recheck.
- No author/provenance claim is made about who originally provisioned the artifacts; the earlier project evidence attributes that action to Codex.

## Decision and limitation

Do not use the prerequisite check to upgrade report-bound identity or S2 system acceptance. Existing exact-run test evidence and the 53 policy `NOT_RUN` selectors remain governed by their separate acceptance records.
