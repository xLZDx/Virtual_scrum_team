# S2-1 current-head cross-generation recovery regression run — 2026-10-29

## Execution identity

- Branch: `s2-canonical-continuation`
- Exact repository HEAD: `56cd816b1b03b39c3f4b4a70ecf00d96ef95d321`
- Role: `e2e-runner`
- Target source/test files were clean relative to HEAD before execution (`git diff --quiet HEAD -- <four selected files>` exit 0).
- Environment: Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4; canonical `D:\Repo\Virtual_scrum_team` mounted as `/mnt/d` using drvfs in the same WSL invocation.
- Focused suite only: `test_s2_signed_dispatch_instruction.py`, `test_s2_store_backed_pubsub.py`, `test_s2_dispatch_owner_service.py`, and `test_s2_dispatch_owner_latch.py`.

## Exact invocation

```powershell
wsl.exe -d Ubuntu-24.04 --user root -- sh -lc 'set -eu; if ! mountpoint -q /mnt/d; then mkdir -p /mnt/d; mount -t drvfs D: /mnt/d; fi; grep -F "D: /mnt/d " /proc/mounts; cd /mnt/d/Repo/Virtual_scrum_team; printf "HEAD="; git rev-parse HEAD; git rev-parse HEAD | grep -Fx 56cd816b1b03b39c3f4b4a70ecf00d96ef95d321; python3 --version; python3 -m pytest --version; sha256sum tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py; /usr/bin/time -f "DURATION_SEC=%e" python3 -m pytest -q tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py'
```

- Result: **129 passed, 1 failed**, pytest exit 1, 13.22 seconds; wall time 14.86 seconds.
- File SHA-256 at the tested HEAD:
  - `tests/vst/test_s2_signed_dispatch_instruction.py`: `13b436675383e98449520c15c640a87fcb84370ade534475b5ad2c63ece8b76f`
  - `tests/vst/test_s2_store_backed_pubsub.py`: `b5f6a36ab8511ea7e09a67d327a44b637b94faab312e0d13293cd735e293b0bc`
  - `tests/vst/test_s2_dispatch_owner_service.py`: `fc7e194cb45700446438c776281be789f8ad0551edc5c506887af35af020df71`
  - `tests/vst/test_s2_dispatch_owner_latch.py`: `dd747aa5c42cf4745197c77b0138c2e71bdd9690ed3d779d00969142382d35f1`

## Failure and triage

- Failing test: `tests/vst/test_s2_store_backed_pubsub.py::test_pending_dispatch_barrier_survives_store_reopen`, assertion at line 440.
- Exact assertion difference: expected `generation_mismatch.value.kind == "duplicate"`; actual kind was `"authorization"`.
- Classification: **test defect in its direct Store call**, confirmed and resolved by change record `docs/changes/0571-s2-cross-generation-recovery-test-fingerprint.md`. Current `Store.accept_dispatch_intent` requires a string `key_fingerprint` for the legacy path and raises authorization when it is absent (`tools/vst/store.py:1318-1322`). The test directly invoked the Store without that argument (`tests/vst/test_s2_store_backed_pubsub.py:435-439`). The production Supervisor path calculates the configured legacy key fingerprint and passes it to Store (`tools/vst/supervisor.py:694-702`). Thus the observed failure occurred before the test reached its intended service-generation duplicate assertion. The fixture now supplies the same trusted synthetic fingerprint and the unchanged focused selection passes in the separately recorded rerun. The assertions were not weakened.
- Scope limit: this failure does not establish an overall S2 defect or a runtime result. No restricted process-kill, crash/recovery, mutation, E8, or policy selectors were run. Two earlier command-construction/mount-preflight attempts exited before pytest; only the invocation above started tests.
- Historical evidence `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-test-run-20261029.md` records 130/130 at `c855ca4`; that prior result does not override this current-HEAD failure.

## Disposition

This file preserves the initial failing run as historical evidence; it is superseded for current acceptance by `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-rerun-56cd816-worktree-20261029.md`, which records 130 passed after the fixture correction. Commit-bound blob verification remains a separate delivery step. Owner for correction: Codex. Owner for the focused rerun: `e2e-runner`.
