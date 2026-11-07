# S2 peer-pidfd option resolution — focused functional run

Date: 2026-10-30

## Scope and source identity

This record covers the focused regression for resolving `SO_PEERPIDFD` when the
target Ubuntu 24.04 Python socket module does not export the Linux socket-option
constant. It also records the unchanged S2 dispatch-owner transport functional
module run against the same worktree.

The repository `HEAD` at execution was
`531874302f0c559fd83872fcb5d1880f41ca1bea` on branch
`s2-canonical-continuation`. The peer-pidfd source fix and service integrations
were uncommitted in the worktree; this result is therefore for that dirty
worktree based on the stated HEAD. It is **not** a run against a committed
revision or a clean checkout. The functional-test-reviewer added only
`tests/vst/test_s2_peer_pidfd.py`; the source changes were already present when
this test task began.

## Environment and exact command

Test execution used the existing `Ubuntu-24.04` WSL distribution as root. The
repository on `D:` was mounted read-only at `/mnt/d` within the same WSL process
that ran pytest. A separate read-only environment query after the run reported
Python `3.12.3`, kernel `6.6.114.1-microsoft-standard-WSL2`, and UID `0`.
`PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider` prevented Python bytecode
and pytest cache artifacts.

```sh
wsl.exe -d Ubuntu-24.04 -u root -- bash -lc 'set -e; mkdir -p /mnt/d; mountpoint -q /mnt/d || mount -t drvfs D: /mnt/d -o ro; cd /mnt/d/Repo/Virtual_scrum_team; PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/vst/test_s2_peer_pidfd.py tests/vst/test_s2_dispatch_owner_transport.py'
```

Actual output:

```text
.............................................                            [100%]
45 passed in 0.73s
```

Exit code: `0`.

## Coverage and result

The new file contributed 11 passing cases:

- A native `SO_PEERPIDFD` constant on the standard-library socket module is
  accepted directly, without numeric fallback.
- Explicit `None`, boolean, zero, negative, string, and floating-point option
  values fail closed, even under simulated Linux x86-64 conditions.
- Numeric ABI option `77` is returned only when the option is absent, the
  platform is Linux x86-64, and the supplied API is the actual standard-library
  socket module. A fake adapter without the option is refused.
- Numeric fallback is refused for Windows, Linux AArch64, and Darwin.

The existing `tests/vst/test_s2_dispatch_owner_transport.py` contributed 34
passing cases without modification. They continue to exercise the existing
credential, pidfd descriptor, liveness, refusal, and transport checks using
their established test adapters. The focused result does not itself establish
that an active production socket or service supports `SO_PEERPIDFD`.

## Worktree hashes

SHA-256 values observed after the run:

| File | SHA-256 |
|---|---|
| `tests/vst/test_s2_peer_pidfd.py` | `c6855945e18a6023e83b200f1b7b3ffbf452a60a3d0b01d5be807bd78f2b52a1` |
| `tools/vst/peer_pidfd.py` | `6950bc239fa2c7a706a03412dea3c8bef3519a104332a66c5e5317e311b5688f` |
| `tools/vst/dispatch_owner_transport.py` | `0bf582319359ae1c1cf04ec4928e5a994d98c5d40c47aab7d0130d1d7856ebb0` |
| `tools/vst/runner_service.py` | `c81619a9de113807cbc2722ecea313f47f696ac20b4b9696e7458eadce6aa6dc` |
| `tools/vst/signer.py` | `0641b79b4dfc274390b2c2d48587a5e94db344527718f789e625821a9c9fade9` |
| `tools/vst/supervisor_service.py` | `f635a0f09eb7b91ae73fbb6b6fe9203d4b44315e3e221243f7dc3b401b43fe4dd` |

The four service/transport files and `tools/vst/peer_pidfd.py` were dirty
before the test file was added. Other untracked runtime configuration/evidence
artifacts were present in the checkout and were left untouched; their
provenance is not asserted here.

## Limits

No runtime services, production keys, probes, or real owner-to-Runner requests
were started. No process-kill, crash-recovery, mutation-campaign, E8, or
restricted policy selector was run. These results establish focused source
behavior and the existing fixture transport contract only; they are not
production runtime, E5, or S2 acceptance evidence.
