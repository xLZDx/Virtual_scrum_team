# S2-4.12c runtime attempt — GPT-PM request 8ee40d1a

## Outcome

**HOLD at root-captured preflight.** The one authorized direct host invocation verified the exact
checkout and launcher, then started one Ubuntu-24.04 WSL child. All 17 fresh identity, pin,
configuration, runtime, manifest, systemd and empty-state checks passed. The one root-captured
preflight command returned exit code 2 and refused the probe namespace:

    probe capture refused: probe namespace exposes an unapproved Windows or host mount

The authorization is consumed. Stop here; do not retry, remount, bypass the preflight, or proceed
to any later stage.

## Identity and invocation

- GPT-PM authorization: 8ee40d1a-27a4-4e1b-9129-292a58959aa3; retry_cap=0.
- Attempt identity: 3a3a0e67-5577-4383-8e1b-5bf803727558.
- Checkout HEAD verified before invocation: 7d1d16f6348e6c00a5a568b5cfbc8caf309194b9.
- Launcher SHA-256 and size verified before invocation:
  5b03f670ec0f5adb01508d63d9f27582bde40fc66d0a8b490299721b621389db; 29,899 bytes.
- Exact command: C:\Python314\python.exe -I -B -S D:\Repo\Virtual_scrum_team\docs\sdlc\evidence\s2-runtime-qual-b3a9b780-launcher.py.
- Working directory: D:\Repo\Virtual_scrum_team.
- Launched directly with shell=false; no cmd.exe or PowerShell intermediary.
- Outer host process started 2026-10-30T12:55:52.648Z and finished
  2026-10-30T12:57:01.019Z; exit code 0, signal null.
- WSL protocol started 2026-10-30T14:55:55.674959+02:00 and finished
  2026-10-30T14:57:00.986356+02:00; WSL child exit code 0; terminal HOLD.
- Immutable attempt tuple: run ID s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910;
  bootstrap request ID e520e04f58ad5e6a431a3a20b0efb87c; nonce
  0aac24fec9a2a5c53c5e9da21cbb4a42; runtime selector
  /opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2.

## Stages and checks

All 17 protocol checks passed:

1. Immutable tuple matches pinned attempt — PASS.
2. Exact HEAD — PASS.
3. Collector source pin — PASS.
4. Validator source pin — PASS.
5. Applier source pin — PASS.
6. Root preflight source pin — PASS.
7. Bundle manifest source pin — PASS.
8. Installation layout source pin — PASS.
9. All 26 post-apply destinations match type, UID, GID, mode, size and SHA-256 — PASS.
10. Runtime selector — PASS.
11. Boot identity unchanged — PASS.
12. Run/request/nonce/selector configuration tuple — PASS.
13. Exact one-selector manifest with retry_cap zero — PASS.
14. Nine-unit readiness predicate with named-property parsing — PASS.
15. No systemd jobs — PASS.
16. systemd running — PASS.
17. Store, preflight, attestation and runtime socket paths absent — PASS.

Mount handling:

- Exact mountpoint query found /mnt/d absent as a mountpoint (findmnt exit 1).
- One authorized temporary read-only mount ran: /usr/bin/mount -t drvfs D: /mnt/d -o ro,
  exit 0.
- Verification returned source D:, filesystem 9p, options containing ro and not rw.
- The read-only mount was removed by /usr/bin/umount /mnt/d, exit 0; no warning.

The single preflight command was:

    /usr/bin/python tools/vst/preflight_host_capture.py --run-id s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910 --nonce 0aac24fec9a2a5c53c5e9da21cbb4a42 --expected-head 7d1d16f6348e6c00a5a568b5cfbc8caf309194b9 --expected-sha256 0f3b7b6fe11798ebc806a55bd4d6f687e7974b6f4394b2065e15defab8255083 --request-id e520e04f58ad5e6a431a3a20b0efb87c --expected-supervisor-sha256 cab6537ebaa4b568814cf8660586144ce640af086ea3e9a908d4981c17c05e60 --expected-profile-sha256 380b14dcdfe50dd7969175cb3b4f619e7f0ece93c53f8a9f4d1bed94c57fd757 --expected-bootstrap-sha256 df0d5701e6a356d43224208cd9a099183e12404967f5133838bd978e0b7834c1 --expected-manifest-sha256 c9dc31dce7419214d88a4da5dd645f5905ef01f8640154d357143f73afdcc860

It returned exit 2; stdout was empty (0 bytes, SHA-256
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855); stderr was 83 bytes,
SHA-256 884fce481d6fa1867e85832278d84e09eca976b00a8441ff235fae579c5b0cfc. The refusal is an
enforced predicate. No workaround or host-mount exception was attempted.

The preflight's measurement stage started the one-shot sandbox-probe systemd unit; that is the
service start that produced the refusal above. No assignment bootstrap, issuer, Supervisor,
Runner, dispatch service start, Owner submission, durable Owner-to-Runner claim/probe, or
report-bound TestRun occurred. The exact selector remains NOT_RUN:

    tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment

No restricted selector, process kill, crash, recovery, Store mutation, migration, credential/key
operation, persistent WSL change, production activation or deployment occurred. The read-only
mount was the only temporary environment change and it was unmounted successfully.

## Raw artifacts

- Outer stdout: s2-runtime-qual-8ee40d1a-outer.stdout.bin, 1,395 bytes, SHA-256
  f18bc51bf5ebbbafce748207e6e10fdc47aa0de912dc13ee42f4f2a1e561c54e.
- Outer stderr: s2-runtime-qual-8ee40d1a-outer.stderr.bin, 0 bytes, SHA-256
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
- Attempt JSON: s2-runtime-qual-3a3a0e67-s2-runtime-20261030-2b5e04a3.attempt.json,
  29,137 bytes, SHA-256
  228ccd03976964ebf3e2a19843ad7d9f08575aa8d4023e21e8eba72478c86ad5.
- WSL stdout protocol: s2-runtime-qual-3a3a0e67-s2-runtime-20261030-2b5e04a3-wsl.stdout.bin,
  19,343 bytes, SHA-256
  935c3107c7cb3a4128b15cab36f909d7b7b3d665d3b41fb53ae244f0c7dac54b.
- WSL stderr: s2-runtime-qual-3a3a0e67-s2-runtime-20261030-2b5e04a3-wsl.stderr.bin,
  0 bytes, SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.

## Next action

S2-4 remains IN PROGRESS; S2-5 remains queued. Codex owns reconciling the approved temporary
read-only D: mount with the preflight's host-mount refusal and obtaining a new correlated
authorization if the accepted boundary can be made consistent. The e2e-runner must not retry this
consumed authorization or bypass the preflight refusal.
