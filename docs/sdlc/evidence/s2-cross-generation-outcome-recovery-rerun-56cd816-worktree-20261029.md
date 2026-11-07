# S2-1 M03 recovery regression rerun — worktree at code HEAD `56cd816` — 2026-10-29

## Execution identity

- Repository branch: `s2-canonical-continuation`.
- Code HEAD: `56cd816b1b03b39c3f4b4a70ecf00d96ef95d321`.
- The only task-scoped source change in this run is an uncommitted test-fixture correction in `tests/vst/test_s2_store_backed_pubsub.py`; the other tracked and untracked worktree changes were pre-existing and left untouched.
- Executor role: `e2e-runner`.
- Environment: Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4; canonical `D:\Repo\Virtual_scrum_team` mounted from D: to `/mnt/d` with drvfs in the same WSL invocation.
- Scope: the four focused S2-1 regression files only. No restricted process-kill, crash/recovery, mutation, E8, or policy selectors were run.

## Exact invocation

```powershell
wsl.exe -d Ubuntu-24.04 --user root -- sh -lc 'set -eu; if ! mountpoint -q /mnt/d; then mkdir -p /mnt/d; mount -t drvfs D: /mnt/d; fi; grep -F "D: /mnt/d " /proc/mounts; cd /mnt/d/Repo/Virtual_scrum_team; printf "HEAD="; git rev-parse HEAD; git rev-parse HEAD | grep -Fx 56cd816b1b03b39c3f4b4a70ecf00d96ef95d321; python3 --version; python3 -m pytest --version; sha256sum tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py; /usr/bin/time -f "DURATION_SEC=%e" python3 -m pytest -q tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py'
```

- Result: **130 passed, 0 failed**, pytest exit 0 in 17.58 seconds; `/usr/bin/time` reported 19.38 seconds.
- SHA-256 of the exact worktree test files executed:
  - `tests/vst/test_s2_signed_dispatch_instruction.py`: `13b436675383e98449520c15c640a87fcb84370ade534475b5ad2c63ece8b76f`
  - `tests/vst/test_s2_store_backed_pubsub.py`: `435262304ca08fef9ed371748fa8184086ada46a8f016b4751a997db37f228e7`
  - `tests/vst/test_s2_dispatch_owner_service.py`: `fc7e194cb45700446438c776281be789f8ad0551edc5c506887af35af020df71`
  - `tests/vst/test_s2_dispatch_owner_latch.py`: `dd747aa5c42cf4745197c77b0138c2e71bdd9690ed3d779d00969142382d35f1`

## Commit binding

After the run, commit `dcb5d63c19eeb63f2f17fce0add510937688e819` was created. Its
`tests/vst/test_s2_store_backed_pubsub.py` blob (`da70c3b9a01c697bec8011f2814c4217fdf6688b`)
was read back from Git and SHA-256 checked as
`435262304ca08fef9ed371748fa8184086ada46a8f016b4751a997db37f228e7`, matching the file executed
by this run. The result is therefore bound to that committed test blob, while the other three
selected test files were unchanged at the tested code head.

## Fixture correction and acceptance mapping

The preceding current-code-head run `s2-1-current-regression-run-56cd816-20261029.md` returned 129 passed and one failure. `test_pending_dispatch_barrier_survives_store_reopen` directly called `Store.accept_dispatch_intent` without the trusted synthetic public-key fingerprint now required by the legacy API path. It failed authorization before reaching the intended service-generation duplicate assertion. The production Supervisor computes and supplies this fingerprint.

The fixture now calls the existing `public_key_fingerprint(keypair.public_key_path)` helper and passes that value to each of its three direct Store calls. The original `duplicate`, `lifecycle`, pending-barrier, and exact-replay assertions are unchanged. The four-file current-worktree rerun passes.

## Limits and disposition

- This verifies focused synthetic source behavior at code HEAD `56cd816` with the recorded test-file worktree hash. The corrected test is uncommitted, so this is **not exact committed-blob evidence**; rerun or verify the Git blob after the eventual task commit.
- This does not prove installed systemd behavior, production identity/root configuration, current E5, real owner-to-Runner runtime, or overall S2 acceptance.
- No code review, PM approval, commit, push, or PR is claimed by this record.
