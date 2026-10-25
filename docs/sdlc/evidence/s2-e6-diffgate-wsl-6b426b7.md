# S2 E6 diff-gate WSL evidence at `6b426b7`

## Scope and provenance

- Repository branch: `s2-isolated-worker-sandbox`.
- Exact committed HEAD: `6b426b775e7ce92ad2fe6d42c1ede7f620ee4994`.
- The worktree was clean before this evidence file was added.
- A fresh stage `/opt/vst-s2/source-6b426b7-e6-diffgate` was extracted from that exact HEAD. Inputs were `tools/vst`, `tests/vst/test_s2_diffgate.py`, and `docs/SANDBOX_SPEC.md`; no checkout-wide copy was made. Archive SHA-256: `a144f88f699d2494e1652763076d34dd5e95e6ce749c7625262348c9ed25c88b`.
- The module was inspected before execution. Its 17 collected cases call the deterministic diff-gate contract over synthetic path lists and have no process-kill, kill-table, mutation-testing, CI, external write, or migration behavior.
- Environment: Ubuntu 24.04.5 on WSL2; kernel `6.6.114.1-microsoft-standard-WSL2`; systemd `255.4-1ubuntu8.17`; Python 3.12.3; pytest 7.4.4. Execution identity: `vst-runner`, UID 997, GID 988.

## Acceptance mapping and result

| E6 criterion | Coverage in this module |
|---|---|
| Stable deterministic diff evidence | Allowed path normalization and stable digest cases. |
| Block unsafe file classes unless explicitly scoped | Seven blocked-path classes fail by default; an explicitly manifest-scoped case passes. |
| Reject unsafe or out-of-scope path changes | Four escaping/ambiguous path inputs, an out-of-scope path, rename into a blocked hook, and symlink change. |
| Bind result to manifest and candidate head | Evidence fields are asserted against the synthetic manifest and candidate head. |

## Command and outcome

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec systemd-run --wait --pipe --collect --unit=s2-diffgate-posix-6b426b7 --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/opt/vst-s2/source-6b426b7-e6-diffgate --property=InaccessiblePaths="/mnt/wsl /mnt/wslg /tmp/.X11-unix /usr/lib/wsl" --property=TemporaryFileSystem=/run/user:ro --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=90s --property=PrivateNetwork=yes --property=RestrictAddressFamilies=AF_UNIX -- /usr/bin/python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_diffgate.py
```

Result: exit 0; **17 passed, 0 skipped, 0 failed** in 0.05 seconds. Transient systemd unit completed successfully; service runtime was 659 ms, CPU time 552 ms, memory peak 256 KiB, and swap peak 0 bytes.

No implementation or test source was changed. No process-kill, kill-table, mutation, CI, build, or migration operation was run. This result proves only the E6 contract module at the listed HEAD and does not close other S2 acceptance gaps.
