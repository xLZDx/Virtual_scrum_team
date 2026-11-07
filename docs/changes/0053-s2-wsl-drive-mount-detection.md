# 0053 S2 WSL Windows-drive mount detection

## What changed

- `tools/vst/preflight.py`: `automount_disabled` now derives from mounts whose source is a Windows drive root (`C:` or `C:\\`) and whose filesystem is `drvfs` directly or WSL `9p` with `aname=drvfs`. The inventory includes the explicit `windows_drive_mounts` list. Generic mount targets under `/mnt`, including WSLg `/mnt/wslg`, are not classified as Windows drives.
- `docs/SANDBOX_SPEC.md` and the S2 E5 acceptance criteria define the same detection contract and distinguish `/mnt/wslg` from a Windows drive mount.
- Decision/lesson logs and document registry were updated.

## Why

WSL diagnostic evidence on HEAD `c470542dbedf992b785804e421b1ff52e142003c` showed that `collect_inventory` treated every mount target containing `/mnt/` as Windows-drive automount. WSLg's `/mnt/wslg` therefore produced `automount_disabled=false` even when Windows drives were absent. Detection must use mount source and filesystem type, rather than broadly accepting any `/mnt` path or host mount.

## Verification state

No tests, checks, builds, CI, migrations or signed WSL probes were run. The E2E test owner is adding regression coverage for `/mnt/wslg` versus `/mnt/c`; run that coverage and the final signed sandbox probe only after this change lands.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation engineer (`gpt-6-luna`).
- Runtime/test owner: designated E2E agent.
- Next: execute the regression and signed WSL probe on the exact final source head.

Agent-Attribution: implementation-engineer (`gpt-6-luna`); Codex executor
