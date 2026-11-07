# S2-4.12c runtime attempt — GPT-PM request 268fd73c

## Outcome

**HOLD at the fresh post-apply status predicate** all_9_units_loaded_inactive_dead_no_pid.
The single authorized host invocation started one Ubuntu-24.04 WSL child and stopped before root
preflight. No unit was started. Owner-to-Runner claim/probe and the exact TestRun selector are
NOT_RUN. The authorization has retry_cap=0; no retry was made.

The failing result appears to be a launcher status-parser mismatch, not an observed active unit:
the command used systemctl show with LoadState, ActiveState, SubState, MainPID, Job and --value,
while the eight service responses placed MainPID=0 first and the socket response omitted MainPID.
The launcher expected the opposite fixed order and five values for every unit. This is an inference
from the captured values; the acceptance result remains HOLD, and no runtime stage is upgraded to
PASS.

## Authorization and host invocation

- GPT-PM authorization: 268fd73c-51e0-477a-83c1-5fcd724a5467.
- Attempt identity: dc22ee55-1f57-44e1-9590-b4e85e6e5db0.
- Source HEAD verified before launch: 7d1d16f6348e6c00a5a568b5cfbc8caf309194b9.
- Launcher verified before launch:
  s2-runtime-qual-b3a9b780-launcher.py, SHA-256
  6c6e0c6e41bf67c3c170cc08492b45b0c4ae18888741a7fd5d95d7ba6cf16fa1.
- Exact command: C:\Python314\python.exe -I -B -S D:\Repo\Virtual_scrum_team\docs\sdlc\evidence\s2-runtime-qual-b3a9b780-launcher.py.
- Working directory: D:\Repo\Virtual_scrum_team.
- Outer process: started 2026-10-30T12:42:49.981Z, finished
  2026-10-30T12:42:55.959Z, exit code 0, signal null.
- The launcher recorded one WSL child, command ending in /usr/bin/python3.12 -I -B -S -,
  child exit code 0, no spawn error, and terminal HOLD.
- Embedded protocol: started 2026-10-30T14:42:53.697007+02:00, finished
  2026-10-30T14:42:55.911913+02:00.
- Immutable identity retained: run ID s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910,
  bootstrap request ID e520e04f58ad5e6a431a3a20b0efb87c, nonce
  0aac24fec9a2a5c53c5e9da21cbb4a42, selector
  /opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2.

## Stage and predicate record

- WSL mountpoint detection found /mnt/d was not mounted (findmnt exit 1). One authorized
  temporary mount ran: /usr/bin/mount -t drvfs D: /mnt/d -o ro, exit 0. Verification succeeded:
  source D:, filesystem 9p, options included ro and not rw.
- Exact source HEAD, immutable attempt tuple, all six source pins, all 26 target path/type/UID/GID/
  mode/size/SHA-256 values, runtime selector, unchanged boot ID, config tuple, exact retry-zero
  manifest, no systemd jobs, systemd is-system-running == running, and empty Store/preflight/
  attestation/socket paths all passed their recorded checks.
- All nine read-only systemctl show commands exited 0. Captured --value arrays, in unit order:

| Unit | Values |
|---|---|
| vst-assignment-bootstrap.service | ["0","loaded","inactive","dead",""] |
| vst-dispatch-issuer.service | ["0","loaded","inactive","dead",""] |
| vst-dispatch-owner.service | ["0","loaded","inactive","dead",""] |
| vst-dispatch-owner.socket | ["loaded","inactive","dead",""] |
| vst-dispatcher.service | ["0","loaded","inactive","dead",""] |
| vst-runner.service | ["0","loaded","inactive","dead",""] |
| vst-sandbox-probe.service | ["0","loaded","inactive","dead",""] |
| vst-signer.service | ["0","loaded","inactive","dead",""] |
| vst-supervisor.service | ["0","loaded","inactive","dead",""] |

- The launcher unit predicate returned false because it expected each array to begin with
  loaded,inactive,dead,0,'' and required at least five values for the socket too. The first
  failing predicate caused immediate HOLD; root preflight was not called.
- The one temporary mount was cleaned up: /usr/bin/umount /mnt/d, exit 0; no unmount warning.
- Reached: local pre-launch HEAD/hash verification; one host launch; one WSL child; one temporary
  read-only mount; scoped read-only source/config/systemd observations.
- NOT_RUN: root-captured preflight; service starts; bootstrap/issuer/Owner submission; durable
  Owner-to-Runner claim/probe; report-bound TestRun
  tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment;
  restricted selectors; production activation.
- No application source, launcher, persistent WSL configuration, credentials, keys, or runtime
  files were changed. Only the temporary mount was created and removed; no process was killed.

## Raw artifacts

- Outer stdout: s2-runtime-qual-268fd73c-outer.stdout.bin, 1,395 bytes, SHA-256
  fa579bb09917412007a8a84b2b6fd8023ffe52aa8039e7fd3a9945207104a25c.
- Outer stderr: s2-runtime-qual-268fd73c-outer.stderr.bin, 0 bytes, SHA-256
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
- Attempt JSON: s2-runtime-qual-dc22ee55-s2-runtime-20261030-2b5e04a3.attempt.json,
  24,507 bytes, SHA-256
  ab8dc91939afb9a4263d25150dc38270bf37190ffb48da3cb1fe9013ab4a265a.
- WSL stdout protocol: s2-runtime-qual-dc22ee55-s2-runtime-20261030-2b5e04a3-wsl.stdout.bin,
  15,995 bytes, SHA-256
  2029de834d5c999776ab3957be0d6efa778dfebe0cddcb931308bf8de97173b6.
- WSL stderr: s2-runtime-qual-dc22ee55-s2-runtime-20261030-2b5e04a3-wsl.stderr.bin, 0 bytes,
  SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.

## Next action

S2-4 remains IN PROGRESS and S2-5 stays queued. Codex owns preparing and obtaining review of a
narrow launcher-only correction that parses named systemd properties rather than assuming array
order and handles the socket unit's missing MainPID field. Because this authorization is consumed,
any new runtime attempt requires a new correlated GPT-PM authorization for the exact launcher
bytes. The e2e-runner must not retry this attempt.
