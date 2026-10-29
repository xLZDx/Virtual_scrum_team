# S2 bounded WSL namespace snapshot — exact source/test HEAD `a6ea0dc`

Date: 2026-10-27. Repository: `D:\Repo\Virtual_scrum_team`.

## Scope and provenance

- Source/test HEAD: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`.
- Documentation HEAD before this evidence-only update: `a2ab23aa4ad65ec2a7f2565035ab457b74c38b3e`.
- `docs/SANDBOX_SPEC.md` was unchanged from the source/test HEAD; SHA-256: `2a09baa462fa073d56dfa9ad3c8b1a72682e07fcd40f9b773e18a05ac5b10c66`.
- Environment: dedicated `Ubuntu-24.04` WSL2 distribution; worker observer identity UID/GID `997:988` (`vst-runner`).
- Executor: Codex, read-only bounded systemd observer. No product source/test code, network request, loopback/external canary, test selector, signer, or key was used. No persistent unit or configuration was installed.

## Command and result

The observer ran in a transient systemd unit with `Delegate=yes`, `RuntimeMaxSec=30s`, `CPUQuota=100%`, `MemoryMax=2G`, `TasksMax=64`, `TemporaryFileSystem=/tmp:size=1G,mode=1777`, `PrivateNetwork=yes`, `RestrictAddressFamilies=AF_UNIX`, `NoNewPrivileges=yes`, empty capability bounding/ambient sets, and the existing WSL host-path masks. The exact invocation was:

```powershell
$py = 'import os,json; rows=[]; f=open("/proc/self/mountinfo",encoding="utf-8"); [rows.append((p[4],p[p.index("-")+1],p[p.index("-")+2],p[3],p[p.index("-")+3:])) for line in f if (p:=line.split())]; candidates=[{"fs":fs,"target":mp,"source":src} for mp,fs,src,root,opts in rows if fs in ("drvfs","9p","overlay") or (fs=="ext4" and mp!="/")]; paths=("/mnt/c","/mnt/d","/mnt/wsl","/mnt/wslg","/usr/lib/wsl","/usr/lib/modules","/var/tmp","/run/lock","/run/shm","/dev/mqueue"); print(json.dumps({"uid":os.geteuid(),"gid":os.getegid(),"mount_count":len(rows),"windows_drive_mount_count":sum(1 for mp,fs,src,root,opts in rows if fs=="drvfs" or (fs=="9p" and "aname=drvfs" in opts and src[:2].endswith(":"))),"host_mount_candidates":candidates,"masked_paths_readable_searchable":{p:os.access(p,os.R_OK|os.X_OK) for p in paths}},sort_keys=True))'
wsl.exe -d Ubuntu-24.04 -- systemd-run --wait --pipe --collect --unit=s2-e5-observer-primary2-a6ea0dc --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=/ --property=Delegate=yes --property=RuntimeMaxSec=30s --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=TemporaryFileSystem=/tmp:size=1G,mode=1777 --property=PrivateNetwork=yes --property=RestrictAddressFamilies=AF_UNIX --property=NoNewPrivileges=yes '--property=CapabilityBoundingSet=' '--property=AmbientCapabilities=' '--property=InaccessiblePaths=-/mnt/wsl -/mnt/wslg -/tmp/.X11-unix -/usr/lib/wsl -/usr/lib/modules -/var/tmp -/dev/mqueue -/run/lock -/run/shm' -- /usr/bin/python3 -c $py
```

The command exited 0; the transient unit completed successfully (98 ms, 256 KiB peak memory). Sanitized output:

```json
{"gid":988,"host_mount_candidates":[],"masked_paths_readable_searchable":{"/dev/mqueue":false,"/mnt/c":true,"/mnt/d":true,"/mnt/wsl":false,"/mnt/wslg":false,"/run/lock":false,"/run/shm":false,"/usr/lib/modules":false,"/usr/lib/wsl":false,"/var/tmp":false},"mount_count":29,"uid":997,"windows_drive_mount_count":0}
```

`/mnt/c` and `/mnt/d` existed as directory paths but had no matching drive-backed mount in the observed mount table; their `exists` state is not treated as evidence of host access. The observer reported no `drvfs`, `9p`, `overlay`, or non-root `ext4` mount candidates. The listed system-path masks were not readable/searchable by the observer. The separate host snapshot recorded complete socket enumeration with zero container socket paths; this observer did not independently enumerate sockets.

## Acceptance limits

This snapshot supports only the bounded mount-visibility facts above. It is not the standard-library E5 preflight, does not contain a runner-signed inventory or operator-root-signed attestation, and does not establish default-deny egress, the loopback canary, persistent deployment, or general host isolation. The earlier signed E5 run remains bound to source/test revision `280e2d0`; no signature was reused here. Stable delegated-parent/replacement behavior, populated stale-scope cleanup, runner crash/restart, and Windows nested Job Object behavior remain `NOT_VERIFIED` or `NOT_RUN` under the active scope.
